from typing import Any, Dict

from sqlalchemy.orm import Session

from app.common.validators import validate_str, validate_update
from app.infra.DB.BaseRepository import BaseRepository
from app.domain.auth.repository.models.RolePage import RolePage


class RolePageRepository(BaseRepository[RolePage]):
    model = RolePage

    def _before_create(self, item: RolePage, db: Session) -> None:
        """ 创建前校验 """
        # 1. 校验基础字段
        validate_str(item.role_id, "role_id", 100)
        validate_str(item.page_id, "page_id", 100)
