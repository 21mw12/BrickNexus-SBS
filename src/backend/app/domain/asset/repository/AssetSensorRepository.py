from typing import Any, Dict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.validators import ValidationError, validate_str, validate_bool, validate_update
from app.infra.DB.BaseRepository import BaseRepository
from .models.AssetSensor import AssetSensor
from .models.Asset import Asset


class AssetSensorRepository(BaseRepository[AssetSensor]):
    model = AssetSensor

    def _before_create(self, item: AssetSensor, db: Session) -> None:
        """ 创建前校验 """
        # 1. 校验
        if item.asset_id is None:
            raise ValidationError("asset not exists")
        if item.model_id is not None:
            validate_str(item.model_id, "model_id", max_len=100)

        # 2. 检查基础资产是否存在
        stmt = select(Asset).where(Asset.asset_id == item.asset_id)
        if not db.execute(stmt).scalars().first():
            raise ValidationError("asset not exists")

        # 3. 检查类型表是否已存在
        stmt = select(AssetSensor).where(AssetSensor.asset_id == item.asset_id)
        if db.execute(stmt).scalars().first():
            raise ValidationError("asset type already exists")

    def _after_create(self, item: AssetSensor, db: Session) -> None:
        """ 创建后：将型号测点复制为传感器实例测点 """
        if item.model_id:
            from app.domain.asset.service.SensorPointService import SensorPointService
            SensorPointService.copy_from_model(item.model_id, item.asset_id, db)

    def _before_update(self, obj: AssetSensor, values: Dict[str, Any], db: Session) -> None:
        """ 更新前校验：仅允许更新 is_online 和 last_receive_time """
        # 1. 定义允许更新字段
        allowed_fields = {"is_online", "last_receive_time"}

        # 2. 过滤非法字段，无更新字段直接返回
        filtered_values = {
            k: v
            for k, v in values.items()
            if k in allowed_fields
        }
        if not filtered_values:
            values.clear()
            return

        # 3. 字段校验规则
        rules = {
            "is_online": lambda v: validate_bool(v, "is_online"),
        }
        validate_update(filtered_values, rules)

        # 4. 回写过滤后的字段
        values.clear()
        values.update(filtered_values)
