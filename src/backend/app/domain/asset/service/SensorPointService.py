from typing import List
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.asset.repository.ModelPointRepository import ModelPointRepository
from app.domain.asset.repository.SensorPointRepository import SensorPointRepository
from app.domain.asset.repository.models.SensorPoint import SensorPoint


class SensorPointService:

    @staticmethod
    def copy_from_model(model_id: str, sensor_id: str, db: Session) -> List[SensorPoint]:
        """
        创建传感器实例时，将型号测点（model_point）复制为传感器实例测点（sensor_point）。
        :param model_id:  传感器型号ID
        :param sensor_id: 传感器资产ID
        :param db:        数据库会话
        :return:          创建的 SensorPoint 列表
        """
        if not model_id:
            raise ValidationError("model_id is required")

        model_point_repo = ModelPointRepository()
        model_points = model_point_repo.get_by_model_id(model_id, db)

        if not model_points:
            return []

        point_repo = SensorPointRepository()
        result = []
        for mp in model_points:
            sp = SensorPoint(
                sensor_id=sensor_id,
                source_model_id=mp.model_id,
                source_point_id=mp.point_id,
                point_name=mp.point_name,
                point_unit=mp.point_unit,
            )
            created = point_repo.create(sp, db=db)
            if created is not None:
                result.append(created)
        return result

    @staticmethod
    def update_json_path(point_id: str, json_path: str, db: Session) -> SensorPoint | None:
        """
        修改传感器实例测点的 JSON 路径（仅允许修改此字段）。
        :param point_id:  测点ID
        :param json_path: JSON 数据提取路径
        :param db:        数据库会话
        :return:          更新后的 SensorPoint 或 None
        """
        if not point_id:
            raise ValidationError("point_id is required")

        point_repo = SensorPointRepository()
        point = point_repo.get(point_id, db)
        if point is None:
            return None

        updated = point_repo.update(point_id, {"json_path": json_path}, db=db)
        return updated
