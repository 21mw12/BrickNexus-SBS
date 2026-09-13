from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.orm import Session

from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.common.AuthDecorator import require_page
from app.domain.settings.schema import (
    LLMConfigAddSchema,
    LLMConfigEditSchema,
    LLMConfigQuerySchema,
    LLMConfigTestSchema,
)
from app.domain.settings.service import LLMConnectivityError, llm_config_service
from app.infra.DB.SQLConnection import sql_manager


router = APIRouter(prefix="/settings/llm", tags=["settings-llm"])


def _connectivity_error(exc: LLMConnectivityError):
    return Response.error(
        str(exc), code=502, http_status=502, data=exc.result
    )


def _connectivity_result(result: dict):
    if result.get("connected"):
        return Response.success(result)
    return Response.error(
        result.get("message", "模型连接失败"),
        code=502,
        http_status=502,
        data=result,
    )


@router.post("/list")
def list_llm_configs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    filters: LLMConfigQuerySchema | None = Body(None),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("settings"),
):
    return Response.success(llm_config_service.list(db, page, limit, filters))


@router.get("/find/{llm_id}")
def find_llm_config(
    llm_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("settings"),
):
    try:
        return Response.success(llm_config_service.find(llm_id, db))
    except ValidationError as exc:
        return Response.error_params(str(exc))


@router.post("/add")
def add_llm_config(
    data: LLMConfigAddSchema,
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("settings"),
):
    try:
        result = llm_config_service.add(data, db)
        db.commit()
        return Response.success(result)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception:
        db.rollback()
        return Response.error_system("模型配置保存失败")


@router.post("/edit/{llm_id}")
async def edit_llm_config(
    llm_id: str,
    data: LLMConfigEditSchema,
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("settings"),
):
    try:
        result = await llm_config_service.edit(llm_id, data, db)
        db.commit()
        return Response.success(result)
    except LLMConnectivityError as exc:
        db.rollback()
        return _connectivity_error(exc)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception:
        db.rollback()
        return Response.error_system("模型配置更新失败")


@router.get("/drop/{llm_id}")
def drop_llm_config(
    llm_id: str,
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("settings"),
):
    try:
        result = llm_config_service.drop(llm_id, db)
        db.commit()
        return Response.success({"ok": result})
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception:
        db.rollback()
        return Response.error_system("模型配置删除失败")


@router.post("/test")
async def test_llm_draft(
    data: LLMConfigTestSchema,
    _auth: None = require_page("settings"),
):
    try:
        return _connectivity_result(await llm_config_service.test_draft(data))
    except ValidationError as exc:
        return Response.error_params(str(exc))


@router.post("/test/{llm_id}")
async def test_llm_saved(
    llm_id: str,
    data: LLMConfigTestSchema | None = Body(None),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("settings"),
):
    try:
        return _connectivity_result(
            await llm_config_service.test_saved(llm_id, db, data)
        )
    except ValidationError as exc:
        return Response.error_params(str(exc))


@router.post("/activate/{llm_id}")
async def activate_llm_config(
    llm_id: str,
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("settings"),
):
    try:
        result = await llm_config_service.activate(llm_id, db)
        db.commit()
        return Response.success(result)
    except LLMConnectivityError as exc:
        db.rollback()
        return _connectivity_error(exc)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception:
        db.rollback()
        return Response.error_system("模型激活失败")


@router.post("/deactivate/{llm_id}")
def deactivate_llm_config(
    llm_id: str,
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("settings"),
):
    try:
        result = llm_config_service.deactivate(llm_id, db)
        db.commit()
        return Response.success(result)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception:
        db.rollback()
        return Response.error_system("模型停用失败")
