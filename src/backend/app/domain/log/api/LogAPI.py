from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.common.AuthDecorator import require_page
from app.domain.log.schema import LogQuery
from app.domain.log.service import LogService
from app.infra.DB.SQLConnection import sql_manager

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post("/list")
def list_logs(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1),
    filters: LogQuery | None = Body(default=None),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("logs"),
):
    try:
        return Response.success(LogService.list_logs(db, page, limit, filters))
    except ValidationError as exc:
        return Response.error_params(str(exc))
    except Exception as exc:
        return Response.error_system(str(exc))


@router.get("/options")
def get_log_options(
    _auth: None = require_page("logs"),
):
    return Response.success(LogService.get_options())
