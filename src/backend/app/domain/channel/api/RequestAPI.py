from fastapi import APIRouter, Body, Depends, Header, Path, Query
from sqlalchemy.orm import Session

from app.infra.DB.SQLConnection import sql_manager
from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.common.AuthDecorator import require_page
from app.domain.channel.schema.RequestSchema import (
    RequestAddSchema,
    RequestEditSchema,
    RequestQuerySchema,
)
from app.domain.channel.service.RequestService import RequestService


router = APIRouter(prefix="/request", tags=["request"])


# ==========================================================
# Request 分页查询
# ==========================================================
@router.post("/list")
def list_requests(
    authorization: str | None = Header(default=None, alias="Authorization"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    filters: RequestQuerySchema | None = Body(None),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = RequestService.list_requests(db, page, limit, filters)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 新增 Request
# ==========================================================
@router.post("/add")
def add_request(
    authorization: str | None = Header(default=None, alias="Authorization"),
    request_data: RequestAddSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = RequestService.create_request(request_data, db)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 查询单个 Request
# ==========================================================
@router.get("/find/{request_id}")
def find_request(
    authorization: str | None = Header(default=None, alias="Authorization"),
    request_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = RequestService.find_request(request_id, db)
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 修改 Request
# ==========================================================
@router.post("/edit/{request_id}")
def edit_request(
    authorization: str | None = Header(default=None, alias="Authorization"),
    request_id: str = Path(...),
    request_data: RequestEditSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = RequestService.edit_request(request_id, request_data, db)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 测试 Request
# ==========================================================
@router.post("/test/{request_id}")
def test_request(
    authorization: str | None = Header(default=None, alias="Authorization"),
    request_id: str = Path(...),
    timeout: float = Body(default=10.0, embed=True),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = RequestService.test_request(request_id, timeout, db)
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 启用或停用 Request
# ==========================================================
@router.post("/toggle/{request_id}")
def toggle_request(
    authorization: str | None = Header(default=None, alias="Authorization"),
    request_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = RequestService.toggle_active(request_id, db)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 删除 Request
# ==========================================================
@router.get("/drop/{request_id}")
def drop_request(
    authorization: str | None = Header(default=None, alias="Authorization"),
    request_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        ok = RequestService.delete_request(request_id, db)
        db.commit()
        return Response.success({"ok": ok})
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))
