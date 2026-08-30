#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/07/23
# @function : 域级权限校验（重构版：角色+用户 Union，Redis Hash/Set 结构）
# @version  : v2.0

import json
from typing import Any, Dict, List, Set

from app.common.validators import ValidationError
from app.infra.Redis import redis_manager

DEFAULT_REDIS_LOGIN_PREFIX = "auth:login:"
DEFAULT_REDIS_ROLE_PREFIX = "auth:role:"
DEFAULT_REDIS_USER_PREFIX = "auth:user:"


def _normalize_token(token: str) -> str:
    """
    规范化 token
    """
    if not token:
        raise ValidationError("token is required")

    token = token.strip()
    if token.startswith("Bearer "):
        token = token.removeprefix("Bearer ").strip()

    if not token:
        raise ValidationError("token is required")

    return token


def _get_login_cache(token: str) -> Dict[str, Any]:
    """
    从 Redis 读取登录会话缓存。
    """
    token = _normalize_token(token)
    login_cache_raw = redis_manager.get(f"{DEFAULT_REDIS_LOGIN_PREFIX}{token}")
    if not login_cache_raw:
        raise ValidationError("unauthorized")
    if isinstance(login_cache_raw, bytes):
        login_cache_raw = login_cache_raw.decode("utf-8")

    try:
        login_cache = json.loads(login_cache_raw)
    except Exception:
        raise ValidationError("unauthorized")
    if not isinstance(login_cache, dict):
        raise ValidationError("unauthorized")

    return login_cache


def get_user_id_from_token(token: str) -> str:
    """
    从 Redis session 中提取 user_id。
    """
    login_cache = _get_login_cache(token)
    user_id = login_cache.get("user_id")
    if not user_id:
        raise ValidationError("invalid session")
    return user_id


def get_role_id_from_token(token: str) -> str | None:
    """
    从 Redis session 中提取 role_id。
    """
    login_cache = _get_login_cache(token)
    return login_cache.get("role_id")


# ==========================================================
# 页面权限校验
# ==========================================================

def check_page_permission(token: str, required_pages: List[str]) -> bool:
    """
    判断 token 对应用户是否拥有指定页面权限（角色级）。
    从 Redis Set `auth:role:{role_id}:pages` 读取。
    """
    login_cache = _get_login_cache(token)
    role_id = login_cache.get("role_id")

    # root 角色全权限
    if role_id and _is_root_role(role_id):
        return True

    # 规范化 required_pages
    required_list: List[str] = [code for code in required_pages if code]
    if not required_list:
        raise ValidationError("required_pages is required")

    # 从 Redis Set 读取角色页面权限
    role_pages = redis_manager.client.smembers(f"{DEFAULT_REDIS_ROLE_PREFIX}{role_id}:pages") if role_id else set()
    if isinstance(role_pages, set):
        page_codes = role_pages
    else:
        page_codes = set()

    return any(code in page_codes for code in required_list)


# ==========================================================
# 资产类型 C 权限校验
# ==========================================================

def check_asset_type_permission(token: str, asset_type: str) -> bool:
    """
    检查用户是否拥有某资产类型的 C 权限（仅角色级）。
    从 Redis Set `auth:role:{role_id}:type_perms` 读取。
    """
    login_cache = _get_login_cache(token)
    role_id = login_cache.get("role_id")

    # root 角色全权限
    if role_id and _is_root_role(role_id):
        return True

    if not role_id:
        return False

    return redis_manager.client.sismember(
        f"{DEFAULT_REDIS_ROLE_PREFIX}{role_id}:type_perms",
        asset_type,
    )


# ==========================================================
# 资产实例权限校验
# ==========================================================

def _is_root_role(role_id: str) -> bool:
    """ 检查角色是否为 root（通过角色名判断） """
    role_name_key = f"{DEFAULT_REDIS_ROLE_PREFIX}{role_id}:name"
    name = redis_manager.get(role_name_key)
    if isinstance(name, bytes):
        name = name.decode("utf-8")
    return name == "root"


def _get_role_asset_perms(role_id: str) -> Dict[str, str]:
    """ 从 Redis Hash 读取角色资产实例权限 """
    if not role_id:
        return {}
    raw = redis_manager.client.hgetall(f"{DEFAULT_REDIS_ROLE_PREFIX}{role_id}:asset_perms")
    if not raw:
        return {}
    result: Dict[str, str] = {}
    for k, v in raw.items():
        key = k.decode("utf-8") if isinstance(k, bytes) else k
        val = v.decode("utf-8") if isinstance(v, bytes) else v
        result[key] = val
    return result


