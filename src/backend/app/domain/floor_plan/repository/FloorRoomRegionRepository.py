"""楼层房间矩形标记 Repository。"""

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.common.validators import ValidationError, validate_int, validate_str, validate_update
from app.infra.DB.BaseRepository import BaseRepository

from app.domain.floor_plan.repository.models.FloorRoomRegion import FloorRoomRegion


class FloorRoomRegionRepository(BaseRepository[FloorRoomRegion]):
    """负责房间标记字段的基础校验和数据库读写。"""

    model = FloorRoomRegion

    def _before_create(self, item: FloorRoomRegion, db: Session) -> None:
        validate_str(item.room_id, "room_id", max_len=100)
        validate_int(item.x, "x", min_value=0)
        validate_int(item.y, "y", min_value=0)
        validate_int(item.width, "width", min_value=1)
        validate_int(item.height, "height", min_value=1)
        if self.get(item.room_id, db) is not None:
            raise ValidationError("room region already exists")

    def _before_update(self, obj: FloorRoomRegion, values: Dict[str, Any], db: Session) -> None:
        allowed_fields = {"x", "y", "width", "height"}
        filtered_values = {key: value for key, value in values.items() if key in allowed_fields}
        rules = {
            "x": lambda value: validate_int(value, "x", min_value=0),
            "y": lambda value: validate_int(value, "y", min_value=0),
            "width": lambda value: validate_int(value, "width", min_value=1),
            "height": lambda value: validate_int(value, "height", min_value=1),
        }
        validate_update(filtered_values, rules)
        values.clear()
        values.update(filtered_values)
