from typing import List

from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.core.utils.MD5Util import md5_util
from app.domain.user.repository import UserRepository, RoleRepository, PageRepository
from app.domain.asset.repository.AssetRepository import AssetRepository
from app.domain.user.repository.models import User, Role
from app.domain.auth.service.RolePageService import RolePageService
from app.domain.auth.service.RoleAssetService import RoleAssetService
from app.domain.user.schema.AssetPermissionSchema import (
    AssetPermissionInputSchema,
    AssetTypePermissionItem,
    AssetIdPermissionNode,
)
from app.domain.user.service.UserService import UserService


DEFAULT_ROOT_ACCOUNT = "root"
DEFAULT_ROOT_NICKNAME = "根管理员"
DEFAULT_ROOT_ROLE_NAME = "root"
DEFAULT_ROOT_ROLE_DESCRIBE = "root user with all permissions"


def ensure_root_user(db: Session) -> None:
    """
    初始化系统时确保 root 用户存在，并且该用户所属角色拥有所有页面与所有资产权限。
    :param db: 数据库会话
    """
    user_repo = UserRepository()
    role_repo = RoleRepository()
    page_repo = PageRepository()
    asset_repo = AssetRepository()
    role_page_service = RolePageService()
    role_asset_service = RoleAssetService()

    # 1. 如果 root 用户已存在，则无需初始化
    root_user = user_repo.select_one(db, filters={"account": DEFAULT_ROOT_ACCOUNT})
    if root_user is not None:
        return

    # 2. 查找或创建 root 角色
    root_role = role_repo.select_one(db, filters={"name": DEFAULT_ROOT_ROLE_NAME})
    if root_role is None:
        root_role = Role(
            name=DEFAULT_ROOT_ROLE_NAME,
            describe=DEFAULT_ROOT_ROLE_DESCRIBE,
        )
        root_role = role_repo.create(root_role, db=db)
        if root_role is None:
            raise ValidationError("create root role failed")

    role_id = root_role.role_id

    # 3. 为 root 角色分配全部页面权限
    pages = page_repo.select(db)
    page_ids: List[str] = [page.page_id for page in pages if getattr(page, "page_id", None)]
    role_page_service.alter_role_page_permission(role_id, page_ids, db=db)

    # 4. 为 root 角色分配全部资产权限
    assets = asset_repo.select(db)
    asset_types = sorted({asset.asset_type for asset in assets if getattr(asset, "asset_type", None)})
    part_asset_type = [
        AssetTypePermissionItem(type=asset_type, permission="C")
        for asset_type in asset_types
    ]
    part_asset_id = []
    for asset in assets:
        asset_id = getattr(asset, "asset_id", None)
        if not asset_id:
            continue
        asset_type = getattr(asset, "asset_type", "")
        permission = "URD"
        if asset_type in {"terminal", "sensor"}:
            permission = "URDO"
        part_asset_id.append(
            AssetIdPermissionNode(
                asset_id=asset_id,
                permission=permission,
            )
        )
    asset_permission = AssetPermissionInputSchema(
        part_asset_type=part_asset_type,
        part_asset_id=part_asset_id,
    )
    role_asset_service.alter_role_asset_permission(role_id, asset_permission, db=db)

    # 5. 创建 root 用户
    root_password = md5_util.encrypt(UserService.DEFAULT_PASSWORD)
    root_user = User(
        role_id=role_id,
        account=DEFAULT_ROOT_ACCOUNT,
        nickname=DEFAULT_ROOT_NICKNAME,
        password=root_password,
    )
    root_user = user_repo.create(root_user, db=db)
    if root_user is None:
        raise ValidationError("create root user failed")