def _get_user_asset_perms(user_id: str) -> Dict[str, str]:
    """ 从 Redis Hash 读取用户资产实例权限 """
    if not user_id:
        return {}
    raw = redis_manager.client.hgetall(f"{DEFAULT_REDIS_USER_PREFIX}{user_id}:asset_perms")
    if not raw:
        return {}
    result: Dict[str, str] = {}
    for k, v in raw.items():
        key = k.decode("utf-8") if isinstance(k, bytes) else k
        val = v.decode("utf-8") if isinstance(v, bytes) else v
        result[key] = val
    return result


def _get_union_asset_perms(token: str) -> Dict[str, str]:
    """
    计算用户对资产的最终权限：角色权限 ∪ 用户权限。
    返回 {asset_id: permission_string}。
    """
    login_cache = _get_login_cache(token)
    role_id = login_cache.get("role_id")
    user_id = login_cache.get("user_id")

    role_perms = _get_role_asset_perms(role_id) if role_id else {}
    user_perms = _get_user_asset_perms(user_id) if user_id else {}

    # Union: 同一资产上合并角色权限与用户权限
    merged = dict(role_perms)
    permission_order = "RUDO"
    for asset_id, user_permission in user_perms.items():
        combined = set(merged.get(asset_id, "")) | set(user_permission)
        merged[asset_id] = "".join(
            code for code in permission_order if code in combined
        )
    return merged


def _build_viewable_set(
    union_perms: Dict[str, str],
    db,
    user_id: str,
) -> Set[str]:
    """
    构建用户可查看的资产 ID 集合：
    - 角色 R 资产 + 用户 R 资产
    - 所有 R 资产的祖先（R 向上穿透）
    """
    from app.domain.asset.repository.AssetRepository import AssetRepository

    r_ids = {aid for aid, perm in union_perms.items() if "R" in perm}
    if not r_ids:
        return set()

    asset_repo = AssetRepository()
    viewable: Set[str] = set(r_ids)
    for aid in list(r_ids):
        asset = asset_repo.get(aid, db)
        if asset and asset.asset_path:
            viewable.update(asset.asset_path.split("/"))

    return viewable


def check_asset_instance_permission(
    token: str,
    asset_id: str,
    code: str,
    db,
) -> bool:
    """
    检查用户是否拥有某资产实例的 R/U/D/O 权限。

    - R: 检查向上穿透后的可见集合
    - U/D/O: 先验证 R，再验证具体权限码
    - D: 仅检查根节点 D 权限（级联删除由业务层负责）
    - root 角色全权限
    """
    login_cache = _get_login_cache(token)
    role_id = login_cache.get("role_id")

    # root 角色全权限
    if role_id and _is_root_role(role_id):
        return True

    union_perms = _get_union_asset_perms(token)
    viewable = _build_viewable_set(union_perms, db, login_cache.get("user_id"))

    # 检查 R 权限
    if code == "R":
        return asset_id in viewable

    # 检查 U / D / O 权限（需要先有 R）
    if code in ("U", "D", "O"):
        if asset_id not in viewable:
            return False
        return code in union_perms.get(asset_id, "")

    return False


def get_viewable_asset_ids(token: str, db) -> Set[str] | None:
    """
    获取用户可查看的资产 ID 集合（角色R ∪ 用户R + 祖先穿透）。
    返回 None 表示 root（不限制），返回空集合表示无任何查看权限。
    """
    login_cache = _get_login_cache(token)
    role_id = login_cache.get("role_id")

    # root 角色全权限
    if role_id and _is_root_role(role_id):
        return None

    union_perms = _get_union_asset_perms(token)
    return _build_viewable_set(union_perms, db, login_cache.get("user_id"))


def get_effective_asset_perm(token: str, asset_id: str, db) -> str:
    """
    返回用户对某资产的最终权限字符串（角色∪用户）。
    用于前端展示当前用户对资产的权限按钮状态。
    """
    login_cache = _get_login_cache(token)
    role_id = login_cache.get("role_id")

    # root 全权限
    if role_id and _is_root_role(role_id):
        from app.domain.asset.repository.AssetRepository import AssetRepository
        asset_repo = AssetRepository()
        asset = asset_repo.get(asset_id, db)
        if asset and asset.asset_type in {"terminal", "sensor"}:
            return "RUDO"
        return "RUD"

    union_perms = _get_union_asset_perms(token)
    return union_perms.get(asset_id, "")
