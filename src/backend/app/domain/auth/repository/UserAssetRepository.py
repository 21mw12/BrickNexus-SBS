from typing import Any, Dict
from sqlalchemy.orm import Session

from app.common.validators import validate_str, validate_bool, validate_update
from app.core.utils.UUIDGenerator import uuid_generator
from app.infra.DB.BaseRepository import BaseRepository
from app.domain.auth.repository.models.UserAsset import UserAsset


class UserAssetRepository(BaseRepository[UserAsset]):
    model = UserAsset

    def _before_create(self, item: UserAsset, db: Session) -> None:
        """ 创建前校验 """
        # 1. 校验基础字段
        validate_str(item.user_id, "user_id", 100)
        validate_str(item.asset_id, "asset_id", 100)

        # 2. 生成 user_asset_id
        item.user_asset_id = uuid_generator.random()

    def _before_update(self, obj: UserAsset, values: Dict[str, Any], db: Session) -> None:
        """ 更新前校验 """
        # 1. 定义允许更新字段（仅权限布尔列）
        allowed_fields = {
            "perm_retrieve", "perm_update", "perm_delete", "perm_operate",
        }

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
            "perm_retrieve": lambda v: validate_bool(v, "perm_retrieve"),
            "perm_update": lambda v: validate_bool(v, "perm_update"),
            "perm_delete": lambda v: validate_bool(v, "perm_delete"),
            "perm_operate": lambda v: validate_bool(v, "perm_operate"),
        }
        validate_update(filtered_values, rules)

        # 4. 将过滤后的值写回 values 字典
        values.clear()
        values.update(filtered_values)
