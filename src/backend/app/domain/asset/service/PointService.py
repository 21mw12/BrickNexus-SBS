from typing import Any, Dict

from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.asset.repository.PointRepository import PointRepository
from app.domain.asset.schema.PointSchema import (
    PointAddSchema,
    PointResponseSchema,
    PointUpdateSchema,
)


class PointService:
    @staticmethod
    def list_points(db: Session, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        repo = PointRepository()
        total = repo.select(db, count_only=True)
        items = repo.select(db, page=page, page_size=limit, order_by=["point_name", "point_unit"])
        return {
            "total": total,
            "items": [PointResponseSchema.model_validate(item).model_dump() for item in items],
        }

    @staticmethod
    def find_point(point_id: str, db: Session) -> Dict[str, Any]:
        point = PointRepository().get(point_id, db=db)
        if point is None:
            raise ValidationError("point not found")
        return PointResponseSchema.model_validate(point).model_dump()

    @staticmethod
    def create_point(data: PointAddSchema, db: Session) -> Dict[str, Any]:
        point = PointRepository().create(data.to_model(), db=db)
        return PointResponseSchema.model_validate(point).model_dump()

    @staticmethod
    def update_point(point_id: str, data: PointUpdateSchema, db: Session) -> Dict[str, Any]:
        repo = PointRepository()
        point = repo.update(
            point_id,
            data.model_dump(exclude_unset=True),
            db=db,
        )
        if point is None:
            raise ValidationError("point not found")

        # SensorPoint 不保存描述；这里只刷新正在运行的采集任务缓存。
        sensor_point_ids = repo.get_sensor_point_ids(point_id, db)
        if sensor_point_ids:
            from app.domain.collector.loader.request_loader import request_loader

            request_loader.update_point_descriptions(
                {sensor_point_id: point.point_description for sensor_point_id in sensor_point_ids}
            )
        return PointResponseSchema.model_validate(point).model_dump()

    @staticmethod
    def delete_point(point_id: str, db: Session) -> bool:
        return PointRepository().delete(point_id, db=db)
