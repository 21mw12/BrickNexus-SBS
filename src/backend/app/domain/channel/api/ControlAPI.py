from fastapi import APIRouter, Body, Depends, Header, Path, Query
from sqlalchemy.orm import Session

from app.infra.DB.SQLConnection import sql_manager
from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.common.AuthDecorator import require_page
from app.domain.common.PermissionChecker import (
    check_asset_instance_permission,
    get_viewable_asset_ids,
)
from app.domain.channel.schema.ControlSchema import (
    ControlAddSchema,
    ControlEditSchema,
    ControlQuerySchema,
)
from app.domain.channel.service.ControlService import ControlService


router = APIRouter(prefix="/control", tags=["control"])


# ==========================================================
# Control 分页查询
# ==========================================================
@router.post("/list")
def list_controls(
    authorization: str | None = Header(default=None, alias="Authorization"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    filters: ControlQuerySchema | None = Body(None),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:controls"),
):
    try:
        if (
            filters is not None
            and filters.asset_id
            and not check_asset_instance_permission(
                authorization, filters.asset_id, "R", db
            )
        ):
            return Response.error_forbidden("no view permission for this asset")

        # None 表示 root 不限制资产范围；空集合才表示没有可见资产。
        viewable_asset_ids = get_viewable_asset_ids(authorization, db)
        result = ControlService.list_controls(
            db, page, limit, filters, viewable_asset_ids
        )
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 查询单个 Control
# ==========================================================
@router.get("/find/{control_id}")
def find_control(
    authorization: str | None = Header(default=None, alias="Authorization"),
    control_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:controls"),
):
    try:
        bound_asset_id = ControlService.get_bound_asset_id(db, control_id)
        if bound_asset_id is None:
            return Response.error("control not found", code=404, http_status=404)
        if not check_asset_instance_permission(
            authorization, bound_asset_id, "R", db
        ):
            return Response.error_forbidden("no view permission for this asset")

        result = ControlService.find(db, control_id)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 新增 Control
# ==========================================================
@router.post("/add")
def add_control(
    authorization: str | None = Header(default=None, alias="Authorization"),
    control_data: ControlAddSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:controls"),
):
    try:
        if not check_asset_instance_permission(
            authorization, control_data.asset_id, "O", db
        ):
            return Response.error_forbidden("no operate permission for this asset")

        result = ControlService.add(db, control_data)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 修改 Control
# ==========================================================
@router.post("/edit/{control_id}")
def edit_control(
    authorization: str | None = Header(default=None, alias="Authorization"),
    control_id: str = Path(...),
    control_data: ControlEditSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:controls"),
):
    try:
        bound_asset_id = ControlService.get_bound_asset_id(db, control_id)
        if bound_asset_id is None:
            return Response.error("control not found", code=404, http_status=404)
        if not check_asset_instance_permission(
            authorization, bound_asset_id, "O", db
        ):
            return Response.error_forbidden("no operate permission for this asset")

        new_asset_id = control_data.asset_id or bound_asset_id
        if (
            new_asset_id != bound_asset_id
            and not check_asset_instance_permission(authorization, new_asset_id, "O", db)
        ):
            return Response.error_forbidden("no operate permission for this asset")

        result = ControlService.edit(db, control_id, control_data)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 启用或停用 Control
# ==========================================================
@router.post("/toggle/{control_id}")
def toggle_control(
    authorization: str | None = Header(default=None, alias="Authorization"),
    control_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:controls"),
):
    try:
        bound_asset_id = ControlService.get_bound_asset_id(db, control_id)
        if bound_asset_id is None:
            return Response.error("control not found", code=404, http_status=404)
        if not check_asset_instance_permission(
            authorization, bound_asset_id, "O", db
        ):
            return Response.error_forbidden("no operate permission for this asset")

        ok = ControlService.toggle(db, control_id)
        db.commit()
        return Response.success({"ok": ok})
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 删除 Control
# ==========================================================
@router.get("/drop/{control_id}")
def drop_control(
    authorization: str | None = Header(default=None, alias="Authorization"),
    control_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:controls"),
):
    try:
        bound_asset_id = ControlService.get_bound_asset_id(db, control_id)
        if bound_asset_id is None:
            return Response.error("control not found", code=404, http_status=404)
        if not check_asset_instance_permission(
            authorization, bound_asset_id, "O", db
        ):
            return Response.error_forbidden("no operate permission for this asset")

        ok = ControlService.drop(db, control_id)
        db.commit()
        return Response.success({"ok": ok})
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 立即执行 Control
# ==========================================================
@router.post("/execute/{control_id}")
def execute_control(
    authorization: str | None = Header(default=None, alias="Authorization"),
    control_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:controls"),
):
    try:
        bound_asset_id = ControlService.get_bound_asset_id(db, control_id)
        if bound_asset_id is None:
            return Response.error("control not found", code=404, http_status=404)
        if not check_asset_instance_permission(
            authorization, bound_asset_id, "O", db
        ):
            return Response.error_forbidden("no operate permission for this asset")

        result = ControlService.execute(db, control_id)
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))
