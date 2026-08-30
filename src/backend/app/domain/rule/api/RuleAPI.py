from fastapi import APIRouter, Body, Depends, Header, Path, Query
from sqlalchemy.orm import Session

from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.common.AuthDecorator import require_page
from app.domain.rule.schema import EventQuery, RuleConfig, RuleQuery, TaskQuery
from app.domain.rule.service import RuleOptionsService, RuleService
from app.infra.DB.SQLConnection import sql_manager

router = APIRouter(prefix="/rules", tags=["rules"])


@router.post("/list")
def list_rules(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1),
    filters: RuleQuery | None = Body(default=None),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("rule"),
):
    try:
        return Response.success(RuleService.list_rules(db, page, limit, filters))
    except ValidationError as exc:
        return Response.error_params(str(exc))
    except Exception as exc:
        return Response.error_system(str(exc))


@router.get("/options")
def get_rule_options(
    _auth: None = require_page("rule"),
):
    return Response.success(RuleOptionsService.get_options())


@router.get("/ttl/{rule_id}")
def get_rule_ttl(
    rule_id: str = Path(...), db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("rule"),
):
    try:
        return Response.success({"rule_id": rule_id, "ttl": RuleService.get_ttl(rule_id, db)})
    except ValidationError as exc:
        return Response.error_params(str(exc))
    except Exception as exc:
        return Response.error_system(str(exc))


@router.get("/find/{rule_id}")
def find_rule(
    rule_id: str = Path(...), db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("rule"),
):
    try:
        return Response.success(RuleService.find(rule_id, db))
    except ValidationError as exc:
        return Response.error_params(str(exc))
    except Exception as exc:
        return Response.error_system(str(exc))


@router.post("/add")
def add_rule(
    authorization: str | None = Header(default=None, alias="Authorization"),
    data: RuleConfig = Body(...), db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("rule"),
):
    try:
        return Response.success(RuleService.create(data, authorization or "", db))
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except PermissionError as exc:
        db.rollback()
        return Response.error_forbidden(str(exc))
    except Exception as exc:
        db.rollback()
        return Response.error_system(str(exc))


@router.post("/edit/{rule_id}")
def edit_rule(
    authorization: str | None = Header(default=None, alias="Authorization"),
    rule_id: str = Path(...), data: RuleConfig = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("rule"),
):
    try:
        return Response.success(RuleService.edit(rule_id, data, authorization or "", db))
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except PermissionError as exc:
        db.rollback()
        return Response.error_forbidden(str(exc))
    except Exception as exc:
        db.rollback()
        return Response.error_system(str(exc))


@router.post("/toggle/{rule_id}")
def toggle_rule(
    authorization: str | None = Header(default=None, alias="Authorization"),
    rule_id: str = Path(...), db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("rule"),
):
    try:
        return Response.success(RuleService.toggle(rule_id, authorization or "", db))
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        return Response.error_system(str(exc))


@router.get("/drop/{rule_id}")
def drop_rule(
    authorization: str | None = Header(default=None, alias="Authorization"),
    rule_id: str = Path(...), db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("rule"),
):
    try:
        return Response.success({"ok": RuleService.delete(rule_id, authorization or "", db)})
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        return Response.error_system(str(exc))


@router.post("/events")
def list_events(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1),
    filters: EventQuery | None = Body(default=None),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("rule"),
):
    try:
        return Response.success(RuleService.list_events(db, page, limit, filters or EventQuery()))
    except Exception as exc:
        return Response.error_system(str(exc))


@router.post("/tasks")
def list_tasks(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1),
    filters: TaskQuery | None = Body(default=None),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("rule"),
):
    try:
        return Response.success(RuleService.list_tasks(db, page, limit, filters or TaskQuery()))
    except Exception as exc:
        return Response.error_system(str(exc))
