from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.validators import ValidationError, validate_str
from app.core.utils.UUIDGenerator import uuid_generator
from app.infra.DB.BaseRepository import BaseRepository
from .models.ModelPoint import ModelPoint
from .models.Point import Point
from .models.SensorPoint import SensorPoint


class PointRepository(BaseRepository[Point]):
    model = Point

    def _before_create(self, item: Point, db: Session) -> None:
        item.point_id = uuid_generator.random()
        validate_str(item.point_name, "point_name", max_len=20)
        if not isinstance(item.point_unit, str):
            raise ValidationError("point_unit must be a string")
        if len(item.point_unit) > 10:
            raise ValidationError("point_unit length must be <= 10")
        item.point_name = item.point_name.strip()
        # 无量纲或状态类测点使用空字符串表示无单位。
        item.point_unit = item.point_unit.strip()
        if item.point_description is not None:
            validate_str(item.point_description, "point_description", max_len=200)

        existing = db.scalar(
            select(Point.point_id).where(
                Point.point_name == item.point_name,
                Point.point_unit == item.point_unit,
            )
        )
        if existing is not None:
            raise ValidationError("point name and unit already exist")

    def _before_update(self, obj: Point, values: Dict[str, Any], db: Session) -> None:
        filtered_values = {
            key: value for key, value in values.items() if key == "point_description"
        }
        if not filtered_values:
            raise ValidationError("only point_description can be updated")
        description = filtered_values["point_description"]
        if description is not None:
            validate_str(description, "point_description", max_len=200)
        values.clear()
        values.update(filtered_values)

    def _before_delete(self, obj: Point, db: Session) -> None:
        binding = db.scalar(
            select(ModelPoint.model_id).where(ModelPoint.point_id == obj.point_id).limit(1)
        )
        if binding is not None:
            raise ValidationError("point is used by a model")

    def get_by_ids(self, point_ids: List[str], db: Session) -> Dict[str, Point]:
        if not point_ids:
            return {}
        points = self.select(db, filters={"point_id__in": point_ids})
        return {point.point_id: point for point in points}

    def get_sensor_point_ids(self, point_id: str, db: Session) -> list[str]:
        return list(
            db.scalars(
                select(SensorPoint.point_id).where(
                    SensorPoint.source_point_id == point_id
                )
            ).all()
        )
