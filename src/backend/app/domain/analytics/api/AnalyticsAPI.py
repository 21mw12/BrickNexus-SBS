from fastapi import APIRouter, Body, Depends, Header
from sqlalchemy.orm import Session

from app.common.Response import Response
from app.common.validators import ValidationError
from app.core.algorithm import algorithm_registry
from app.core.middleware.LogRecorder import get_logger
from app.domain.analytics.schema import AnalyticsRunRequest
from app.domain.analytics.service import analytics_service
from app.domain.agent.analysis import analysis_snapshot_service
from app.domain.agent.analysis.store import AnalysisContextUnavailableError
from app.domain.asset.repository.SensorPointRepository import SensorPointRepository
from app.domain.common.AuthDecorator import require_page
from app.domain.common.PermissionChecker import get_user_id_from_token
from app.domain.data.service.PointDataAccessService import point_data_access_service
from app.infra.DB.SQLConnection import sql_manager

router = APIRouter(prefix="/analytics", tags=["analytics"])
logger = get_logger(__name__)


@router.get("/algorithms")
def list_algorithms(_auth: None = require_page("data", "data:analysis")):
    return Response.success(algorithm_registry.catalog())


@router.post("/run")
def run_analysis(
    data: AnalyticsRunRequest = Body(...),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("data", "data:analysis"),
):
    try:
        point_data_access_service.require_read(data.point_ids, authorization or "", db)
        result = analytics_service.run(data, db)
        try:
            metadata = SensorPointRepository().get_metadata_by_point_ids(data.point_ids, db)
            result["ai_context"] = analysis_snapshot_service.create(
                get_user_id_from_token(authorization or ""), result, data.point_ids, metadata
            )
        except Exception as exc:
            # AI摘要属于可选增强能力，绝不能影响数值分析结果。
            logger.warning("AI分析摘要创建失败 error=%s", exc)
            result["ai_context"] = {
                "available": False,
                "analysis_id": None,
                "expires_at": None,
                "reason_code": "AI_CONTEXT_UNAVAILABLE",
            }
        return Response.success(result)
    except PermissionError:
        db.rollback()
        return Response.error_forbidden("permission denied")
    except (ValidationError, ValueError, TypeError) as exc:
        db.rollback()
        return Response.error_params(str(exc))
    except Exception as exc:
        db.rollback()
        logger.exception("智能分析失败 error=%s", exc)
        return Response.error_system("analytics failed")
