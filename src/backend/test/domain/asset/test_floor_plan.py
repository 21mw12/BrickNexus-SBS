"""楼层平面图模型、图片和房间标记业务测试。"""

from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.repository.models.AssetFloor import AssetFloor
from app.domain.asset.repository.models.AssetRoom import AssetRoom
from app.domain.floor_plan.repository.models.FloorPlan import FloorPlan
from app.domain.floor_plan.repository.models.FloorRoomRegion import FloorRoomRegion
from app.domain.floor_plan.schema.FloorPlanSchema import FloorRoomRegionSaveSchema
from app.domain.floor_plan.service.FloorPlanService import FloorPlanService


def _png_bytes(width: int = 320, height: int = 180) -> bytes:
    """生成一个只存在于内存的合法 PNG 测试图片。"""
    stream = BytesIO()
    Image.new("RGB", (width, height), color="white").save(stream, format="PNG")
    return stream.getvalue()


def test_floor_and_room_ids_are_shared_primary_foreign_keys() -> None:
    """Floor 和 Room ID 不额外生成编号，同时承担主键和映射外键职责。"""
    floor_column = FloorPlan.__table__.c.floor_id
    room_column = FloorRoomRegion.__table__.c.room_id

    assert floor_column.primary_key is True
    assert {foreign_key.target_fullname for foreign_key in floor_column.foreign_keys} == {
        "assets_floor.asset_id"
    }
    assert room_column.primary_key is True
    assert {foreign_key.target_fullname for foreign_key in room_column.foreign_keys} == {
        "assets_room.asset_id"
    }


def test_decode_image_uses_real_content_and_original_size() -> None:
    """图片宽高和类型必须从真实内容读取，不能依赖用户文件名。"""
    width, height, suffix, image_type = FloorPlanService._decode_image(
        _png_bytes(640, 360)
    )

    assert (width, height) == (640, 360)
    assert suffix == ".png"
    assert image_type == "image/png"

    with pytest.raises(ValidationError, match="invalid image"):
        FloorPlanService._decode_image(b"not an image")


def test_write_and_delete_image_use_configured_floor_plan_directory(tmp_path, monkeypatch) -> None:
    """图片只写入 floorPlan 目录，并且可以按数据库文件名清理。"""
    monkeypatch.setattr(FloorPlanService, "IMAGE_DIRECTORY", tmp_path / "floorPlan")

    image_path = FloorPlanService._write_image("plan.png", _png_bytes())

    assert image_path == tmp_path / "floorPlan" / "plan.png"
    assert image_path.is_file()
    assert list((tmp_path / "floorPlan").glob("*.tmp")) == []

    FloorPlanService._delete_image("plan.png")
    assert image_path.exists() is False


class _RegionDb:
    """只实现 save_regions 测试所需的最小 Session 行为。"""

    def __init__(self, rooms):
        self.rooms = rooms
        self.saved = []
        self.commit_count = 0
        self.rollback_count = 0

    def execute(self, statement):
        rooms = self.rooms

        class _Result:
            def scalars(self):
                return self

            def all(self):
                return rooms

        return _Result()

    def add_all(self, models):
        self.saved.extend(models)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def test_save_regions_validates_room_floor_and_image_bounds(monkeypatch) -> None:
    """只有当前楼层的 Room 可以保存，并且矩形不能超过原图。"""
    plan = SimpleNamespace(image_width=1000, image_height=600)
    monkeypatch.setattr(FloorPlanService, "_require_floor", lambda floor_id, db: None)
    monkeypatch.setattr(FloorPlanService, "_require_plan", lambda floor_id, db: plan)
    monkeypatch.setattr(FloorPlanService, "_delete_floor_regions", lambda floor_id, db: None)
    monkeypatch.setattr(
        FloorPlanService,
        "get_floor_plan",
        lambda floor_id, db: {"floor_id": floor_id},
    )

    valid_room = SimpleNamespace(
        asset_id="room-1",
        asset_type="room",
        asset_id_parent="floor-1",
    )
    db = _RegionDb([valid_room])
    payload = FloorRoomRegionSaveSchema.model_validate(
        {
            "regions": [
                {"room_id": "room-1", "x": 10, "y": 20, "width": 300, "height": 200}
            ]
        }
    )

    result = FloorPlanService.save_regions("floor-1", payload, db)

    assert result == {"floor_id": "floor-1"}
    assert db.commit_count == 1
    assert len(db.saved) == 1
    assert db.saved[0].room_id == "room-1"

    out_of_bounds = FloorRoomRegionSaveSchema.model_validate(
        {
            "regions": [
                {"room_id": "room-1", "x": 900, "y": 20, "width": 200, "height": 100}
            ]
        }
    )
    with pytest.raises(ValidationError, match="exceeds image width"):
        FloorPlanService.save_regions("floor-1", out_of_bounds, _RegionDb([valid_room]))

    other_floor_room = SimpleNamespace(
        asset_id="room-1",
        asset_type="room",
        asset_id_parent="floor-2",
    )
    with pytest.raises(ValidationError, match="does not belong"):
        FloorPlanService.save_regions("floor-1", payload, _RegionDb([other_floor_room]))


def test_floor_plan_complete_lifecycle_with_real_session(tmp_path, monkeypatch) -> None:
    """用内存数据库验证上传、标记、替换清标记和删除文件的完整流程。"""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Asset.__table__,
        AssetFloor.__table__,
        AssetRoom.__table__,
        FloorPlan.__table__,
        FloorRoomRegion.__table__,
    ):
        table.create(engine)

    monkeypatch.setattr(FloorPlanService, "IMAGE_DIRECTORY", tmp_path / "floorPlan")
    with Session(engine, expire_on_commit=False) as db:
        db.add_all(
            [
                Asset(
                    asset_id="floor-1",
                    asset_id_parent="building-1",
                    asset_path="building-1/floor-1",
                    asset_type="floor",
                    name="一层",
                    is_use=True,
                ),
                AssetFloor(asset_id="floor-1", level="1"),
                Asset(
                    asset_id="room-1",
                    asset_id_parent="floor-1",
                    asset_path="building-1/floor-1/room-1",
                    asset_type="room",
                    name="会议室",
                    is_use=True,
                ),
                AssetRoom(asset_id="room-1", number="101"),
            ]
        )
        db.commit()

        first = FloorPlanService.upload_image(
            "floor-1",
            SimpleNamespace(file=BytesIO(_png_bytes(1000, 600))),
            db,
        )
        first_image_path = FloorPlanService.IMAGE_DIRECTORY / first["image_name"]
        assert first_image_path.is_file()

        saved = FloorPlanService.save_regions(
            "floor-1",
            FloorRoomRegionSaveSchema.model_validate(
                {
                    "regions": [
                        {
                            "room_id": "room-1",
                            "x": 100,
                            "y": 80,
                            "width": 300,
                            "height": 200,
                        }
                    ]
                }
            ),
            db,
        )
        assert saved["regions"][0]["room_name"] == "会议室"
        assert db.get(FloorRoomRegion, "room-1") is not None

        replaced = FloorPlanService.upload_image(
            "floor-1",
            SimpleNamespace(file=BytesIO(_png_bytes(800, 400))),
            db,
        )
        replacement_path = FloorPlanService.IMAGE_DIRECTORY / replaced["image_name"]
        assert replacement_path.is_file()
        assert first_image_path.exists() is False
        assert db.get(FloorRoomRegion, "room-1") is None

        assert FloorPlanService.delete_floor_plan("floor-1", db) is True
        assert db.get(FloorPlan, "floor-1") is None
        assert replacement_path.exists() is False

    engine.dispose()
