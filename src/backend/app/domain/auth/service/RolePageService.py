from typing import List
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.auth.repository.models import RolePage
from app.domain.user.repository import PageRepository
from app.domain.auth.repository import RolePageRepository


class RolePageService:
    """角色的页面缺陷相关业务逻辑封装"""

    # ==========================================================
    # 功能性Service
    # ==========================================================

    @staticmethod
    def save_role_page_permission(role_id: str, page_ids: List[str], db: Session) -> int:
        """
        保存角色的页面权限
        :param role_id: 角色 ID
        :param page_ids: 页面 ID 列表
        :param db: 数据库会话
        :return: 保存的数量
        """
        # 1. 参数校验
        if role_id is None or page_ids is None:
            return 0
        if not isinstance(page_ids, list):
            raise ValidationError("page_ids must be a list")

        # 2. 去重并过滤空值
        unique_page_ids = [pid for pid in dict.fromkeys(page_ids) if pid]
        if not unique_page_ids:
            return 0

        # 3. 过滤不存在的页面
        page_repo = PageRepository()
        pages = page_repo.select(filters={"page_id__in": unique_page_ids}, db=db)
        valid_ids = {page.page_id for page in pages}
        if not valid_ids:
            return 0

        # 4. 构造角色页面权限对象
        role_page_list: List[RolePage] = []
        for page_id in unique_page_ids:
            if page_id not in valid_ids:
                continue
            role_page_list.append(RolePage(role_id=role_id, page_id=page_id))

        if not role_page_list:
            return 0

        # 5. 批量保存
        role_page_repo = RolePageRepository()
        result = role_page_repo.bulk_create(role_page_list, db=db)

        return len(result)

    def alter_role_page_permission(self, role_id: str, page_ids: List[str], db: Session) -> int:
        """
        修改角色页面权限（先删除角色已有权限，再批量写入新权限）
        :param role_id: 角色 ID
        :param page_ids: 页面 ID 列表
        :param db: 数据库会话
        :return: 保存的数量
        """
        # 1. 删除角色已有权限
        self.drop_page_permission_by_role_id(role_id, db)

        # 2. 无新权限
        if page_ids is None:
            return 0

        # 3. 写入新权限
        return self.save_role_page_permission(role_id, page_ids, db)

    @staticmethod
    def query_role_page_permission(role_id: str, db: Session) -> List[str]:
        """
        根据角色 ID 查询对应的页面权限
        :param role_id: 角色 ID
        :param db: 数据库会话
        :return: 页面编码列表
        """
        # 1. 参数校验
        if not role_id:
            raise ValidationError("role_id is required")

        # 2. 查询角色页面权限
        role_page_repo = RolePageRepository()
        records = role_page_repo.select(db, filters={"role_id": role_id})
        if not records:
            return []

        page_ids = [item.page_id for item in records]
        if not page_ids:
            return []

        # 3. 获取页面编码
        page_repo = PageRepository()
        pages = page_repo.select(
            db,
            filters={"page_id__in": page_ids},
        )
        path_map = {page.page_id: page.path_code for page in pages}

        return [path_map[pid] for pid in page_ids if pid in path_map]

    @staticmethod
    def drop_page_permission_by_role_id(role_id: str, db: Session) -> int:
        """
        根据角色 ID 删除对应的页面权限
        :param role_id: 角色 ID
        :param db: 数据库会话
        :return: 删除的数量
        """
        # 1. 参数校验
        if not role_id:
            return 0

        # 2. 批量删除
        role_page_repo = RolePageRepository()
        return role_page_repo.bulk_delete("role_id", [role_id], db)

    @staticmethod
    def drop_page_permission_by_page_id(page_id: str, db: Session) -> int:
        """
        根据页面 ID 删除对应的页面权限
        :param page_id: 页面 ID
        :param db: 数据库会话
        :return: 删除的数量
        """
        # 1. 参数校验
        if not page_id:
            return 0

        # 2. 批量删除
        role_page_repo = RolePageRepository()
        return role_page_repo.bulk_delete("page_id", [page_id], db)
