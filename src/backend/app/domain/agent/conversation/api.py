from fastapi import APIRouter, Header

from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.common.AuthDecorator import require_page
from app.domain.common.PermissionChecker import get_user_id_from_token
from .service import ConversationUnavailableError, conversation_service


router = APIRouter(prefix="/agent/conversations", tags=["agent-conversation"])


@router.delete("/{conversation_id}")
def close_conversation(
    conversation_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
    _auth=require_page("rule"),
):
    try:
        user_id = get_user_id_from_token(authorization or "")
        return Response.success(conversation_service.close(user_id, conversation_id))
    except PermissionError as exc:
        return Response.error_forbidden(str(exc))
    except (ValidationError, ValueError) as exc:
        return Response.error_params(str(exc))
    except ConversationUnavailableError as exc:
        return Response.error(str(exc), code=503, http_status=503)
