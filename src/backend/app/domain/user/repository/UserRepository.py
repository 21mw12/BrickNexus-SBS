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
from app.domain.user.repository.models.User import User


class UserRepository(BaseRepository[User]):

    model = User

    # ==========================================================
    # Hook
    # ==========================================================


    def _before_create(self, item: User, db: Session) -> None:
        """ 创建前校验 """
        # 1. 校验基础字段
        validate_str(item.account, "account", 30)
        validate_str(item.nickname, "nickname", 30)
        validate_str(item.password, "password", 130)
        validate_str(item.role_id, "role_id", 100)

        # 2. 校验用户名称是否重复
        stmt = select(User).where(User.account == item.account)
        exists = db.execute(stmt).scalars().first()
        if exists:
            raise ValidationError("user account already exists")

        # 3. 生成 user_id
        item.user_id = uuid_generator.random()

    def _before_update(self, obj: User, values: Dict[str, Any], db: Session) -> None:
        """ 更新前校验 """
        # 1. 定义允许更新字段
        allowed_fields = {"account", "role_id", "nickname", "password"}

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
            "account": lambda v: validate_str(v, "account", 30),
            "role_id": lambda v: validate_str(v, "role_id", 100),
            "nickname": lambda v: validate_str(v, "nickname", 30),
            "password": lambda v: validate_str(v, "password", 130),
        }
        validate_update(values, rules)

        # 4. 回写过滤后的字段
        values.clear()
        values.update(filtered_values)
