from typing import Any, Dict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.validators import (
    ValidationError,
    validate_bool,
    validate_str,
    validate_update,
)
from app.core.utils.UUIDGenerator import uuid_generator
from app.infra.DB.BaseRepository import BaseRepository
from app.domain.user.repository.models.Role import Role


class RoleRepository(BaseRepository[Role]):

    model = Role

    # ==========================================================
    # Hook
    # ==========================================================

    def _before_create(self, item: Role, db: Session) -> None:
        """ 创建前校验 """
        # 1. 校验基础字段
        validate_str(item.name, "name", 30)
        validate_str(item.describe, "describe", 150)

        # 2. 校验角色名称是否重复
        stmt = select(Role).where(Role.name == item.name)
        exists = db.execute(stmt).scalars().first()
        if exists:
            raise ValidationError("role name already exists")

        # 3. 生成 role_id
        item.role_id = uuid_generator.random()

    def _before_update(self, obj: Role, values: Dict[str, Any], db: Session) -> None:
        """ 更新前校验 """
        # 1. 定义允许更新字段
        allowed_fields = {"name", "describe"}

        # 2. 过滤非法字段，无更新字段直接返回
        filtered_values = {
            k: v
            for k, v in values.items()
            if k in allowed_fields
        }
        if not filtered_values:
            return

        # 3. 定义字段校验规则，并校验
        rules = {
            "name": lambda v: validate_str(v, "name", 30),
            "describe": lambda v: validate_str(v, "describe", 150),
        }
        validate_update(values, rules)

        # 4. 回写过滤后的字段
        values.clear()
        values.update(filtered_values)
