from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.auth.repository.UserAssetRepository import UserAssetRepository
from app.domain.auth.repository.models.UserAsset import UserAsset
from app.domain.asset.repository.AssetRepository import AssetRepository
from app.domain.user.service.UserService import UserService


class UserAssetService:
    """用户资产实例权限管理"""

    OPERABLE_ASSET_TYPES = {"terminal", "sensor"}

    @classmethod
    def _validate_operate_permission(
        cls, asset_id: str, perm_operate: bool, db: Session
    ) -> None:
        if not perm_operate:
            return
        asset = AssetRepository().get(asset_id, db=db)
        if asset is None:
            raise ValidationError("asset not exists")
        if asset.asset_type not in cls.OPERABLE_ASSET_TYPES:
            raise ValidationError(
                "O permission is only valid for terminal or sensor assets"
            )

    @staticmethod
    def grant_user_asset_permission(
        user_id: str,
        asset_id: str,
        perms: Dict[str, bool],
        db: Session,
    ) -> Dict[str, Any]:
        """
        管理员为用户授予/修改资产实例权限。
        如果用户对该资产已有权限记录则更新，否则新建。
        """
        if not user_id or not asset_id:
            raise ValidationError("user_id and asset_id are required")

        UserAssetService._validate_operate_permission(
            asset_id, perms.get("perm_operate", False), db
        )

        repo = UserAssetRepository()

        # 查找已有记录
        existing = repo.select_one(
            db,
            filters={"user_id": user_id, "asset_id": asset_id},
        )

        if existing:
            # 更新已有记录
            values = {
                "perm_retrieve": perms.get("perm_retrieve", existing.perm_retrieve),
                "perm_update": perms.get("perm_update", existing.perm_update),
                "perm_delete": perms.get("perm_delete", existing.perm_delete),
                "perm_operate": perms.get("perm_operate", existing.perm_operate),
            }
            result = repo.update(existing.user_asset_id, values, db=db)
        else:
            # 新建记录
            record = UserAsset(
                user_id=user_id,
                asset_id=asset_id,
                perm_retrieve=perms.get("perm_retrieve", False),
                perm_update=perms.get("perm_update", False),
                perm_delete=perms.get("perm_delete", False),
                perm_operate=perms.get("perm_operate", False),
            )
            result = repo.create(record, db=db)

        # 刷新 Redis
        UserService.refresh_user_cache(user_id, db)

        return {
            "user_asset_id": result.user_asset_id,
            "user_id": result.user_id,
            "asset_id": result.asset_id,
            "perm_retrieve": result.perm_retrieve,
            "perm_update": result.perm_update,
            "perm_delete": result.perm_delete,
            "perm_operate": result.perm_operate,
        }

    @staticmethod
    def revoke_user_asset_permission(user_id: str, asset_id: str, db: Session) -> bool:
        """
        移除用户对某资产的全部权限。
        """
        if not user_id or not asset_id:
            raise ValidationError("user_id and asset_id are required")

        repo = UserAssetRepository()
        record = repo.select_one(
            db,
            filters={"user_id": user_id, "asset_id": asset_id},
        )
        if not record:
            return False

        deleted = repo.delete(record.user_asset_id, db=db)
        if deleted:
            UserService.refresh_user_cache(user_id, db)
        return deleted

    @staticmethod
    def query_user_asset_permissions(user_id: str, db: Session) -> List[Dict[str, Any]]:
        """
        查询用户的所有资产实例权限。
        """
        if not user_id:
            return []

        repo = UserAssetRepository()
        records = repo.select(db, filters={"user_id": user_id})

        return [
            {
                "user_asset_id": r.user_asset_id,
                "user_id": r.user_id,
                "asset_id": r.asset_id,
                "perm_retrieve": r.perm_retrieve,
                "perm_update": r.perm_update,
                "perm_delete": r.perm_delete,
                "perm_operate": r.perm_operate,
            }
            for r in (records or [])
        ]

    @staticmethod
    def grant_creator_permissions(
        user_id: str,
        asset_id: str,
        asset_type: str,
        db: Session,
    ) -> None:
        """
        用户创建资产后，自动授予该用户对新建资产的全部操作权限。
        building/floor/room → R+U+D
        terminal/sensor → R+U+D+O
        """
        if not user_id or not asset_id:
            return

        can_operate = asset_type in UserAssetService.OPERABLE_ASSET_TYPES
        repo = UserAssetRepository()

        record = UserAsset(
            user_id=user_id,
            asset_id=asset_id,
            perm_retrieve=True,
            perm_update=True,
            perm_delete=True,
            perm_operate=can_operate,
        )
        repo.create(record, db=db)

        # 刷新 Redis
        UserService.refresh_user_cache(user_id, db)

    @staticmethod
    def drop_user_assets_by_asset_ids(asset_ids: List[str], db: Session) -> int:
        """
        按资产 ID 列表批量删除用户权限（级联删除资产时调用）。
        """
        if not asset_ids:
            return 0
        repo = UserAssetRepository()
        return repo.bulk_delete("asset_id", asset_ids, db)
