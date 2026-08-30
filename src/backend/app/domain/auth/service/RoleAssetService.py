from collections import defaultdict
from typing import List, Dict, Set
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.auth.repository.models import RoleAsset
from app.domain.auth.repository.RoleAssetRepository import RoleAssetRepository
from app.domain.user.schema.AssetPermissionSchema import (
    AssetPermissionSchema,
    AssetTypePermissionItem,
    AssetIdPermissionNode,
    AssetIdPermissionTreeNode,
)
from app.domain.asset.repository.AssetRepository import AssetRepository

# 权限代码 → 布尔字段名 映射
_CODE_TO_FIELD = {
    "C": "perm_create",
    "R": "perm_retrieve",
    "U": "perm_update",
    "D": "perm_delete",
    "O": "perm_operate",
}

# 类型权限（instance）排序
_TYPE_ORDER = ["C"]
# 实例权限（type）排序
_INSTANCE_ORDER = ["R", "U", "D", "O"]


class RoleAssetService:
    """角色的资产权限相关业务逻辑封装"""

    OPERABLE_ASSET_TYPES = {"terminal", "sensor"}

    # ==========================================================
    # 辅助方法
    # ==========================================================

    @staticmethod
    def _codes_to_bool(permission_str: str) -> Dict[str, bool]:
        """ 将 "RUD" 字符串转为布尔字段映射 """
        return {
            "perm_create": "C" in permission_str,
            "perm_retrieve": "R" in permission_str,
            "perm_update": "U" in permission_str,
            "perm_delete": "D" in permission_str,
            "perm_operate": "O" in permission_str,
        }

    @staticmethod
    def _bool_to_codes(record: RoleAsset) -> str:
        """ 从布尔字段拼回 "RUD" 字符串（按固定顺序） """
        codes = []
        if record.perm_create:
            codes.append("C")
        if record.perm_retrieve:
            codes.append("R")
        if record.perm_update:
            codes.append("U")
        if record.perm_delete:
            codes.append("D")
        if record.perm_operate:
            codes.append("O")
        return "".join(codes)

    @staticmethod
    def _sort_permission(permissions: Set[str], order: List[str]) -> str:
        """ 按固定顺序排序权限字符串 """
        result = [p for p in order if p in permissions]
        remain = permissions - set(order)
        if remain:
            result.extend(sorted(remain))
        return "".join(result)

    # ==========================================================
    # 功能性 Service
    # ==========================================================

    def save_role_asset_permission(self, role_id: str, permission_data: AssetPermissionSchema, db: Session) -> int:
        """
        将角色的权限 json 解析成 role_asset 对象，并保存到数据库当中。
        每个资产/类型一行，用布尔字段表示权限。
        """
        if role_id is None or permission_data is None:
            return 0

        if hasattr(permission_data, "model_dump"):
            payload = permission_data.model_dump(exclude_none=True)
        else:
            payload = permission_data
        if not isinstance(payload, dict):
            raise ValidationError("invalid payload")

        role_asset_list: List[RoleAsset] = []

        # 资产类型权限（仅 C，一行一个类型）
        for item in payload.get("part_asset_type", ()):
            asset_type = item.get("type")
            if asset_type:
                role_asset_list.append(RoleAsset(
                    role_id=role_id,
                    asset_type=asset_type,
                    perm_create="C" in item.get("permission", ""),
                ))

        # 资产实例权限（R/U/D/O，一行一个资产）
        for node in payload.get("part_asset_id", ()):
            asset_id = node.get("asset_id")
            if asset_id:
                perms = node.get("permission", "")
                if "O" in perms:
                    asset = AssetRepository().get(asset_id, db=db)
                    if asset is None:
                        raise ValidationError("asset not exists")
                    if asset.asset_type not in self.OPERABLE_ASSET_TYPES:
                        raise ValidationError(
                            "O permission is only valid for terminal or sensor assets"
                        )
                role_asset_list.append(RoleAsset(
                    role_id=role_id,
                    asset_id=asset_id,
                    perm_retrieve="R" in perms,
                    perm_update="U" in perms,
                    perm_delete="D" in perms,
                    perm_operate="O" in perms,
                ))

        if not role_asset_list:
            return 0
        role_asset_repo = RoleAssetRepository()
        result = role_asset_repo.bulk_create(role_asset_list, db=db)
        return len(result)

    def alter_role_asset_permission(self, role_id: str, permission_data: AssetPermissionSchema, db: Session) -> int:
        """ 修改角色资产权限（先删后建） """
        self.drop_asset_permission_by_role_id(role_id, db)
        if permission_data is None:
            return 0
        return self.save_role_asset_permission(role_id, permission_data, db)

    def query_role_asset_permission(self, role_id: str, db: Session) -> AssetPermissionSchema:
        """ 根据角色 ID 查询对应的资产权限 """
        if not role_id:
            raise ValidationError("role_id is required")

        role_asset_repo = RoleAssetRepository()
        records = role_asset_repo.select(db, filters={"role_id": role_id})
        if not records:
            return AssetPermissionSchema(part_asset_type=[], part_asset_id=[])

        # 按类型 / 资产 ID 聚合权限码
        type_permissions: Dict[str, Set[str]] = defaultdict(set)
        asset_permissions: Dict[str, Set[str]] = defaultdict(set)

        for item in records:
            if item.asset_type:
                if item.perm_create:
                    type_permissions[item.asset_type].add("C")
            if item.asset_id:
                if item.perm_retrieve:
                    asset_permissions[item.asset_id].add("R")
                if item.perm_update:
                    asset_permissions[item.asset_id].add("U")
                if item.perm_delete:
                    asset_permissions[item.asset_id].add("D")
                if item.perm_operate:
                    asset_permissions[item.asset_id].add("O")

        # 构建类型权限
        part_asset_type = [
            AssetTypePermissionItem(
                type=asset_type,
                permission=self._sort_permission(perms, _TYPE_ORDER),
            )
            for asset_type, perms in type_permissions.items()
        ]

        if not asset_permissions:
            return AssetPermissionSchema(
                part_asset_type=part_asset_type,
                part_asset_id=[],
            )

        # 查询资产信息用于构建树
        asset_repo = AssetRepository()
        assets = asset_repo.select(filters={"asset_id__in": list(asset_permissions.keys())}, db=db)

        parent_map: Dict[str, str | None] = {}
        name_map: Dict[str, str] = {}
        for asset in assets:
            parent_map[asset.asset_id] = asset.asset_id_parent
            name_map[asset.asset_id] = asset.name

        # 创建节点
        nodes: Dict[str, AssetIdPermissionTreeNode] = {}
        for asset_id, perms in asset_permissions.items():
            nodes[asset_id] = AssetIdPermissionTreeNode(
                asset_id=asset_id,
                name=name_map.get(asset_id, ""),
                permission=self._sort_permission(perms, _INSTANCE_ORDER),
                sub_assets=None,
            )

        # 构建树结构
        roots: List[AssetIdPermissionTreeNode] = []
        for asset_id, node in nodes.items():
            parent_id = parent_map.get(asset_id)
            if parent_id and parent_id in nodes:
                parent_node = nodes[parent_id]
                if parent_node.sub_assets is None:
                    parent_node.sub_assets = []
                parent_node.sub_assets.append(node)
            else:
                roots.append(node)

        return AssetPermissionSchema(
            part_asset_type=part_asset_type,
            part_asset_id=roots,
        )

    @staticmethod
    def drop_asset_permission_by_role_id(role_id: str, db: Session) -> int:
        """ 根据角色 ID 删除对应的资产权限 """
        if not role_id:
            return 0
        role_asset_repo = RoleAssetRepository()
        return role_asset_repo.bulk_delete("role_id", [role_id], db)

    @staticmethod
    def drop_asset_permission_by_asset_id(asset_id: str, db: Session) -> int:
        """ 根据资产 ID 删除对应的资产权限 """
        if not asset_id:
            return 0
        role_asset_repo = RoleAssetRepository()
        return role_asset_repo.bulk_delete("asset_id", [asset_id], db)

    @staticmethod
    def drop_asset_permission_by_asset_ids(asset_ids: List[str], db: Session) -> int:
        """ 根据资产 ID 列表批量删除资产权限（级联删除时调用） """
        if not asset_ids:
            return 0
        role_asset_repo = RoleAssetRepository()
        return role_asset_repo.bulk_delete("asset_id", asset_ids, db)

    @staticmethod
    def remove_role_r_permission(role_id: str, removed_r_asset_ids: List[str], db: Session) -> int:
        """
        当角色 R 权限被移除时，级联清理该角色下所有用户在 user_asset 中的 U/D/O 权限。
        :param role_id: 角色 ID
        :param removed_r_asset_ids: 被移除 R 权限的资产 ID 列表
        :param db: 数据库会话
        :return: 删除的用户权限记录数
        """
        if not role_id or not removed_r_asset_ids:
            return 0

        from app.domain.user.repository.UserRepository import UserRepository
        from app.domain.auth.repository.UserAssetRepository import UserAssetRepository

        # 1. 查出该角色下所有用户
        user_repo = UserRepository()
        users = user_repo.select(db, filters={"role_id": role_id})
        if not users:
            return 0

        # 2. 对每个用户，查询其对受影响资产的权限，移除非 R 权限
        user_asset_repo = UserAssetRepository()
        total_deleted = 0
        for user in users:
            for asset_id in removed_r_asset_ids:
                record = user_asset_repo.select_one(
                    db,
                    filters={"user_id": user.user_id, "asset_id": asset_id},
                )
                if not record:
                    continue

                # 移除 U/D/O，保留 R（如果有的话）
                # 实际上角色 R 被移除了，用户的 R 来自角色，用户自身可能没 R
                # 所以检查用户自己的 R 是否还在
                if not record.perm_retrieve:
                    # 用户自己没有独立 R，全部删除
                    user_asset_repo.delete(record.user_asset_id, db=db)
                    total_deleted += 1
                elif not record.perm_update and not record.perm_delete and not record.perm_operate:
                    # 只有 R 没有其他，记录保留
                    pass
                else:
                    # 有 R 但需要清掉 U/D/O
                    user_asset_repo.update(
                        record.user_asset_id,
                        {"perm_update": False, "perm_delete": False, "perm_operate": False},
                        db=db,
                    )
                    total_deleted += 1

            # 刷新用户 Redis
            if total_deleted > 0:
                from app.domain.user.service.UserService import UserService
                UserService.refresh_user_cache(user.user_id, db)

        return total_deleted
