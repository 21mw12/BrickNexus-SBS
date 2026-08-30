from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.validators import validate_str, validate_update
from app.core.utils.UUIDGenerator import uuid_generator
from app.infra.DB.BaseRepository import BaseRepository
from .models.SensorPoint import SensorPoint


class SensorPointRepository(BaseRepository[SensorPoint]):

    model = SensorPoint

    def _before_create(self, item: SensorPoint, db: Session) -> None:
        """ 创建前自动生成 point_id """
        item.point_id = uuid_generator.random()

    def _before_update(self, obj: SensorPoint, values: Dict[str, Any], db: Session) -> None:
        """ 更新前校验：只允许修改 json_path """
        allowed_fields = {"json_path"}

        filtered_values = {
            k: v
            for k, v in values.items()
            if k in allowed_fields
        }
        if not filtered_values:
            values.clear()
            return

        rules = {
            "json_path": lambda v: validate_str(v, "json_path", max_len=200),
        }
        validate_update(filtered_values, rules)

        values.clear()
        values.update(filtered_values)

    def copy_from_model(self, model_id: str, sensor_id: str, db: Session) -> List[SensorPoint]:
        """ 从型号测点复制为传感器实例测点 """
        from .ModelPointRepository import ModelPointRepository
        model_point_repo = ModelPointRepository()
        model_points = model_point_repo.get_by_model_id(model_id, db)

        result = []
        for mp in model_points:
            sp = SensorPoint(
                sensor_id=sensor_id,
                source_model_id=mp.model_id,
                source_point_id=mp.point_id,
                point_name=mp.point_name,
                point_unit=mp.point_unit,
            )
            created = self.create(sp, db=db)
            if created is not None:
                result.append(created)
        return result

    def get_by_sensor_id(self, sensor_id: str, db: Session) -> List[SensorPoint]:
        """ 查询指定传感器的所有测点 """
        return self.select(db, filters={"sensor_id": sensor_id})

    def get_sensor_ids_by_point_ids(
        self,
        point_ids: List[str],
        db: Session,
    ) -> Dict[str, str]:
        """批量返回有效测点与 Sensor 资产的映射。"""
        if not point_ids:
            return {}

        # 同时关联 assets，避免把孤立测点或非 Sensor 资产当成有效测点。
        from .models.Asset import Asset

        rows = db.execute(
            select(SensorPoint.point_id, SensorPoint.sensor_id)
            .join(Asset, Asset.asset_id == SensorPoint.sensor_id)
            .where(
                SensorPoint.point_id.in_(point_ids),
                Asset.asset_type == "sensor",
            )
        ).all()
        return {point_id: sensor_id for point_id, sensor_id in rows}

    def delete_by_sensor_id(self, sensor_id: str, db: Session) -> int:
        """ 删除指定传感器的所有测点 """
        return self.bulk_delete("sensor_id", [sensor_id], db)
