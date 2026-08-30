"""楼层平面图上传、查询、标记和文件生命周期管理。"""

import os
import uuid
from io import BytesIO
from pathlib import Path
from typing import Iterable

from PIL import Image, UnidentifiedImageError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.core.middleware.LogRecorder import get_logger
from app.domain.floor_plan.repository.FloorPlanRepository import FloorPlanRepository
from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.repository.models.AssetFloor import AssetFloor
from app.domain.floor_plan.repository.models.FloorPlan import FloorPlan
from app.domain.floor_plan.repository.models.FloorRoomRegion import FloorRoomRegion
from app.domain.floor_plan.schema.FloorPlanSchema import FloorRoomRegionSaveSchema

logger = get_logger(__name__)


class FloorPlanService:
    """以楼层为中心管理一张平面图和该楼层下的房间矩形标记。"""

    # 图片统一放在仓库 resources/floorPlan 下，数据库只保存生成后的文件名。
    IMAGE_DIRECTORY = Path(__file__).resolve().parents[4] / "resources" / "floorPlan"
    MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
    SUPPORTED_IMAGE_FORMATS = {
        "PNG": (".png", "image/png"),
        "JPEG": (".jpg", "image/jpeg"),
        "WEBP": (".webp", "image/webp"),
    }

    @staticmethod
    def _require_floor(floor_id: str, db: Session) -> Asset:
        """确认目标资产和楼层扩展记录同时存在。"""
        asset = db.get(Asset, floor_id)
        if asset is None or asset.asset_type != "floor":
            raise ValidationError("floor not found")
        if db.get(AssetFloor, floor_id) is None:
            raise ValidationError("floor not found")
        return asset

    @staticmethod
    def _require_plan(floor_id: str, db: Session) -> FloorPlan:
        """读取楼层平面图，不存在时阻止后续房间标记操作。"""
        plan = db.get(FloorPlan, floor_id)
        if plan is None:
            raise ValidationError("floor plan not found")
        return plan

    @classmethod
    def _decode_image(cls, content: bytes) -> tuple[int, int, str, str]:
        """按图片真实内容识别格式和尺寸，不信任上传文件名及 Content-Type。"""
        if not content:
            raise ValidationError("image file is empty")
        if len(content) > cls.MAX_IMAGE_SIZE_BYTES:
            raise ValidationError("image file size must be <= 10MB")

        try:
            with Image.open(BytesIO(content)) as image:
                image_format = str(image.format or "").upper()
                width, height = image.size
                # verify 会检查图片主体是否完整，避免只上传一个伪造文件头。
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValidationError("invalid image file") from exc

        format_info = cls.SUPPORTED_IMAGE_FORMATS.get(image_format)
        if format_info is None:
            raise ValidationError("image type must be PNG, JPEG or WEBP")
        if width <= 0 or height <= 0:
            raise ValidationError("image width and height must be greater than 0")

        suffix, image_type = format_info
        return width, height, suffix, image_type

    @classmethod
    def _build_image_path(cls, image_name: str) -> Path:
        """将数据库文件名安全地解析到固定图片目录内。"""
        if not image_name or Path(image_name).name != image_name:
            raise ValidationError("invalid floor plan image name")
        return cls.IMAGE_DIRECTORY / image_name

    @classmethod
    def _write_image(cls, image_name: str, content: bytes) -> Path:
        """先写临时文件再替换，避免异常中断后留下半张图片。"""
        cls.IMAGE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        image_path = cls._build_image_path(image_name)
        temporary_path = cls.IMAGE_DIRECTORY / f".{image_name}.{uuid.uuid4().hex}.tmp"
        try:
            temporary_path.write_bytes(content)
            os.replace(temporary_path, image_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return image_path

    @classmethod
    def _delete_image(cls, image_name: str | None) -> None:
        """删除磁盘图片；文件已不存在时视为清理完成。"""
        if not image_name:
            return
        try:
            cls._build_image_path(image_name).unlink(missing_ok=True)
        except Exception as exc:
            # 数据库事务已经完成时，文件清理失败只能记录日志，不能恢复数据库记录。
            logger.exception("楼层平面图文件删除失败 image_name=%s error=%s", image_name, exc)

    @staticmethod
    def _floor_room_ids(floor_id: str, db: Session) -> list[str]:
        """一次查询得到楼层直接包含的全部房间 ID。"""
        stmt = select(Asset.asset_id).where(
            Asset.asset_type == "room",
            Asset.asset_id_parent == floor_id,
        )
        return list(db.execute(stmt).scalars().all())

    @classmethod
    def _delete_floor_regions(cls, floor_id: str, db: Session) -> None:
        """清除一个楼层当前全部房间的标记。"""
        room_ids = cls._floor_room_ids(floor_id, db)
        if room_ids:
            db.execute(delete(FloorRoomRegion).where(FloorRoomRegion.room_id.in_(room_ids)))

    @classmethod
    def upload_image(cls, floor_id: str, upload_file, db: Session) -> dict:
        """上传或替换平面图；替换后旧坐标全部失效并被删除。"""
        cls._require_floor(floor_id, db)

        # UploadFile 使用临时文件，限制读取长度可以阻止超大文件全部进入内存。
        content = upload_file.file.read(cls.MAX_IMAGE_SIZE_BYTES + 1)
        width, height, suffix, image_type = cls._decode_image(content)
        image_name = f"{uuid.uuid4().hex}{suffix}"
        cls._write_image(image_name, content)

        repository = FloorPlanRepository()
        previous_plan = repository.get(floor_id, db)
        previous_image_name = previous_plan.image_name if previous_plan else None
        values = {
            "image_name": image_name,
            "image_width": width,
            "image_height": height,
            "image_type": image_type,
        }

        try:
            if previous_plan is None:
                repository.create(FloorPlan(floor_id=floor_id, **values), db)
            else:
                repository.update(floor_id, values, db)
                cls._delete_floor_regions(floor_id, db)
            db.commit()
        except Exception:
            db.rollback()
            cls._delete_image(image_name)
            raise

        # 新记录成功提交后才删除旧图片，避免事务失败时原图也无法继续读取。
        if previous_image_name and previous_image_name != image_name:
            cls._delete_image(previous_image_name)
        return cls.get_floor_plan(floor_id, db)

    @classmethod
    def get_floor_plan(cls, floor_id: str, db: Session) -> dict:
        """返回平面图元数据以及该楼层下当前已有的全部房间标记。"""
        cls._require_floor(floor_id, db)
        plan = cls._require_plan(floor_id, db)
        stmt = (
            select(FloorRoomRegion, Asset.name)
            .join(Asset, Asset.asset_id == FloorRoomRegion.room_id)
            .where(
                Asset.asset_type == "room",
                Asset.asset_id_parent == floor_id,
            )
            .order_by(Asset.name, Asset.asset_id)
        )
        region_rows = db.execute(stmt).all()
        regions = [
            {
                "room_id": region.room_id,
                "room_name": room_name,
                "x": region.x,
                "y": region.y,
                "width": region.width,
                "height": region.height,
            }
            for region, room_name in region_rows
        ]
        return {
            "floor_id": plan.floor_id,
            "image_name": plan.image_name,
            "image_width": plan.image_width,
            "image_height": plan.image_height,
            "image_type": plan.image_type,
            "image_url": f"/floor-plans/{plan.floor_id}/image",
            "regions": regions,
        }

    @classmethod
    def get_image_file(cls, floor_id: str, db: Session) -> tuple[Path, str]:
        """返回经过数据库记录验证的图片路径和 MIME 类型。"""
        cls._require_floor(floor_id, db)
        plan = cls._require_plan(floor_id, db)
        image_path = cls._build_image_path(plan.image_name)
        if not image_path.is_file():
            raise ValidationError("floor plan image file not found")
        return image_path, plan.image_type

    @classmethod
    def save_regions(
        cls,
        floor_id: str,
        payload: FloorRoomRegionSaveSchema,
        db: Session,
    ) -> dict:
        """校验后批量覆盖一个楼层的全部房间矩形标记。"""
        cls._require_floor(floor_id, db)
        plan = cls._require_plan(floor_id, db)
        regions = payload.regions
        room_ids = [region.room_id for region in regions]
        if len(room_ids) != len(set(room_ids)):
            raise ValidationError("room_id must not be duplicated")

        # 一次性加载全部目标 Room，避免逐条查询数据库。
        room_map: dict[str, Asset] = {}
        if room_ids:
            stmt = select(Asset).where(Asset.asset_id.in_(room_ids))
            room_map = {room.asset_id: room for room in db.execute(stmt).scalars().all()}

        models: list[FloorRoomRegion] = []
        for region in regions:
            room = room_map.get(region.room_id)
            if (
                room is None
                or room.asset_type != "room"
                or room.asset_id_parent != floor_id
            ):
                raise ValidationError(f"room does not belong to floor: {region.room_id}")
            if region.x + region.width > plan.image_width:
                raise ValidationError(f"room region exceeds image width: {region.room_id}")
            if region.y + region.height > plan.image_height:
                raise ValidationError(f"room region exceeds image height: {region.room_id}")
            models.append(FloorRoomRegion(**region.model_dump()))

        try:
            cls._delete_floor_regions(floor_id, db)
            if models:
                db.add_all(models)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return cls.get_floor_plan(floor_id, db)

    @classmethod
    def delete_floor_plan(cls, floor_id: str, db: Session) -> bool:
        """删除一个楼层的平面图记录、全部标记和实际图片。"""
        cls._require_floor(floor_id, db)
        plan = cls._require_plan(floor_id, db)
        image_name = plan.image_name
        try:
            cls._delete_floor_regions(floor_id, db)
            db.delete(plan)
            db.commit()
        except Exception:
            db.rollback()
            raise
        cls._delete_image(image_name)
        return True

    @staticmethod
    def delete_room_region(room_id: str, db: Session) -> None:
        """房间移动楼层时，在同一个资产事务中删除其旧标记。"""
        db.execute(delete(FloorRoomRegion).where(FloorRoomRegion.room_id == room_id))

    @classmethod
    def delete_for_assets(
        cls,
        floor_ids: Iterable[str],
        room_ids: Iterable[str],
        db: Session,
    ) -> list[str]:
        """资产树删除前清理数据库记录，并返回事务提交后需要删除的文件名。"""
        floor_id_list = list(set(floor_ids))
        room_id_set = set(room_ids)

        # 即使调用方只传 Floor，也补充查询其直接房间，保证标记不会残留。
        if floor_id_list:
            stmt = select(Asset.asset_id).where(
                Asset.asset_type == "room",
                Asset.asset_id_parent.in_(floor_id_list),
            )
            room_id_set.update(db.execute(stmt).scalars().all())

        if room_id_set:
            db.execute(
                delete(FloorRoomRegion).where(FloorRoomRegion.room_id.in_(room_id_set))
            )

        image_names: list[str] = []
        if floor_id_list:
            plans = db.execute(
                select(FloorPlan).where(FloorPlan.floor_id.in_(floor_id_list))
            ).scalars().all()
            image_names = [plan.image_name for plan in plans]
            db.execute(delete(FloorPlan).where(FloorPlan.floor_id.in_(floor_id_list)))
        return image_names

    @classmethod
    def delete_image_files(cls, image_names: Iterable[str]) -> None:
        """资产事务提交后统一删除已经失去数据库引用的图片。"""
        for image_name in image_names:
            cls._delete_image(image_name)
