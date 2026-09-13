"""Rule-specific adapter for the shared conversation runtime."""

import json

from . import config
from .prompts import SYSTEM_PROMPT
from .schema import FormFields, ComparisonForm, ModelSuggestion, SearchQuery
from .tools import TOOL_DESCRIPTIONS
from app.common.validators import ValidationError
from app.domain.agent.conversation import conversation_service
from app.domain.settings.service import llm_config_service
from app.infra.llm import LLMClientConfigurationError


class ModelConfigurationError(RuntimeError):
    pass


class RuleModelClient:
    async def suggest(self, message, draft, tools, *, user_id, conversation_id=None):
        from .service import merge_draft
        try:
            runtime = llm_config_service.active_runtime(tools.db)
        except ValidationError as exc:
            raise ModelConfigurationError(str(exc)) from exc
        definitions = [{"type": "function", "function": {"name": name,
            "description": description, "parameters": SearchQuery.model_json_schema()}}
            for name, description in TOOL_DESCRIPTIONS.items()]
        try:
            result = await conversation_service.run(
                user_id=user_id,
                conversation_id=conversation_id,
                agent_type="rule",
                user_message=message,
                current_context={
                    "current_form": draft.model_dump(exclude_none=True),
                    "selected_objects": tools.describe_current(draft),
                },
                system_prompt=SYSTEM_PROMPT + "\n字段结构：" + json.dumps({
                    "form": FormFields.model_json_schema(),
                    "comparison": ComparisonForm.model_json_schema(),
                }, ensure_ascii=False),
                output_schema=ModelSuggestion,
                runtime=runtime,
                tools=definitions,
                tool_executor=tools.dispatch,
                output_validator=lambda output: merge_draft(draft, output.patch),
                timeout_seconds=config.REQUEST_TIMEOUT_SECONDS,
            )
        except LLMClientConfigurationError as exc:
            raise ModelConfigurationError(str(exc)) from exc
        return result
