"""规则适配器与共享对话运行时集成测试；不请求外部模型。"""

import asyncio

import pytest

from app.domain.agent.rule.model import RuleModelClient
from app.domain.agent.rule.schema import RuleFormDraft
from app.domain.settings.service.LLMClientFactory import LLMRuntimeConfig


class MemoryConversationStore:
    def load_or_create(self, user_id, conversation_id, agent_type):
        return {"conversation_id": conversation_id or "00000000-0000-0000-0000-000000000001",
                "user_id": user_id, "agent_type": agent_type, "turns": []}, False

    def append(self, document, user_message, assistant_output):
        document["turns"].append({"user": user_message, "assistant": assistant_output})


class ToolResponse:
    def __init__(self, tool_calls=None):
        self.tool_calls = tool_calls or []
        self.content = ""


class ToolModel:
    def __init__(self): self.calls = 0
    async def ainvoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            return ToolResponse([{"id": "call-1", "name": "search_points", "args": {"keyword": "二氧化碳"}}])
        return ToolResponse()


class StructuredModel:
    def __init__(self, invalid_first): self.invalid_first, self.calls = invalid_first, 0
    async def ainvoke(self, messages):
        self.calls += 1
        fields = {"invalid_field": 1} if self.invalid_first and self.calls == 1 else {"trigger_duration": 600}
        return {"reply": "已调整持续时间", "patch": {"form": fields}}


class FakeFactory:
    def __init__(self, invalid_first):
        self.tool_model = ToolModel()
        self.structured_model = StructuredModel(invalid_first)
    def create(self, runtime, timeout): return object()
    def bind_tools(self, model, definitions): return self.tool_model
    def structured(self, model, schema): return self.structured_model


@pytest.mark.parametrize("invalid_first", [False, True])
def test_tools_and_structured_repair(monkeypatch, invalid_first):
    model_module = __import__("app.domain.agent.rule.model", fromlist=["unused"])
    runtime = LLMRuntimeConfig(None, "vllm", "test", {
        "base_url": "https://example.invalid/v1", "model_name": "example-model",
        "api_key": "test-placeholder", "model_type": "chat", "max_tokens": 4096,
    })
    factory = FakeFactory(invalid_first)
    monkeypatch.setattr(model_module.llm_config_service, "active_runtime", lambda _db: runtime)
    monkeypatch.setattr(model_module.conversation_service, "store", MemoryConversationStore())
    monkeypatch.setattr(model_module.conversation_service, "client_factory", factory)
    queries = []

    class Tools:
        db = object()
        def describe_current(self, draft): return {}
        def dispatch(self, name, arguments):
            queries.append((name, arguments))
            return {"items": [], "has_more": False}

    result = asyncio.run(RuleModelClient().suggest(
        "持续十分钟", RuleFormDraft(), Tools(), user_id="user"
    ))
    assert result.output.patch.form == {"trigger_duration": 600}
    assert queries == [("search_points", {"keyword": "二氧化碳"})]
    assert factory.structured_model.calls == (2 if invalid_first else 1)
