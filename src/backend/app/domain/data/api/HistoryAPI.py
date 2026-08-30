"""历史测量数据查询 API。"""

from fastapi import APIRouter, Body, Depends, Header
from sqlalchemy.orm import Session

from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.asset.repository.SensorPointRepository import SensorPointRepository
from app.domain.common.AuthDecorator import require_page
from app.core.middleware.LogRecorder import get_logger
from app.domain.common.PermissionChecker import check_asset_instance_permission
from app.domain.data.schema.HistorySchema import HistoryQuerySchema
from app.domain.data.service.HistoryService import history_service
from app.infra.DB.SQLConnection import sql_manager

logger = get_logger(__name__)
sensor_point_repository = SensorPointRepository()

router = APIRouter(prefix="/history", tags=["history"])


@router.post("/query")
def query_history(
    data: HistoryQuerySchema = Body(...),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("data", "data:history"),
):
    """按测点批量查询历史数据，并按需执行 LTTB 下采样。"""
    try:
        # 1. 查询传感器ID
        point_sensor_map = sensor_point_repository.get_sensor_ids_by_point_ids(data.point_ids, db)
        if len(point_sensor_map) != len(data.point_ids):
            return Response.error_params("invalid point_ids")

        # 2. 多个 Point 可能属于同一个 Sensor，去重后复用现有资产实例权限校验。
        for sensor_id in dict.fromkeys(point_sensor_map.values()):
            if not check_asset_instance_permission(authorization or "", sensor_id, "R", db):
                return Response.error_forbidden("permission denied")

        result = history_service.query(data, db)
        return Response.success(result)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        logger.exception("历史数据查询失败 error=%s", exc)
        return Response.error_system("history query failed")
