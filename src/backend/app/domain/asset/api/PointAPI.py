from fastapi import APIRouter, Body, Depends, Header, Path, Query
from sqlalchemy.orm import Session

from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.asset.schema.PointSchema import PointAddSchema, PointUpdateSchema
from app.domain.asset.service.PointService import PointService
from app.domain.common.AuthDecorator import require_page
from app.infra.DB.SQLConnection import sql_manager


router = APIRouter(prefix="/points", tags=["points"])


@router.get("/list")
def list_points(
    authorization: str | None = Header(default=None, alias="Authorization"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:model", "asset:tree", "asset:table"),
):
    try:
        return Response.success(PointService.list_points(db, page, limit))
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        return Response.error_system(str(exc))


@router.get("/find/{point_id}")
def find_point(
    authorization: str | None = Header(default=None, alias="Authorization"),
    point_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:model", "asset:tree", "asset:table"),
):
    try:
        return Response.success(PointService.find_point(point_id, db))
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        return Response.error_system(str(exc))


@router.post("/add")
def add_point(
    authorization: str | None = Header(default=None, alias="Authorization"),
    data: PointAddSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:model"),
):
    try:
        result = PointService.create_point(data, db)
        db.commit()
        from app.infra.RDF import asset_rdf_runtime
        asset_rdf_runtime.request_rebuild()
        return Response.success(result)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        return Response.error_system(str(exc))


@router.post("/edit/{point_id}")
def edit_point(
    authorization: str | None = Header(default=None, alias="Authorization"),
    point_id: str = Path(...),
    data: PointUpdateSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:model"),
):
    try:
        result = PointService.update_point(point_id, data, db)
        db.commit()
        from app.infra.RDF import asset_rdf_runtime
        asset_rdf_runtime.request_rebuild()
        return Response.success(result)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        return Response.error_system(str(exc))


@router.get("/drop/{point_id}")
def drop_point(
    authorization: str | None = Header(default=None, alias="Authorization"),
    point_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:model"),
):
    try:
        result = PointService.delete_point(point_id, db)
        db.commit()
        from app.infra.RDF import asset_rdf_runtime
        asset_rdf_runtime.request_rebuild()
        return Response.success({"ok": result})
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        return Response.error_system(str(exc))
