#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/07/23
# @function : 统一鉴权装饰器（FastAPI Depends）
# @version  : v1.0

from typing import List
from fastapi import Depends, Header, HTTPException, Path, Request
from sqlalchemy.orm import Session

from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.common.PermissionChecker import (
    check_page_permission,
    check_asset_instance_permission,
)
from app.infra.DB.SQLConnection import sql_manager


def require_page(*page_codes: str):
    """
    页面权限校验依赖。
    用法:
        @router.get("/path")
        def handler(
            ...,
            _auth=Depends(require_page("asset", "asset:tree")),
        ): ...

    用户拥有白名单中任一页面权限即通过。
    """

    def dependency(
        authorization: str | None = Header(default=None, alias="Authorization"),
    ):
        if not authorization:
            raise HTTPException(status_code=401, detail="token is required")
        try:
            allowed = check_page_permission(authorization, list(page_codes))
        except ValidationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        if not allowed:
            raise HTTPException(status_code=403, detail="permission denied")
        return True

    return Depends(dependency)


def require_asset_perm(code: str, asset_id_param: str = "asset_id"):
    """
    资产实例权限校验依赖。
    用法:
        @router.get("/find/{asset_id}")
        def handler(
            asset_id: str = Path(...),
            ...,
            _auth=Depends(require_asset_perm("R")),
        ): ...

    code: R | U | D | O
    asset_id_param: 路径参数名（默认 "asset_id"）
    """

    def dependency(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ):
        if not authorization:
            raise HTTPException(status_code=401, detail="token is required")
        asset_id = request.path_params.get(asset_id_param, "")
        try:
            with sql_manager.get_db("main") as db:
                allowed = check_asset_instance_permission(authorization, asset_id, code, db)
        except ValidationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        if not allowed:
            raise HTTPException(status_code=403, detail=f"no {code} permission for this asset")
        return True

    return Depends(dependency)
