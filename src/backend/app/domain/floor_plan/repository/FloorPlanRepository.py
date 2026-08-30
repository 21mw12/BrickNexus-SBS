"""楼层平面图 Repository。"""

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.common.validators import ValidationError, validate_int, validate_str, validate_update
from app.infra.DB.BaseRepository import BaseRepository

from app.domain.floor_plan.repository.models.FloorPlan import FloorPlan


class FloorPlanRepository(BaseRepository[FloorPlan]):
    """负责平面图字段的基础校验和数据库读写。"""

    model = FloorPlan

    def _before_create(self, item: FloorPlan, db: Session) -> None:
        validate_str(item.floor_id, "floor_id", max_len=100)
        validate_str(item.image_name, "image_name", max_len=100)
        validate_int(item.image_width, "image_width", min_value=1)
        validate_int(item.image_height, "image_height", min_value=1)
        validate_str(item.image_type, "image_type", max_len=50)
        if self.get(item.floor_id, db) is not None:
            raise ValidationError("floor plan already exists")

    def _before_update(self, obj: FloorPlan, values: Dict[str, Any], db: Session) -> None:
        allowed_fields = {"image_name", "image_width", "image_height", "image_type"}
        filtered_values = {key: value for key, value in values.items() if key in allowed_fields}
        rules = {
            "image_name": lambda value: validate_str(value, "image_name", max_len=100),
            "image_width": lambda value: validate_int(value, "image_width", min_value=1),
            "image_height": lambda value: validate_int(value, "image_height", min_value=1),
            "image_type": lambda value: validate_str(value, "image_type", max_len=50),
        }
        validate_update(filtered_values, rules)
        values.clear()
        values.update(filtered_values)
