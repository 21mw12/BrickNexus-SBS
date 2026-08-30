from typing import Any, Dict
from sqlalchemy.orm import Session

from app.common.validators import ValidationError, validate_str, validate_update
from app.core.utils.UUIDGenerator import uuid_generator
from app.infra.DB.BaseRepository import BaseRepository
from .models.SensorModel import SensorModel


class SensorModelRepository(BaseRepository[SensorModel]):

    model = SensorModel

    def _before_create(self, item: SensorModel, db: Session) -> None:
        """ 创建前校验 """
        # 1. 自动生成 model_id
        item.model_id = uuid_generator.random()

        # 2. 校验字段
        if item.sensor_type is not None:
            validate_str(item.sensor_type, "sensor_type", max_len=50)
        if item.model_name is not None:
            validate_str(item.model_name, "model_name", max_len=50)
        if item.remark is not None:
            validate_str(item.remark, "remark", max_len=100)

    def _before_update(self, obj: SensorModel, values: Dict[str, Any], db: Session) -> None:
        """ 更新前校验 """
        # 1. 定义允许更新字段（model_id 为主键不可修改）
        allowed_fields = {"sensor_type", "model_name", "remark"}

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
            "sensor_type": lambda v: validate_str(v, "sensor_type", max_len=50),
            "model_name": lambda v: validate_str(v, "model_name", max_len=50),
            "remark": lambda v: validate_str(v, "remark", max_len=100),
        }
        validate_update(filtered_values, rules)

        # 4. 回写过滤后的字段
        values.clear()
        values.update(filtered_values)
