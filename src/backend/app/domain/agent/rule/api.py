import asyncio

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.common.Response import Response
from app.domain.common.AuthDecorator import require_page
from app.infra.DB.SQLConnection import sql_manager
from . import config
from .schema import GenerateRequest
from .model import ModelConfigurationError
from .service import rule_agent_service
from app.domain.agent.conversation import ConversationUnavailableError

router = APIRouter(prefix="/agent/rule", tags=["rule-agent"])


@router.post("/generate")
async def generate_rule_draft(
    data: GenerateRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth= require_page("rule"),
):
    """仅返回AI文字说明和完整可编辑表单，不保存或执行规则。"""
    try:
        result = await asyncio.wait_for(
            rule_agent_service.generate(data, authorization or "", db),
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )
        return Response.success(result)
    except PermissionError as exc:
        return Response.error_forbidden(str(exc))
    except ModelConfigurationError as exc:
        return Response.error_params(str(exc))
    except ConversationUnavailableError as exc:
        return Response.error(str(exc), code=503, http_status=503)
    except asyncio.TimeoutError:
        return Response.error_system("规则助手请求超时，请缩小需求后重试")
    except ValueError:
        return Response.error_params("模型草稿结构无效，请重新描述需求；原表单未改变")
    except Exception:
        # 不将供应商异常、请求头或凭据回传到前端。
        return Response.error_system("模型服务请求失败，请检查模型配置或稍后重试")
