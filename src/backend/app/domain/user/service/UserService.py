from typing import List, Dict, Optional, Any
import json
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.infra.Redis import redis_manager
from app.core.utils.MD5Util import md5_util
from app.core.utils.JWTUtil import jwt_util
from app.domain.user.repository import *
from app.domain.user.repository.models.User import User
from app.domain.user.schema.UserSchema import UserLoginSchema, UserAddSchema, UserUpdateSchema, UserQueryFilterSchema
from app.domain.auth.repository.UserAssetRepository import UserAssetRepository


class UserService:
    """账号相关业务逻辑封装"""

    DEFAULT_PASSWORD = "123456"
    DEFAULT_PASSWORD_SALT = "sues7719"
    REDIS_LOGIN_PREFIX = "auth:login:"
    REDIS_LOGIN_USER_PREFIX = "auth:login:user:"
    REDIS_ROLE_PREFIX = "auth:role:"
    REDIS_USER_PREFIX = "auth:user:"

    # ==========================================================
    # API相关Service
    # ==========================================================

    @staticmethod
    def login_user(login_data: UserLoginSchema, db: Session) -> Dict[str, Any]:
        """
        用户登录。
        将角色权限写入共享 Redis Key，用户权限写入个人 Redis Key。
        """
        # 1. schema 转 dict
        if hasattr(login_data, "model_dump"):
            payload = login_data.model_dump(exclude_none=True)
        else:
            payload = login_data
        if not isinstance(payload, dict):
            raise ValidationError("invalid payload")

        account = payload.get("account")
        password = payload.get("password")
        if not account:
            raise ValidationError("account is required")
        if not password:
            raise ValidationError("password is required")

        # 2. Repository
        user_repo = UserRepository()

        # 3. 验证账号存在
        users = user_repo.select(db, filters={"account": account})
        user = users[0] if users else None
        if user is None:
            raise ValidationError("user not exists")

        # 4. 验证密码正确
        if not md5_util.verify(password, user.password):
            raise ValidationError("password error")

        # 5. 如果当前用户已有未过期登录 token，则尝试复用
        existing_token = redis_manager.get(f"{UserService.REDIS_LOGIN_USER_PREFIX}{user.user_id}")
        if existing_token:
            if isinstance(existing_token, bytes):
                existing_token = existing_token.decode("utf-8")
            if existing_token:
                existing_login_cache_raw = redis_manager.get(f"{UserService.REDIS_LOGIN_PREFIX}{existing_token}")
                if existing_login_cache_raw:
                    if isinstance(existing_login_cache_raw, bytes):
                        existing_login_cache_raw = existing_login_cache_raw.decode("utf-8")
                    try:
                        existing_login_cache = json.loads(existing_login_cache_raw)
                    except Exception:
                        existing_login_cache = None
                    if isinstance(existing_login_cache, dict):
                        redis_manager.expire(
                            f"{UserService.REDIS_LOGIN_PREFIX}{existing_token}",
                            jwt_util.DEFAULT_EXPIRE_SECONDS,
                        )
                        redis_manager.expire(
                            f"{UserService.REDIS_LOGIN_USER_PREFIX}{user.user_id}",
                            jwt_util.DEFAULT_EXPIRE_SECONDS,
                        )
                        # 获取角色页面权限用于前端
                        page_codes = UserService._get_role_page_codes(user.role_id)
                        return {
                            "token": existing_token,
                            "token_type": "Bearer",
                            "expires_in": jwt_util.DEFAULT_EXPIRE_SECONDS,
                            "user_id": user.user_id,
                            "role_id": user.role_id,
                            "account": user.account,
                            "nickname": user.nickname,
                            "page_codes": page_codes,
                        }

        # 6. 生成JWT
        token_payload = {
            "user_id": user.user_id,
            "account": user.account,
            "role_id": user.role_id,
        }
        token = jwt_util.encode(token_payload)

        # 7. 将角色权限写入共享 Redis（首次登录或缓存过期时）
        UserService._ensure_role_cache(user.role_id, db)

        # 8. 将用户级权限写入 Redis
        UserService._ensure_user_cache(user.user_id, db)

        # 9. 写入登录会话（精简，不含权限详情）
        login_cache = {
            "user_id": user.user_id,
            "account": user.account,
            "nickname": user.nickname,
            "role_id": user.role_id,
        }
        redis_manager.set(
            f"{UserService.REDIS_LOGIN_PREFIX}{token}",
            json.dumps(login_cache, ensure_ascii=False),
            ex=jwt_util.DEFAULT_EXPIRE_SECONDS,
        )
        redis_manager.set(
            f"{UserService.REDIS_LOGIN_USER_PREFIX}{user.user_id}",
            token,
            ex=jwt_util.DEFAULT_EXPIRE_SECONDS,
        )

        # 10. 返回JWT
        page_codes = UserService._get_role_page_codes(user.role_id)
        return {
            "token": token,
            "token_type": "Bearer",
            "expires_in": jwt_util.DEFAULT_EXPIRE_SECONDS,
            "user_id": user.user_id,
            "role_id": user.role_id,
            "account": user.account,
            "nickname": user.nickname,
            "page_codes": page_codes,
        }

    @staticmethod
    def logout_user(token: str) -> bool:
        """
        用户退出登录，清理登录会话及用户级权限缓存。
        """
        if not token:
            raise ValidationError("token is required")

        if token.startswith("Bearer "):
            token = token.removeprefix("Bearer ").strip()

        login_cache_raw = redis_manager.get(f"{UserService.REDIS_LOGIN_PREFIX}{token}")
        user_id = None
        if login_cache_raw:
            if isinstance(login_cache_raw, bytes):
                login_cache_raw = login_cache_raw.decode("utf-8")
            try:
                login_cache = json.loads(login_cache_raw)
            except Exception:
                login_cache = None
            if isinstance(login_cache, dict):
                user_id = login_cache.get("user_id")

        deleted = redis_manager.delete(f"{UserService.REDIS_LOGIN_PREFIX}{token}")
        if user_id:
            deleted += redis_manager.delete(f"{UserService.REDIS_LOGIN_USER_PREFIX}{user_id}")
            # 清理用户级权限缓存（角色权限是共享的，不清理）
            redis_manager.delete(f"{UserService.REDIS_USER_PREFIX}{user_id}:asset_perms")
        return deleted > 0

    # ==========================================================
    # 权限缓存管理
    # ==========================================================

    @staticmethod
    def _ensure_role_cache(role_id: str, db: Session) -> None:
        """
        确保角色权限已写入共享 Redis Key。
        检查 `auth:role:{role_id}:name` 是否存在，不存在则从 DB 全量加载。
        root 角色仅写 name + pages，跳过资产权限（鉴权时硬编码跳过）。
        """
        if not role_id:
            return

        name_key = f"{UserService.REDIS_ROLE_PREFIX}{role_id}:name"
        if redis_manager.exists(name_key):
            return

        from app.domain.user.service.RoleService import RoleService
        role_info = RoleService.query_role_by_id(role_id, db=db)
        if not role_info:
            return

        role_name = role_info.get("name", "")

        # 角色名（用于 root 判断）
        redis_manager.set(name_key, role_name, ex=jwt_util.DEFAULT_EXPIRE_SECONDS * 7)

        # 角色页面权限 → Set
        pages_key = f"{UserService.REDIS_ROLE_PREFIX}{role_id}:pages"
        page_codes = role_info.get("page_codes") or []
        redis_manager.client.delete(pages_key)
        if page_codes:
            redis_manager.client.sadd(pages_key, *page_codes)
        redis_manager.expire(pages_key, jwt_util.DEFAULT_EXPIRE_SECONDS * 7)

        # root 角色无需缓存资产权限（鉴权硬编码跳过），节省 Redis 内存
        if role_name == "root":
            return

        # 角色资产实例权限 → Hash
        asset_perms_key = f"{UserService.REDIS_ROLE_PREFIX}{role_id}:asset_perms"
        asset_permission = role_info.get("asset_permission") or {}
        if isinstance(asset_permission, dict):
            part_asset_id = asset_permission.get("part_asset_id") or []
            flat = {}
            stack = list(part_asset_id)
            while stack:
                node = stack.pop()
                aid = node.get("asset_id")
                if aid:
                    flat[aid] = node.get("permission", "")
                children = node.get("sub_assets") or []
                stack.extend(children)
            redis_manager.client.delete(asset_perms_key)
            if flat:
                redis_manager.client.hset(asset_perms_key, mapping=flat)
            redis_manager.expire(asset_perms_key, jwt_util.DEFAULT_EXPIRE_SECONDS * 7)

        # 角色资产类型 C 权限 → Set
        type_perms_key = f"{UserService.REDIS_ROLE_PREFIX}{role_id}:type_perms"
        part_asset_type = asset_permission.get("part_asset_type") if isinstance(asset_permission, dict) else []
        redis_manager.client.delete(type_perms_key)
        for item in (part_asset_type or []):
            atype = item.get("type") if isinstance(item, dict) else item.type
            perm = item.get("permission") if isinstance(item, dict) else item.permission
            if atype and "C" in (perm or ""):
                redis_manager.client.sadd(type_perms_key, atype)
        redis_manager.expire(type_perms_key, jwt_util.DEFAULT_EXPIRE_SECONDS * 7)

    @staticmethod
    def _ensure_user_cache(user_id: str, db: Session) -> None:
        """
        将用户级资产权限写入 Redis Hash `auth:user:{user_id}:asset_perms`。
        """
        if not user_id:
            return

        user_asset_repo = UserAssetRepository()
        records = user_asset_repo.select(db, filters={"user_id": user_id})

        perms_key = f"{UserService.REDIS_USER_PREFIX}{user_id}:asset_perms"
        redis_manager.client.delete(perms_key)

        if not records:
            return

        mapping = {}
        for r in records:
            codes = []
            if r.perm_retrieve:
                codes.append("R")
            if r.perm_update:
                codes.append("U")
            if r.perm_delete:
                codes.append("D")
            if r.perm_operate:
                codes.append("O")
            if codes:
                mapping[r.asset_id] = "".join(codes)

        if mapping:
            redis_manager.client.hset(perms_key, mapping=mapping)
        redis_manager.expire(perms_key, jwt_util.DEFAULT_EXPIRE_SECONDS * 7)

    @staticmethod
    def _get_role_page_codes(role_id: str) -> List[str]:
        """ 从 Redis 读取角色页面权限 """
        if not role_id:
            return []
        pages_key = f"{UserService.REDIS_ROLE_PREFIX}{role_id}:pages"
        members = redis_manager.client.smembers(pages_key)
        return sorted([m.decode("utf-8") if isinstance(m, bytes) else m for m in (members or [])])

    # ==========================================================
    # 缓存刷新（供外部调用）
    # ==========================================================

    @staticmethod
    def refresh_role_cache(role_id: str, db: Session) -> int:
        """
        角色权限变更后，刷新共享 Redis Key。
        直接删除旧缓存，下次登录或请求时会重新加载。
        :return: 1 成功，0 失败
        """
        if not role_id:
            return 0

        # 删除旧的共享缓存 Key
        redis_manager.delete(
            f"{UserService.REDIS_ROLE_PREFIX}{role_id}:name",
            f"{UserService.REDIS_ROLE_PREFIX}{role_id}:pages",
            f"{UserService.REDIS_ROLE_PREFIX}{role_id}:asset_perms",
            f"{UserService.REDIS_ROLE_PREFIX}{role_id}:type_perms",
        )
        # 立即重建
        UserService._ensure_role_cache(role_id, db)
        return 1

    @staticmethod
    def refresh_user_cache(user_id: str, db: Session) -> int:
        """
        刷新用户级权限 Redis 缓存。
        :return: 1 成功，0 失败
        """
        if not user_id:
            return 0

        redis_manager.delete(f"{UserService.REDIS_USER_PREFIX}{user_id}:asset_perms")
        UserService._ensure_user_cache(user_id, db)
        return 1

    # ==========================================================
    # 账号CRUD
    # ==========================================================

    @staticmethod
    def query_users_form(db: Session, page: int = 1, limit: int = 20, filters: UserQueryFilterSchema | None = None) -> Dict[str, Any]:
        """ 分页查询账号信息 """
        user_repo = UserRepository()
        role_repo = RoleRepository()

        repo_filters: Dict[str, Any] = {}
        if filters is not None:
            if hasattr(filters, "model_dump"):
                payload = filters.model_dump(exclude_none=True)
            elif isinstance(filters, dict):
                payload = filters
            else:
                payload = {}

            if payload.get("account"):
                repo_filters["account__ilike"] = payload.get("account")
            if payload.get("role_id"):
                repo_filters["role_id"] = payload.get("role_id")

        total = user_repo.select(db, filters=repo_filters, count_only=True)
        users = user_repo.select(db, filters=repo_filters, page=page, page_size=limit)

        items: List[Dict[str, Any]] = []
        for user in users:
            role_name = ""
            role = role_repo.get(user.role_id, db=db)
            if role is not None:
                role_name = role.name
            items.append({
                "user_id": user.user_id,
                "account": user.account,
                "nickname": user.nickname,
                "role_name": role_name,
            })
        return {"items": items, "total": total}

    @staticmethod
    def find_user_by_id(user_id: str, db: Session) -> Dict[str, Any]:
        """ 查询单个账号详情（含角色名和资产权限） """
        user_repo = UserRepository()
        role_repo = RoleRepository()

        user = user_repo.get(user_id, db=db)
        if user is None:
            raise ValidationError("user not exists")

        role = role_repo.get(user.role_id, db=db)
        role_name = role.name if role else ""

        from app.domain.auth.service.UserAssetService import UserAssetService
        asset_perms = UserAssetService.query_user_asset_permissions(user_id, db=db)

        return {
            "user_id": user.user_id,
            "account": user.account,
            "nickname": user.nickname,
            "role_id": user.role_id,
            "role_name": role_name,
            "asset_permissions": asset_perms,
        }

    @staticmethod
    def get_my_profile(authorization: str, db: Session) -> Dict[str, Any]:
        """ 获取当前登录用户的个人页面信息（用户信息 + 角色 + 权限 + 资产树） """
        from app.domain.common.PermissionChecker import (
            get_user_id_from_token,
            get_role_id_from_token,
            get_viewable_asset_ids,
            get_effective_asset_perm,
        )
        from app.domain.asset.service.AssetService import AssetService
        from app.infra.Redis import redis_manager

        user_id = get_user_id_from_token(authorization)
        role_id = get_role_id_from_token(authorization)

        user_repo = UserRepository()
        role_repo = RoleRepository()

        user = user_repo.get(user_id, db=db)
        if user is None:
            raise ValidationError("user not exists")

        role = role_repo.get(user.role_id, db=db)
        role_name = role.name if role else ""

        # 1. 可创建的资产类型（C 权限）
        if role_name == "root":
            create_types = ["building", "floor", "room", "terminal", "sensor"]
        else:
            type_key = f"auth:role:{role_id}:type_perms"
            members = redis_manager.client.smembers(type_key) if role_id else set()
            create_types = sorted([
                m.decode("utf-8") if isinstance(m, bytes) else m
                for m in (members or [])
            ])

        # 2. 构建带权限标记的资产实例树
        raw_tree = AssetService.query_assets_tree(db)
        viewable = get_viewable_asset_ids(authorization, db)

        def _annotate_tree(nodes: list) -> list:
            result = []
            for node in nodes:
                aid = node.get("asset_id")
                children = node.get("sub_assets") or []

                pruned_children = _annotate_tree(children)

                if viewable is not None and aid not in viewable and not pruned_children:
                    continue

                perm = get_effective_asset_perm(authorization, aid, db)

                node_copy = {"asset_id": aid, "name": node.get("name"), "permission": perm}
                if pruned_children:
                    node_copy["sub_assets"] = pruned_children
                result.append(node_copy)
            return result

        asset_tree = _annotate_tree(raw_tree)

        return {
            "user_id": user.user_id,
            "account": user.account,
            "nickname": user.nickname,
            "role_name": role_name,
            "create_types": create_types,
            "asset_tree": asset_tree,
        }

    @staticmethod
    def save_new_user(user_data: UserAddSchema, db: Session) -> Dict[str, Any]:
        """ 创建账号 """
        if hasattr(user_data, "model_dump"):
            payload = user_data.model_dump(exclude_none=True)
        else:
            payload = user_data
        if not isinstance(payload, dict):
            raise ValidationError("invalid payload")

        user_repo = UserRepository()
        role_repo = RoleRepository()

        role = role_repo.get(payload.get("role_id"), db=db)
        if role is None:
            raise ValidationError("role not exists")

        try:
            user = User(
                role_id=payload.get("role_id"),
                account=payload.get("account"),
                nickname=payload.get("nickname"),
                password=md5_util.encrypt(payload.get("password")),
            )
            user = user_repo.create(user, db=db)
            if user is None:
                raise ValidationError("create user failed")

            db.commit()
            db.refresh(user)

            return {
                "user_id": user.user_id,
                "role_id": user.role_id,
                "account": user.account,
                "nickname": user.nickname,
            }
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def alter_user_by_id(user_id: str, user_data: UserUpdateSchema, db: Session) -> Dict[str, Any]:
        """ 修改账号（含资产权限全量替换） """
        if hasattr(user_data, "model_dump"):
            payload = user_data.model_dump(exclude_none=True)
        else:
            payload = user_data
        if not isinstance(payload, dict):
            raise ValidationError("invalid payload")

        user_repo = UserRepository()
        role_repo = RoleRepository()

        user = user_repo.get(user_id, db=db)
        if user is None:
            raise ValidationError("user not exists")

        if "role_id" in payload:
            role = role_repo.get(payload.get("role_id"), db=db)
            if role is None:
                raise ValidationError("role not exists")

        if "password" in payload:
            payload["password"] = md5_util.encrypt(payload.get("password"))

        # 提取 asset_permissions，不传给 user_repo.update
        asset_permissions = payload.pop("asset_permissions", None)

        try:
            user = user_repo.update(user_id, payload, db=db)
            if user is None:
                raise ValidationError("update user failed")

            # 全量替换用户资产权限
            if asset_permissions is not None:
                from app.domain.auth.service.UserAssetService import UserAssetService
                from app.domain.auth.repository.UserAssetRepository import UserAssetRepository
                ua_repo = UserAssetRepository()
                existing = ua_repo.select(db, filters={"user_id": user_id})
                for rec in (existing or []):
                    ua_repo.delete(rec.user_asset_id, db=db)

                for perm in asset_permissions:
                    perm_dict = perm if isinstance(perm, dict) else perm.model_dump()
                    UserAssetService.grant_user_asset_permission(
                        user_id,
                        perm_dict.get("asset_id"),
                        {
                            "perm_retrieve": perm_dict.get("perm_retrieve", False),
                            "perm_update": perm_dict.get("perm_update", False),
                            "perm_delete": perm_dict.get("perm_delete", False),
                            "perm_operate": perm_dict.get("perm_operate", False),
                        },
                        db=db,
                    )

            db.commit()
            db.refresh(user)

            return {
                "user_id": user.user_id,
                "role_id": user.role_id,
                "account": user.account,
                "nickname": user.nickname,
            }
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def reset_user_pwd_by_id(user_id: str, db: Session) -> bool:
        """ 重置账号密码 """
        user_repo = UserRepository()

        user = user_repo.get(user_id, db=db)
        if user is None:
            raise ValidationError("user not exists")

        try:
            user = user_repo.update(
                user_id,
                {"password": md5_util.encrypt(UserService.DEFAULT_PASSWORD)},
                db=db,
            )
            if user is None:
                raise ValidationError("reset user password failed")
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def drop_user_by_id(user_id: str, db: Session):
        """ 删除账号 """
        user_repo = UserRepository()

        user = user_repo.get(user_id, db=db)
        if user is None:
            raise ValidationError("user not exists")

        try:
            deleted = user_repo.delete(user_id, db=db)
            if not deleted:
                raise ValidationError("delete user failed")
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
