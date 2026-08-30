import os

from fastapi import APIRouter, Body, Depends, Header, Path, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.infra.DB.SQLConnection import sql_manager
from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.common.AuthDecorator import require_page
from app.domain.common.PermissionChecker import (
    check_asset_type_permission,
    check_asset_instance_permission,
    get_viewable_asset_ids,
    get_user_id_from_token,
)
from app.domain.asset.service.AssetService import AssetService
from app.domain.asset.schema import *

router = APIRouter(prefix="/assets", tags=["assets"])


# ==========================================================
# 导出 Excel
# ==========================================================
@router.get("/excel")
def export_assets_excel(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:table", "asset:tree"),
):
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
        export_dir = os.path.join(base_dir, "resources", "exports")
        file_path = AssetService.export_assets_excel(db, export_dir)
        db.commit()
        return FileResponse(
            file_path,
            filename=os.path.basename(file_path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 资产树
# ==========================================================
@router.get("/tree")
def get_assets_tree(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:tree"),
):
    try:
        viewable = get_viewable_asset_ids(authorization, db)
        result = AssetService.query_assets_tree(db, viewable=viewable)
        return Response.success(result)
    except ValidationError as e:
        return Response.error_params(str(e))
    except Exception as e:
        return Response.error_system(str(e))


# ==========================================================
# 资产表格
# ==========================================================
@router.post("/form")
def get_assets_form(
    authorization: str | None = Header(default=None, alias="Authorization"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    filters: AssetQueryFilterSchema | None = Body(None),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:table", "asset:tree"),
):
    try:
        viewable = get_viewable_asset_ids(authorization, db)
        result = AssetService.query_assets_form(db, page, limit, filters, asset_ids=viewable)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 查询单个资产
# ==========================================================
@router.get("/find/{asset_id}")
def find_asset(
    authorization: str | None = Header(default=None, alias="Authorization"),
    asset_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:table", "asset:tree"),
):
    try:
        if not check_asset_instance_permission(authorization, asset_id, "R", db):
            return Response.error_forbidden("no view permission for this asset")

        result = AssetService().query_asset_by_id(asset_id, db=db)
        db.commit()
        if result is None:
            return Response.error_params("asset not found", code=404, http_status=404)
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 新增资产
# ==========================================================
@router.post("/add")
def add_new_asset(
    authorization: str | None = Header(default=None, alias="Authorization"),
    asset_data: AssetAddSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:table", "asset:tree"),
):
    try:
        if not check_asset_type_permission(authorization, asset_data.asset_type):
            return Response.error_forbidden(f"no create permission for asset type: {asset_data.asset_type}")

        if asset_data.asset_id_parent:
            if not check_asset_instance_permission(authorization, asset_data.asset_id_parent, "R", db):
                return Response.error_forbidden("no view permission for parent asset")

        user_id = get_user_id_from_token(authorization)
        result = AssetService().save_new_asset(asset_data, db=db, creator_user_id=user_id)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 修改资产
# ==========================================================
@router.post("/edit/{asset_id}")
def edit_asset(
    authorization: str | None = Header(default=None, alias="Authorization"),
    asset_id: str = Path(...),
    asset_data: AssetUpdateSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:table", "asset:tree"),
):
    try:
        if not check_asset_instance_permission(authorization, asset_id, "U", db):
            return Response.error_forbidden("no update permission for this asset")

        result = AssetService().alter_asset_by_id(asset_id, asset_data, db=db)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 删除资产（级联删除 + 权限清理）
# ==========================================================
@router.get("/drop/{asset_id}")
def drop_asset(
    authorization: str | None = Header(default=None, alias="Authorization"),
    asset_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:table", "asset:tree"),
):
    try:
        if not check_asset_instance_permission(authorization, asset_id, "D", db):
            return Response.error_forbidden("no delete permission for this asset")

        ok = AssetService().drop_asset_by_id(asset_id, db=db)
        db.commit()
        return Response.success({"ok": ok})
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))
