"""Generic model/tool loop with short-lived conversational context."""

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.infra.llm import LLMClientConfigurationError, LLMRuntimeConfig, llm_client_factory
from .store import ConversationUnavailableError, conversation_store


@dataclass(frozen=True)
class ConversationRunResult:
    conversation_id: str
    conversation_reset: bool
    output: BaseModel


class ConversationService:
    MAX_TOOL_CALLS = 6

    def __init__(self, store=None, client_factory=None):
        self.store = store or conversation_store
        self.client_factory = client_factory or llm_client_factory

    async def run(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
        agent_type: str,
        user_message: str,
        current_context: dict[str, Any],
        system_prompt: str,
        output_schema: type[BaseModel],
        runtime: LLMRuntimeConfig,
        tools: list[dict[str, Any]] | None = None,
        tool_executor=None,
        output_validator=None,
        timeout_seconds: int = 90,
    ) -> ConversationRunResult:
        try:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
        except ImportError as exc:
            raise LLMClientConfigurationError("模型依赖未安装：langchain-core") from exc

        document, reset = self.store.load_or_create(user_id, conversation_id, agent_type)
        model = self.client_factory.create(runtime, timeout_seconds)
        messages = [SystemMessage(content=system_prompt)]
        for turn in document.get("turns", []):
            messages.append(HumanMessage(content=turn.get("user", "")))
            messages.append(AIMessage(content=json.dumps(turn.get("assistant", {}), ensure_ascii=False)))
        messages.append(HumanMessage(content=json.dumps({
            "message": user_message,
            "current_context": current_context,
            "instruction": "current_context 是当前权威状态；历史内容仅用于理解指代，不得覆盖用户手动修改。",
        }, ensure_ascii=False)))

        if tools:
            if tool_executor is None:
                raise ValueError("配置了工具但缺少工具执行器")
            tool_model = self.client_factory.bind_tools(model, tools)
            calls = 0
            while calls < self.MAX_TOOL_CALLS:
                response = await asyncio.wait_for(
                    tool_model.ainvoke(messages), timeout=timeout_seconds
                )
                messages.append(response)
                if not response.tool_calls:
                    break
                for call in response.tool_calls:
                    if calls >= self.MAX_TOOL_CALLS:
                        result = {"error": "查询次数已达上限，请使用已有候选或提示用户缩小范围"}
                    else:
                        calls += 1
                        try:
                            result = tool_executor(call["name"], call["args"])
                        except (ValueError, PermissionError):
                            result = {"error": "查询参数无效或对象不可访问，请更正条件"}
                    messages.append(ToolMessage(
                        content=json.dumps(result, ensure_ascii=False),
                        tool_call_id=call["id"],
                    ))

        messages.append(HumanMessage(content="根据当前需求、权威状态和查询结果输出最终结构化结果。"))
        structured = self.client_factory.structured(model, output_schema)
        output = None
        for attempt in range(2):
            try:
                candidate = await asyncio.wait_for(
                    structured.ainvoke(messages), timeout=timeout_seconds
                )
                if candidate is None:
                    raise ValueError("empty structured output")
                output = output_schema.model_validate(candidate)
                if output_validator is not None:
                    output_validator(output)
                break
            except (ValueError, TypeError):
                if attempt:
                    raise ValueError("模型返回结构无效，请重新描述需求")
                messages.append(HumanMessage(content="上一次输出结构无效，请严格按给定 Schema 输出，不附加字段。"))
        assert output is not None
        self.store.append(document, user_message, output.model_dump(exclude_none=True))
        return ConversationRunResult(document["conversation_id"], reset, output)

    def close(self, user_id: str, conversation_id: str) -> bool:
        return self.store.delete(user_id, conversation_id)


conversation_service = ConversationService()
