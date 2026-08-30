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
from app.domain.user.repository.models.Page import Page


class PageRepository(BaseRepository[Page]):

    model = Page

    # ==========================================================
    # Hook
    # ==========================================================

    def _before_create(self, item: Page, db: Session) -> None:
        """ 创建前校验 """
        # 1. 校验基础字段
        validate_str(item.name, "name", 50)
        validate_str(item.path_code, "path_code", 50)
        if item.page_id_parent is not None:
            validate_str(item.page_id_parent, "page_id_parent", max_len=100)

        # 2. 校验页面名称是否重复
        stmt = select(Page).where(Page.name == item.name)
        exists = db.execute(stmt).scalars().first()
        if exists:
            raise ValidationError("page name already exists")
        
        # 3. 检查父页面存在
        if item.page_id_parent:
            parent = db.get(Page, item.page_id_parent)
            if parent is None:
                raise ValidationError("page_id_parent not found")
        
        # 4. 生成 page_id
        item.page_id = uuid_generator.random()

    def _before_update(self, obj: Page, values: Dict[str, Any], db: Session) -> None:
        """ 更新前校验 """
        # 1. 定义允许更新字段
        allowed_fields = {"page_id_parent", "name", "path_code"}

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
            "page_id_parent": lambda v: validate_str(v, "page_id_parent", 100),
            "name": lambda v: validate_str(v, "name", 50),
            "path_code": lambda v: validate_str(v, "path_code", 50),
        }
        validate_update(values, rules)

        # 4. 回写过滤后的字段
        values.clear()
        values.update(filtered_values)
