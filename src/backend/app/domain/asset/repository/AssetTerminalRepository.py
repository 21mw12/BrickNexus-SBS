from typing import Any, Dict
from sqlalchemy.orm import Session

from app.common.validators import ValidationError, validate_str, validate_bool, validate_update
from app.infra.DB.BaseRepository import BaseRepository
from .models.AssetTerminal import AssetTerminal
from .AssetRepository import AssetRepository


class AssetTerminalRepository(BaseRepository[AssetTerminal]):

    model = AssetTerminal

    def __init__(self):
        # 资产主表 Repository
        self.asset_repo = AssetRepository()

    # ==========================================================
    # Hook
    # ==========================================================

    def _before_create(self, item: AssetTerminal, db: Session) -> None:
        """ 创建前校验 """
        # 1. 校验基础字段
        if item.asset_id is None:
            raise ValidationError("asset_id must be input")
        if item.request_id is not None:
            validate_str(item.request_id, "request_id", max_len=100)
        if item.number is not None:
            validate_str(item.number, "number", max_len=50)
        if item.model is not None:
            validate_str(item.model, "model", max_len=50)
        if item.location is not None:
            validate_str(item.location, "location", max_len=100)
        if item.iot_number is not None:
            validate_str(item.iot_number, "iot_number", max_len=50)
        if item.iot_activate_human is not None:
            validate_str(item.iot_activate_human, "iot_activate_human", max_len=50)

        # 2. 检查基础资产是否存在
        asset = self.asset_repo.get(item.asset_id, db)
        if asset is None:
            raise ValidationError("asset not exists")

        # 3. 校验资产类型必须为 terminal
        if asset.asset_type != "terminal":
            raise ValidationError("asset_type must be terminal")

        # 4. 检查 terminal 扩展表是否已存在
        exists = self.exists(db, filters={ "asset_id": item.asset_id })
        if exists:
            raise ValidationError("asset terminal already exists")

    def _before_update(self, obj: AssetTerminal, values: Dict[str, Any], db: Session) -> None:
        """ 更新前校验 """
        # 1. 定义允许更新字段
        allowed_fields = {"request_id", "number", "model", "location", "iot_number", "iot_activate_human", "last_receive_time", "is_online"}

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
            "request_id": lambda v: validate_str(v, "request_id", max_len=100) if v is not None else None,
            "number": lambda v: validate_str(v, "number", max_len=50),
            "model": lambda v: validate_str(v, "model", max_len=50),
            "location": lambda v: validate_str(v, "location", max_len=100),
            "iot_number": lambda v: validate_str(v, "iot_number", max_len=50),
            "iot_activate_human": lambda v: validate_str(v, "iot_activate_human", max_len=50),
            "is_online": lambda v: validate_bool(v, "is_online"),
        }
        validate_update(filtered_values, rules)

        # 4. 回写过滤后的字段
        values.clear()
        values.update(filtered_values)
