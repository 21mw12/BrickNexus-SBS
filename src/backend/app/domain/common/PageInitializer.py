#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/07/14
# @function : 启动时初始化页面数据
# @version  : v1.0

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.user.repository import PageRepository
from app.domain.user.repository.models import Page
from app.core.utils.UUIDGenerator import uuid_generator


# ==========================================================
# 待添加的页面数据（请按需填写）
# ==========================================================
# 使用嵌套 JSON 树形结构表示父子关系，无需手动指定 page_id_parent。
# 每条记录:
#   name:       str                  # 页面名称
#   path_code:  str                  # 页面编码（路径标识）
#   sub_pages:  List[Dict]           # 子页面列表，结构与父节点一致，可为空列表
# ==========================================================

PAGE_TREE: List[Dict[str, Any]] = [
    # TODO: 在此处添加需要初始化的页面数据
    # 示例:
    # {
    #     "name": "首页",
    #     "path_code": "/home",
    #     "sub_pages": [],
    # },
    {
        "name": "看板",
        "path_code": "dashboard",
    },
    {
        "name": "楼层平面图配置",
        "path_code": "floorPlan",
    },
    {
        "name": "资产中心",
        "path_code": "asset",
        "sub_pages": [
            {
                "name": "资产树",
                "path_code": "asset:tree"
            },
            {
                "name": "资产表",
                "path_code": "asset:table"
            },
            {
                "name": "传感器型号管理",
                "path_code": "asset:model"
            },
        ],
    },
    {
        "name": "数据监测",
        "path_code": "data",
        "sub_pages": [
            {
                "name": "实时数据",
                "path_code": "data:realtime"
            },
            {
                "name": "历史数据",
                "path_code": "data:history"
            },
        ],
    },
    {
        "name": "采控通道配置",
        "path_code": "channel",
        "sub_pages": [
            {
                "name": "通道管理",
                "path_code": "channel:management"
            },
            {
                "name": "请求管理",
                "path_code": "channel:requests"
            },
            {
                "name": "控制管理",
                "path_code": "channel:controls"
            },
        ],
    },
    {
        "name": "规则管理",
        "path_code": "rule",
    },
    {
        "name": "用户管理",
        "path_code": "user",
        "sub_pages": [
            {
                "name": "账户管理",
                "path_code": "user:accounts"
            },
            {
                "name": "角色管理",
                "path_code": "user:roles"
            },
        ],
    },
    {
        "name": "系统日志",
        "path_code": "logs",
    },
]


def _create_page_recursive(
    node: Dict[str, Any],
    page_id_parent: Optional[str],
    page_repo: PageRepository,
    db: Session,
    result: List[Page],
) -> None:
    """
    递归创建页面节点及其子页面。
    :param node:           当前页面节点数据
    :param page_id_parent: 父页面 ID（顶层为 None）
    :param page_repo:      PageRepository 实例
    :param db:             数据库会话
    :param result:         累积结果列表
    """
    name = node.get("name")
    path_code = node.get("path_code")
    sub_pages = node.get("sub_pages", [])

    if not name or not path_code:
        return

    # 页面编码才是权限契约；同名页面可以属于不同模块。
    existing = page_repo.select_one(db, filters={"path_code": path_code})
    if existing is not None:
        result.append(existing)
        # 继续处理子页面，使用已有页面的 ID 作为父 ID
        page_id = existing.page_id
    else:
        page = Page(
            page_id=uuid_generator.random(),
            page_id_parent=page_id_parent,
            name=name,
            path_code=path_code,
        )
        page = page_repo.create(page, db=db)
        if page is None:
            raise ValidationError(f"create page '{name}' failed")
        result.append(page)
        page_id = page.page_id

    # 递归创建子页面
    for child in sub_pages:
        _create_page_recursive(child, page_id, page_repo, db, result)


def ensure_pages(db: Session) -> List[Page]:
    """
    启动时确保 page 表中存在 PAGE_TREE 中预设的页面数据。
    若页面名称已存在则跳过，否则递归创建整个页面树。
    :param db: 数据库会话
    :return: 本次创建或已存在的页面列表
    """
    page_repo = PageRepository()
    result: List[Page] = []

    for node in PAGE_TREE:
        _create_page_recursive(node, None, page_repo, db, result)

    return result


def refresh_page_permission_caches(db: Session) -> int:
    """页面初始化或权限迁移后，立即让 Redis 页面权限与 SQL 一致。"""
    from app.domain.user.repository.models import Role
    from app.domain.user.service.UserService import UserService

    role_ids = list(db.scalars(select(Role.role_id)).all())
    for role_id in role_ids:
        UserService.refresh_role_cache(role_id, db)
    return len(role_ids)
