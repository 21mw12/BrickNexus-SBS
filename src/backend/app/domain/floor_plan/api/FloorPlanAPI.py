"""楼层平面图上传、查看和房间标记接口。"""

from fastapi import APIRouter, Body, Depends, File, Header, Path, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.floor_plan.schema.FloorPlanSchema import FloorRoomRegionSaveSchema
from app.domain.floor_plan.service.FloorPlanService import FloorPlanService
from app.domain.common.AuthDecorator import require_page
from app.domain.common.PermissionChecker import check_asset_instance_permission
from app.infra.DB.SQLConnection import sql_manager

router = APIRouter(prefix="/floor-plans", tags=["floor-plans"])


@router.post("/{floor_id}/image")
def upload_floor_plan_image(
    floor_id: str = Path(...),
    image: UploadFile = File(...),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:table", "asset:tree"),
):
    """上传或替换楼层平面图，替换图片时自动清除旧房间标记。"""
    try:
        if not check_asset_instance_permission(authorization, floor_id, "U", db):
            return Response.error_forbidden("no update permission for this floor")
        result = FloorPlanService.upload_image(floor_id, image, db)
        return Response.success(result)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        return Response.error_system(str(exc))
    finally:
        image.file.close()


@router.get("/{floor_id}/image")
def get_floor_plan_image(
    floor_id: str = Path(...),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:table", "asset:tree"),
):
    """校验楼层读取权限后返回平面图文件，不公开暴露资源目录。"""
    try:
        if not check_asset_instance_permission(authorization, floor_id, "R", db):
            return Response.error_forbidden("no view permission for this floor")
        image_path, image_type = FloorPlanService.get_image_file(floor_id, db)
        return FileResponse(path=image_path, media_type=image_type)
    except ValidationError as exc:
        return Response.error_params(str(exc))
    except Exception as exc:
        return Response.error_system(str(exc))


@router.get("/{floor_id}")
def get_floor_plan(
    floor_id: str = Path(...),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:table", "asset:tree"),
):
    """查询楼层平面图元数据和当前全部房间标记。"""
    try:
        if not check_asset_instance_permission(authorization, floor_id, "R", db):
            return Response.error_forbidden("no view permission for this floor")
        return Response.success(FloorPlanService.get_floor_plan(floor_id, db))
    except ValidationError as exc:
        return Response.error_params(str(exc))
    except Exception as exc:
        return Response.error_system(str(exc))


@router.put("/{floor_id}/regions")
def save_floor_room_regions(
    floor_id: str = Path(...),
    payload: FloorRoomRegionSaveSchema = Body(...),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:table", "asset:tree"),
):
    """批量覆盖一个楼层的房间标记，空列表表示清空全部标记。"""
    try:
        if not check_asset_instance_permission(authorization, floor_id, "U", db):
            return Response.error_forbidden("no update permission for this floor")
        result = FloorPlanService.save_regions(floor_id, payload, db)
        return Response.success(result)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        return Response.error_system(str(exc))


@router.delete("/{floor_id}")
def delete_floor_plan(
    floor_id: str = Path(...),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("asset", "asset:table", "asset:tree"),
):
    """删除楼层平面图、其全部房间标记以及实际图片文件。"""
    try:
        if not check_asset_instance_permission(authorization, floor_id, "U", db):
            return Response.error_forbidden("no update permission for this floor")
        return Response.success({"ok": FloorPlanService.delete_floor_plan(floor_id, db)})
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        return Response.error_system(str(exc))
