import asyncio
import json

import pytest
from pydantic import BaseModel

from app.domain.agent.conversation.service import ConversationService
from app.domain.agent.conversation.store import ConversationStore
from app.infra.llm import LLMRuntimeConfig


class FakePipeline:
    def __init__(self, data): self.data, self.commands = data, []
    def set(self, key, value, ex=None): self.commands.append((key, value)); return self
    def execute(self):
        for key, value in self.commands: self.data[key] = value


class FakeRedis:
    def __init__(self): self.data = {}
    def get(self, key): return self.data.get(key)
    def pipeline(self, transaction=True): return FakePipeline(self.data)
    def delete(self, *keys):
        for key in keys: self.data.pop(key, None)


def test_store_isolates_users_resets_expired_and_trims(monkeypatch):
    module = __import__("app.domain.agent.conversation.store", fromlist=["unused"])
    backend = FakeRedis()
    monkeypatch.setattr(module, "redis_manager", backend)
    store = ConversationStore()
    document, reset = store.load_or_create("u1", None, "rule")
    assert not reset
    conversation_id = document["conversation_id"]
    with pytest.raises(PermissionError):
        store.load_or_create("u2", conversation_id, "rule")
    for index in range(12):
        store.append(document, f"q{index}", {"reply": "x"})
    assert len(document["turns"]) == 10
    backend.data.pop(store.key("u1", conversation_id))
    replacement, reset = store.load_or_create("u1", conversation_id, "rule")
    assert reset and replacement["conversation_id"] != conversation_id


class Output(BaseModel):
    reply: str
    value: int


class MemoryStore:
    def __init__(self): self.document = None
    def load_or_create(self, user_id, conversation_id, agent_type):
        if self.document is None:
            self.document = {"conversation_id": "cid", "user_id": user_id, "agent_type": agent_type, "turns": []}
        return self.document, False
    def append(self, document, user_message, assistant_output):
        document["turns"].append({"user": user_message, "assistant": assistant_output})


class FakeResponse:
    tool_calls = []


class Structured:
    async def ainvoke(self, messages):
        self.messages = messages
        return Output(reply="ok", value=2)


class Model:
    async def ainvoke(self, messages): return FakeResponse()


class Factory:
    def __init__(self): self.structured_model = Structured()
    def create(self, runtime, timeout): return Model()
    def bind_tools(self, model, definitions): return model
    def structured(self, model, schema): return self.structured_model


def test_service_reuses_history_without_storing_tool_results():
    store, factory = MemoryStore(), Factory()
    service = ConversationService(store, factory)
    runtime = LLMRuntimeConfig(None, "ollama", "test", {})
    first = asyncio.run(service.run(user_id="u", conversation_id=None, agent_type="rule",
        user_message="第一次", current_context={"value": 1}, system_prompt="system",
        output_schema=Output, runtime=runtime))
    second = asyncio.run(service.run(user_id="u", conversation_id=first.conversation_id, agent_type="rule",
        user_message="改一下", current_context={"value": 2}, system_prompt="system",
        output_schema=Output, runtime=runtime))
    assert second.conversation_id == "cid"
    contents = [getattr(message, "content", "") for message in factory.structured_model.messages]
    assert "第一次" in contents
    assert any('"value": 2' in content for content in contents)
    assert "tool_call_id" not in json.dumps(store.document, ensure_ascii=False)
