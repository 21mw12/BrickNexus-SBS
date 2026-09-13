from .schema import RuleFormDraft
from .model import RuleModelClient
from .tools import RuleCandidateTools
from app.domain.common.PermissionChecker import get_user_id_from_token
from app.domain.agent.conversation import ConversationRunResult


def merge_draft(current, patch):
    result = current.model_dump(exclude_none=True)
    result["form"].update(patch.form)
    for key in ("sensor_id", "comparisons", "actions"):
        value = getattr(patch, key)
        if value is not None:
            result[key] = [item.model_dump(exclude_none=True) for item in value] if isinstance(value, list) else value
    return RuleFormDraft.model_validate(result)


class RuleAgentService:
    def __init__(self, client=None, user_resolver=None):
        self.client = client or RuleModelClient()
        self.user_resolver = user_resolver or get_user_id_from_token

    async def generate(self, data, authorization, db):
        tools = RuleCandidateTools(authorization, db)
        tools.validate_draft(data.current_form)
        user_id = self.user_resolver(authorization)
        result = await self.client.suggest(
            data.message,
            data.current_form,
            tools,
            user_id=user_id,
            conversation_id=data.conversation_id,
        )
        if isinstance(result, ConversationRunResult):
            suggestion = result.output
            conversation_id = result.conversation_id
            conversation_reset = result.conversation_reset
        else:
            # Test and extension compatibility for simple rule-specific clients.
            suggestion = result
            conversation_id = data.conversation_id
            conversation_reset = False
        draft = merge_draft(data.current_form, suggestion.patch)
        # 重新取得权限，避免请求期间权限变更；不信任模型返回的ID。
        RuleCandidateTools(authorization, db).validate_draft(draft)
        return {
            "conversation_id": conversation_id,
            "conversation_reset": conversation_reset,
            "reply": suggestion.reply,
            "form_data": draft.model_dump(exclude_none=True),
        }


rule_agent_service = RuleAgentService()
