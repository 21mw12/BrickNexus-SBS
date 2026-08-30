from typing import List, Dict, Optional, Any, Set
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.user.repository import RoleRepository
from app.domain.auth.repository import RolePageRepository
from app.domain.user.schema import *
from app.domain.auth.service.RolePageService import RolePageService
from app.domain.auth.service.RoleAssetService import RoleAssetService


class RoleService:
    """角色相关业务逻辑封装"""

    # ==========================================================
    # API相关Service
    # ==========================================================

    @staticmethod
    def query_roles_form(
            db: Session,
            page: int = 1, limit: int = 20,
            filters: Optional[RoleQueryFilterSchema] = None
    ) -> Dict[str, Any]:
        """
        分页/模糊查询角色信息，支持按角色名模糊匹配
        :param db: 数据库会话
        :param page: 当前页
        :param limit: 页数量
        :param filters: 模糊查询条件
        :return: {"items": [...], "total": count}
        """
        payload: Dict[str, Any] = {}
        if filters is not None:
            if hasattr(filters, "model_dump"):
                payload = filters.model_dump(exclude_none=True)
            elif isinstance(filters, dict):
                payload = filters

        repo_filters: Dict[str, Any] = {}
        if payload.get("name"):
            repo_filters["name__like"] = payload.get("name")
        if payload.get("describe"):
            repo_filters["describe__like"] = payload.get("describe")

        role_repo = RoleRepository()

        # 查询符合筛选条件的总数
        total = role_repo.select(db, filters=repo_filters or None, count_only=True)

        # 分页查询
        roles = role_repo.select(
            db,
            filters=repo_filters or None,
            page=page,
            page_size=limit,
        )

        items: List[Dict[str, Any]] = []
        for role in roles:
            items.append({
                "role_id": role.role_id,
                "name": role.name,
                "describe": role.describe,
            })
        return {"items": items, "total": total}

    @staticmethod
    def query_role_by_id(role_id: str, db: Session) -> Dict[str, Any]:
        """
        根据角色 ID 去查询角色信息
        :param role_id: 角色 ID
        :param db: 数据库会话
        :return: 查询到的角色对象的字典
        """
        # 1. 参数校验
        if not role_id:
            raise ValidationError("role_id is required")

        # 2. 查询角色
        role_repo = RoleRepository()
        role = role_repo.get(role_id, db=db)
        if role is None:
            raise ValidationError("role not exists")

        # 3. 查询页面权限
        role_page_repo = RolePageRepository()
        role_pages = role_page_repo.select(db, filters={"role_id": role_id})
        page_ids = [item.page_id for item in role_pages]
        page_codes = RolePageService().query_role_page_permission(role_id, db=db)

        # 4. 查询资产权限
        asset_permission = RoleAssetService().query_role_asset_permission(role_id, db=db)

        # 5. 构造响应
        result = RoleResponseSchema.from_models(
            role=role,
            page_ids=page_ids,
            page_codes=page_codes,
            asset_permission=asset_permission,
        )
        return result.model_dump(exclude_none=True)

    @staticmethod
    def save_new_role(role_data: RoleAddSchema, db: Session) -> Dict[str, Any]:
        """
        创建角色
        :param role_data: 用于新建角色 Schema 对象
        :param db: 数据库会话
        :return: 新建的角色对象的字典
        """
        # 1. schema 转 dict
        if hasattr(role_data, "model_dump"):
            payload = role_data.model_dump(exclude_none=True)
        else:
            payload = role_data
        if not isinstance(payload, dict):
            raise ValidationError("invalid payload")

        # 2. Repository & Service
        role_repo = RoleRepository()
        role_page_service = RolePageService()
        role_asset_service = RoleAssetService()

        # 3. 开启事务
        try:
            # 4. 构造角色对象，并创建
            role = role_data.to_role_model()
            role = role_repo.create(role, db=db)
            if role is None:
                raise ValidationError("create role failed")

            # 5. 写入角色-页面关联（仅当传了 page_ids 时）
            if "page_ids" in payload:
                role_page_service.save_role_page_permission(role.role_id, payload.get("page_ids") or [], db=db)

            # 6. 写入角色-资产权限（仅当传了 asset_permission 时）
            if "asset_permission" in payload:
                role_asset_service.save_role_asset_permission(role.role_id, payload.get("asset_permission") or [], db=db)

            # 7. 提交事务 & refresh
            db.commit()
            db.refresh(role)

            # 8. 构造响应
            return {
                "role_id": role.role_id,
                "name": role.name,
                "describe": role.describe
            }

        except Exception:
            # 9. 回滚事务
            db.rollback()

            raise

    @staticmethod
    def alter_role_by_id(role_id: str, role_data: RoleUpdateSchema, db: Session) -> Dict[str, Any]:
        """
        根据角色 ID 对角色进行修改。若资产权限变更导致 R 权限被移除，级联清理用户 U/D/O。
        :param role_id: 角色 ID
        :param role_data: 用于修改角色 Schema 对象
        :param db: 数据库会话
        :return: 修改的角色对象的字典
        """
        # 1. schema 转 dict
        if hasattr(role_data, "model_dump"):
            payload = role_data.model_dump(exclude_none=True)
        else:
            payload = role_data
        if not isinstance(payload, dict):
            raise ValidationError("invalid payload")

        # 2. Repository & Service
        role_repo = RoleRepository()
        role_page_service = RolePageService()
        role_asset_service = RoleAssetService()

        # 3. 查询角色
        role = role_repo.get(role_id, db=db)
        if role is None:
            raise ValidationError("role not exists")

        # 4. 记录旧的资产 R 权限（用于检测被移除的 R）
        old_r_asset_ids: Set[str] = set()
        if "asset_permission" in payload:
            old_perm = role_asset_service.query_role_asset_permission(role_id, db=db)
            if old_perm and old_perm.part_asset_id:
                stack = list(old_perm.part_asset_id)
                while stack:
                    node = stack.pop()
                    aid = node.asset_id
                    if aid and "R" in (node.permission or ""):
                        old_r_asset_ids.add(aid)
                    children = node.sub_assets or []
                    stack.extend(children)

        # 5. 开启事务
        try:
            # 6. 更新角色基础信息
            role = role_repo.update(role_id, payload, db=db)

            # 7. 更新角色页面权限
            if "page_ids" in payload:
                role_page_service.alter_role_page_permission(
                    role_id,
                    payload.get("page_ids") or [],
                    db=db,
                )

            # 8. 更新角色资产权限
            if "asset_permission" in payload:
                role_asset_service.alter_role_asset_permission(
                    role_id,
                    payload.get("asset_permission"),
                    db=db,
                )

                # 9. 检测被移除的 R 权限，级联清理用户 U/D/O
                new_perm = role_asset_service.query_role_asset_permission(role_id, db=db)
                new_r_asset_ids: Set[str] = set()
                if new_perm and new_perm.part_asset_id:
                    stack = list(new_perm.part_asset_id)
                    while stack:
                        node = stack.pop()
                        aid = node.asset_id
                        if aid and "R" in (node.permission or ""):
                            new_r_asset_ids.add(aid)
                        children = node.sub_assets or []
                        stack.extend(children)

                removed_r_ids = old_r_asset_ids - new_r_asset_ids
                if removed_r_ids:
                    role_asset_service.remove_role_r_permission(
                        role_id,
                        list(removed_r_ids),
                        db=db,
                    )

            # 10. 提交事务 & refresh
            db.commit()
            db.refresh(role)

            # 11. 刷新该角色的共享 Redis 缓存
            from app.domain.user.service.UserService import UserService
            UserService.refresh_role_cache(role_id, db=db)

            # 12. 构造响应
            return {
                "role_id": role.role_id,
                "name": role.name,
                "describe": role.describe
            }

        except Exception:
            db.rollback()
            raise

    @staticmethod
    def drop_role_by_id(role_id: str, db: Session) -> bool:
        """
        删除角色
        :param role_id: 角色 ID
        :param db: 数据库会话
        :return: 删除是否成功
        """
        # 1. Repository & Service
        role_repo = RoleRepository()
        role_page_service = RolePageService()
        role_asset_service = RoleAssetService()
        
        # 2. 参数校验
        if not role_id:
            raise ValidationError("role_id is required")

        # 3. 查询角色
        role = role_repo.get(role_id, db=db)
        if role is None:
            raise ValidationError("role not exists")

        # 4. 开启事务
        try:
            # 5. 删除角色页面权限
            role_page_service.drop_page_permission_by_role_id(role_id, db=db)

            # 6. 删除角色资产权限
            role_asset_service.drop_asset_permission_by_role_id(role_id, db=db)

            # 7. 删除角色
            deleted = role_repo.delete(role_id, db=db)
            if not deleted:
                raise ValidationError("delete role failed")

            # 8. 提交事务
            db.commit()
            return True

        except Exception:
            # 9. 回滚事务
            db.rollback()
            raise
