from fastapi import APIRouter, Body, Depends, Header, Path, Query
from sqlalchemy.orm import Session

from app.infra.DB.SQLConnection import sql_manager
from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.common.AuthDecorator import require_page
from app.domain.asset.schema.SensorModelSchema import (
    SensorModelAddSchema,
    SensorModelUpdateSchema,
)
from app.domain.asset.service.SensorModelService import SensorModelService

router = APIRouter(prefix="/models", tags=["models"])


# ==========================================================
# 查询所有传感器型号
# ==========================================================
@router.get("/list")
def list_sensor_models(
    authorization: str | None = Header(default=None, alias="Authorization"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:model", "asset:tree", "asset:table"),
):
    try:
        result = SensorModelService.list_models(db, page, limit)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 查询单个传感器型号
# ==========================================================
@router.get("/find/{model_id}")
def find_sensor_model(
    authorization: str | None = Header(default=None, alias="Authorization"),
    model_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:model", "asset:tree", "asset:table"),
):
    try:
        result = SensorModelService.find_model(model_id, db)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 新增传感器型号
# ==========================================================
@router.post("/add")
def add_sensor_model(
    authorization: str | None = Header(default=None, alias="Authorization"),
    data: SensorModelAddSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:model"),
):
    try:
        result = SensorModelService.create_model(data, db)
        db.commit()
        from app.infra.RDF import asset_rdf_runtime
        asset_rdf_runtime.request_rebuild()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 修改传感器型号基本信息（测点绑定不可修改）
# ==========================================================
@router.post("/edit/{model_id}")
def edit_sensor_model(
    authorization: str | None = Header(default=None, alias="Authorization"),
    model_id: str = Path(...),
    data: SensorModelUpdateSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:model"),
):
    try:
        result = SensorModelService.update_model(model_id, data, db)
        db.commit()
        from app.infra.RDF import asset_rdf_runtime
        asset_rdf_runtime.request_rebuild()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 删除传感器型号（级联删除测点）
# ==========================================================
@router.get("/drop/{model_id}")
def drop_sensor_model(
    authorization: str | None = Header(default=None, alias="Authorization"),
    model_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:model"),
):
    try:
        ok = SensorModelService.delete_model(model_id, db)
        db.commit()
        from app.infra.RDF import asset_rdf_runtime
        asset_rdf_runtime.request_rebuild()
        return Response.success({"ok": ok})
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))
