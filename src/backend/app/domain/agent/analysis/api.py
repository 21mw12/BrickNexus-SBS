import asyncio

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.agent.conversation import ConversationUnavailableError
from app.domain.common.AuthDecorator import require_page
from app.infra.DB.SQLConnection import sql_manager
from . import config
from .model import ModelConfigurationError
from .schema import AnalysisAgentRequest
from .service import analysis_agent_service
from .store import AnalysisContextExpiredError, AnalysisContextUnavailableError


router = APIRouter(prefix="/agent/analysis", tags=["analysis-agent"])


@router.post("/respond")
async def respond_to_analysis(
    data: AnalysisAgentRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth=require_page("data", "data:analysis"),
):
    try:
        result = await asyncio.wait_for(
            analysis_agent_service.respond(data, authorization or "", db),
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )
        return Response.success(result)
    except PermissionError as exc:
        return Response.error_forbidden(str(exc))
    except AnalysisContextExpiredError as exc:
        return Response.error(str(exc), code=410, http_status=410, data={"reason_code": "ANALYSIS_CONTEXT_EXPIRED"})
    except (AnalysisContextUnavailableError, ConversationUnavailableError) as exc:
        return Response.error(str(exc), code=503, http_status=503)
    except ModelConfigurationError as exc:
        return Response.error_params(str(exc))
    except (ValidationError, ValueError, TypeError) as exc:
        return Response.error_params(str(exc))
    except asyncio.TimeoutError:
        return Response.error_system("AI分析请求超时，请稍后重试")
    except Exception:
        return Response.error_system("模型服务请求失败，请检查模型配置或稍后重试")
