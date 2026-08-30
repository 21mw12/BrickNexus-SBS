from typing import Any, Dict
from sqlalchemy.orm import Session

from app.common.validators import ValidationError, validate_str, validate_update
from app.infra.DB.BaseRepository import BaseRepository
from .models.AssetRoom import AssetRoom
from .AssetRepository import AssetRepository


class AssetRoomRepository(BaseRepository[AssetRoom]):

    model = AssetRoom

    def __init__(self):
        # 资产主表 Repository
        self.asset_repo = AssetRepository()

    # ==========================================================
    # Hook
    # ==========================================================

    def _before_create(self, item: AssetRoom, db: Session) -> None:
        """ 创建前校验 """
        # 1. 校验基础字段
        if item.asset_id is None:
            raise ValidationError("asset_id must be input")
        if item.number is not None:
            validate_str(item.number, "number", max_len=20)
        if item.room_purpose is not None:
            validate_str(item.room_purpose, "room_purpose", max_len=100)
        if item.max_current is not None:
            validate_str(item.max_current, "max_current", max_len=20)
        if item.manager_name is not None:
            validate_str(item.manager_name, "manager_name", max_len=50)

        # 2. 检查基础资产是否存在
        asset = self.asset_repo.get(item.asset_id, db)
        if asset is None:
            raise ValidationError("asset not exists")

        # 3. 校验资产类型必须为 room
        if asset.asset_type != "room":
            raise ValidationError("asset_type must be room")

        # 4. 检查 room 扩展表是否已存在
        exists = self.exists(db, filters={ "asset_id": item.asset_id })
        if exists:
            raise ValidationError("asset room already exists")

    def _before_update(self, obj: AssetRoom, values: Dict[str, Any], db: Session) -> None:
        """ 更新前校验 """
        # 1. 定义允许更新字段
        allowed_fields = {"number", "room_purpose", "max_current", "manager_name"}

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
            "number": lambda v: validate_str(v, "number", max_len=20),
            "room_purpose": lambda v: validate_str(v, "room_purpose", max_len=100),
            "max_current": lambda v: validate_str(v, "max_current", max_len=20),
            "manager_name": lambda v: validate_str(v, "manager_name", max_len=50),
        }
        validate_update(filtered_values, rules)

        # 4. 回写过滤后的字段
        values.clear()
        values.update(filtered_values)
