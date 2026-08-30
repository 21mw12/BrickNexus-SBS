from typing import Any, Dict
from sqlalchemy.orm import Session

from app.common.validators import ValidationError, validate_str, validate_update
from app.infra.DB.BaseRepository import BaseRepository
from .models.AssetBuilding import AssetBuilding
from .AssetRepository import AssetRepository


class AssetBuildingRepository(BaseRepository[AssetBuilding]):

    model = AssetBuilding

    def __init__(self):
        # 资产主表 Repository
        self.asset_repo = AssetRepository()

    # ==========================================================
    # Hook
    # ==========================================================

    def _before_create(self, item: AssetBuilding, db: Session) -> None:
        """ 创建前处理 """
        # 1. 校验基础字段
        if item.asset_id is None:
            raise ValidationError("asset_id must be input")
        if item.number is not None:
            validate_str(item.number, "number", max_len=50)
        if item.address is not None:
            validate_str(item.address, "address", max_len=200)

        # 2. 检查基础资产是否存在
        asset = self.asset_repo.get(item.asset_id, db)
        if asset is None:
            raise ValidationError("asset not exists")

        # 3. 校验资产类型必须为 building
        if asset.asset_type != "building":
            raise ValidationError("asset_type must be building")

        # 4. 检查 building 扩展表是否已存在
        exists = self.exists(db, filters={ "asset_id": item.asset_id })
        if exists:
            raise ValidationError("asset building already exists")

    def _before_update(self, obj: AssetBuilding, values: Dict[str, Any], db: Session) -> None:
        """ 更新前校验 """
        # 1. 定义允许更新字段
        allowed_fields = {"number", "address"}

        # 2. 过滤非法字段，无更新字段直接返回
        filtered_values = {
            k: v
            for k, v in values.items()
            if k in allowed_fields
        }
        if not filtered_values:
            values.clear()
            return

        # 3. 定义字段校验规则，并校验
        rules = {
            "number": lambda v: validate_str(v, "number", max_len=50),
            "address": lambda v: validate_str(v, "address", max_len=200),
        }
        validate_update(filtered_values, rules)

        # 4. 回写过滤后的字段
        values.clear()
        values.update(filtered_values)
