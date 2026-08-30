from typing import Any, Dict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.asset.repository.SensorModelRepository import SensorModelRepository
from app.domain.asset.repository.ModelPointRepository import ModelPointRepository
from app.domain.asset.repository.PointRepository import PointRepository
from app.domain.asset.repository.models.AssetSensor import AssetSensor
from app.domain.asset.repository.models.SensorPoint import SensorPoint
from app.domain.asset.schema.SensorModelSchema import (
    SensorModelAddSchema,
    SensorModelUpdateSchema,
    SensorModelResponseSchema,
)


class SensorModelService:

    @staticmethod
    def list_models(db: Session, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        """ 分页查询所有传感器型号（含测点） """
        model_repo = SensorModelRepository()
        point_repo = ModelPointRepository()
        total = model_repo.select(db, count_only=True)
        items = model_repo.select(db, page=page, page_size=limit)

        model_ids = [m.model_id for m in items]
        points_map = point_repo.get_by_model_ids(model_ids, db)

        result = [
            SensorModelResponseSchema.from_model(m, points_map.get(m.model_id)).model_dump()
            for m in items
        ]
        return {"total": total, "items": result}

    @staticmethod
    def find_model(model_id: str, db: Session) -> Dict[str, Any]:
        """ 查询单个传感器型号（含测点） """
        model_repo = SensorModelRepository()
        point_repo = ModelPointRepository()
        model = model_repo.get(model_id, db=db)
        if model is None:
            raise ValidationError("sensor model not found")

        points = point_repo.get_by_model_id(model_id, db)
        return SensorModelResponseSchema.from_model(model, points).model_dump()

    @staticmethod
    def create_model(data: SensorModelAddSchema, db: Session) -> Dict[str, Any]:
        """ 创建传感器型号（含测点） """
        model_repo = SensorModelRepository()
        point_repo = ModelPointRepository()
        definition_repo = PointRepository()

        point_ids = [point.point_id for point in data.points or []]
        if len(point_ids) != len(set(point_ids)):
            raise ValidationError("duplicate point_id")
        definitions = definition_repo.get_by_ids(point_ids, db)
        missing_ids = [point_id for point_id in point_ids if point_id not in definitions]
        if missing_ids:
            raise ValidationError(f"point not found: {missing_ids[0]}")

        model = data.to_model()
        model = model_repo.create(model, db=db)

        points = []
        if point_ids:
            points = point_repo.create_points(model.model_id, point_ids, db)

        return SensorModelResponseSchema.from_model(model, points).model_dump()

    @staticmethod
    def update_model(model_id: str, data: SensorModelUpdateSchema, db: Session) -> Dict[str, Any]:
        """修改型号基本信息；测点绑定创建后不可修改。"""
        model_repo = SensorModelRepository()
        point_repo = ModelPointRepository()
        payload = data.model_dump(exclude_none=True)
        model = model_repo.update(model_id, payload, db=db)
        if model is None:
            raise ValidationError("sensor model not found")

        points = point_repo.get_by_model_id(model_id, db)
        return SensorModelResponseSchema.from_model(model, points).model_dump()

    @staticmethod
    def delete_model(model_id: str, db: Session) -> bool:
        """ 删除传感器型号（级联删除测点） """
        model_repo = SensorModelRepository()
        point_repo = ModelPointRepository()

        used_by_sensor = db.scalar(
            select(AssetSensor.asset_id).where(AssetSensor.model_id == model_id).limit(1)
        )
        used_by_sensor_point = db.scalar(
            select(SensorPoint.point_id)
            .where(SensorPoint.source_model_id == model_id)
            .limit(1)
        )
        if used_by_sensor is not None or used_by_sensor_point is not None:
            raise ValidationError("sensor model is used by a sensor")

        point_repo.delete_by_model_id(model_id, db)
        return model_repo.delete(model_id, db=db)
