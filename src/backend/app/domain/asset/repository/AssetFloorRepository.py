from typing import Any, Dict
from sqlalchemy.orm import Session

from app.common.validators import ValidationError, validate_str, validate_update
from app.infra.DB.BaseRepository import BaseRepository
from .models.AssetFloor import AssetFloor
from .AssetRepository import AssetRepository


class AssetFloorRepository(BaseRepository[AssetFloor]):

    model = AssetFloor

    def __init__(self):
        # 资产主表 Repository
        self.asset_repo = AssetRepository()

    # ==========================================================
    # Hook
    # ==========================================================

    def _before_create(self, item: AssetFloor, db: Session) -> None:
        """ 创建前校验 """
        # 1. 校验基础字段
        if item.asset_id is None:
            raise ValidationError("asset_id must be input")
        if item.level is not None:
            validate_str(item.level, "level", max_len=20)

        # 2. 检查基础资产是否存在
        asset = self.asset_repo.get(item.asset_id, db)
        if asset is None:
            raise ValidationError("asset not exists")

        # 3. 校验资产类型必须为 floor
        if asset.asset_type != "floor":
            raise ValidationError("asset_type must be floor")

        # 4. 检查 floor 扩展表是否已存在
        exists = self.exists(db, filters={ "asset_id": item.asset_id })
        if exists:
            raise ValidationError("asset floor already exists")

    def _before_update(self, obj: AssetFloor, values: Dict[str, Any], db: Session) -> None:
        """ 更新前校验 """
        # 1. 定义允许更新字段
        allowed_fields = {"level"}

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
            "level": lambda v: validate_str(v, "level", max_len=20),
        }
        validate_update(filtered_values, rules)

        # 4. 回写过滤后的字段
        values.clear()
        values.update(filtered_values)
