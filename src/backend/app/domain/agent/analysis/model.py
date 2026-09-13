"""智能分析 Agent 对共享会话与活动模型配置的适配。"""

from app.common.validators import ValidationError
from app.domain.agent.conversation import conversation_service
from app.domain.settings.service import llm_config_service
from app.infra.llm import LLMClientConfigurationError
from . import config
from .prompts import build_system_prompt
from .schema import AnswerAgentOutput, ReportAgentOutput


class ModelConfigurationError(RuntimeError):
    pass


class AnalysisModelClient:
    async def respond(self, *, context, message, user_id, conversation_id=None):
        try:
            runtime = llm_config_service.active_runtime(context["db"])
        except ValidationError as exc:
            raise ModelConfigurationError(str(exc)) from exc

        snapshot = context["snapshot"]
        initial = not conversation_id
        output_schema = ReportAgentOutput if initial else AnswerAgentOutput
        user_message = message or "请根据当前分析摘要生成首次结构化解读。"
        current_context = {
            "analysis": snapshot,
            "response_contract": "首次结构化报告" if initial else "针对用户问题的纯文本回答",
        }
        try:
            return await conversation_service.run(
                user_id=user_id,
                conversation_id=conversation_id,
                agent_type="analysis",
                user_message=user_message,
                current_context=current_context,
                system_prompt=build_system_prompt(snapshot["analysis_type"], snapshot["algorithm"]["name"]),
                output_schema=output_schema,
                runtime=runtime,
                timeout_seconds=config.REQUEST_TIMEOUT_SECONDS,
            )
        except LLMClientConfigurationError as exc:
            raise ModelConfigurationError(str(exc)) from exc


analysis_model_client = AnalysisModelClient()
