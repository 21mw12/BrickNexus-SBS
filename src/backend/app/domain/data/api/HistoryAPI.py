"""历史测量数据查询 API。"""

from fastapi import APIRouter, Body, Depends, Header
from sqlalchemy.orm import Session

from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.asset.repository.SensorPointRepository import SensorPointRepository
from app.domain.common.AuthDecorator import require_page
from app.core.middleware.LogRecorder import get_logger
from app.domain.data.service.PointDataAccessService import point_data_access_service
from app.domain.common.PermissionChecker import check_asset_instance_permission
from app.domain.data.schema.HistorySchema import (
    HistoryHeatmapQuerySchema,
    HistoryQuerySchema,
    RawHistoryQuerySchema,
)
from app.domain.data.service.DataQueryService import data_query_service
from app.domain.data.service.HistoryHeatmapService import history_heatmap_service
from app.domain.data.service.HistoryService import history_service
from app.infra.DB.SQLConnection import sql_manager

logger = get_logger(__name__)
sensor_point_repository = SensorPointRepository()
router = APIRouter(prefix="/history", tags=["history"])


def _check_point_permissions(
    point_ids: list[str], authorization: str | None, db: Session
):
    try:
        point_data_access_service.require_read(
            point_ids, authorization or "", db,
            repository=sensor_point_repository,
            checker=check_asset_instance_permission,
        )
    except PermissionError:
        return Response.error_forbidden("permission denied")
    except ValidationError as exc:
        return Response.error_params(str(exc))
    return None


@router.post("/query")
def query_history(
    data: HistoryQuerySchema = Body(...),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("data", "data:history"),
):
    """按测点批量查询历史数据，并按需执行 LTTB 下采样。"""
    try:
        permission_error = _check_point_permissions(
            data.point_ids, authorization, db
        )
        if permission_error is not None:
            return permission_error

        result = history_service.query(data, db)
        return Response.success(result)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        logger.exception("历史数据查询失败 error=%s", exc)
        return Response.error_system("history query failed")


@router.post("/heatmap")
def query_history_heatmap(
    data: HistoryHeatmapQuerySchema = Body(...),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("data", "data:history"),
):
    """返回对齐时间矩阵、归一化矩阵及相关性矩阵。"""
    try:
        permission_error = _check_point_permissions(
            data.point_ids, authorization, db
        )
        if permission_error is not None:
            return permission_error
        return Response.success(history_heatmap_service.query(data, db))
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        logger.exception("历史热力图查询失败 error=%s", exc)
        return Response.error_system("history heatmap query failed")


@router.post("/raw")
def query_raw_history(
    data: RawHistoryQuerySchema = Body(...),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("data", "data:history"),
):
    """按时间范围返回真实测点全部原始数据，不执行下采样。"""
    try:
        permission_error = _check_point_permissions(
            data.point_ids, authorization, db
        )
        if permission_error is not None:
            return permission_error
        return Response.success(data_query_service.query_raw(data, db))
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        logger.exception("全量历史数据查询失败 error=%s", exc)
        return Response.error_system("raw history query failed")
