import asyncio
import importlib
import sys
from inspect import signature
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.settings.repository.models import LLMConfig
from app.domain.settings.schema import LLMConfigAddSchema, LLMConfigEditSchema, LLMConfigTestSchema
from app.domain.settings.service.LLMConfigCipher import LLMConfigCipher
from app.domain.settings.service.LLMConfigService import LLMConfigService, LLMConnectivityError
from app.domain.settings.service.LLMClientFactory import LLMClientFactory, LLMRuntimeConfig
from app.infra.DB.SQLConnection import Base


service_module = importlib.import_module("app.domain.settings.service.LLMConfigService")


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[LLMConfig.__table__])
    with Session(engine) as session:
        yield session
    engine.dispose()


def openai_payload(name="DeepSeek"):
    return LLMConfigAddSchema.model_validate({
        "service_name": name,
        "service_type": "deepseek",
        "content": {
            "base_url": "https://api.deepseek.com",
            "api_key": "secret-key",
            "model_name": "deepseek-chat",
            "max_tokens": 4096,
        },
    })


def test_provider_schemas_are_strict_and_normalize_urls():
    ollama = LLMConfigAddSchema.model_validate({
        "service_name": " Local ",
        "service_type": "ollama",
        "content": {"base_url": "http://localhost:11434/", "model_name": "qwen3"},
    })
    assert ollama.service_name == "Local"
    assert ollama.content["base_url"] == "http://localhost:11434"
    assert ollama.content["num_ctx"] == 8192
    with pytest.raises(PydanticValidationError):
        LLMConfigAddSchema.model_validate({
            "service_name": "bad", "service_type": "ollama",
            "content": {"base_url": "http://localhost", "model_name": "qwen", "max_tokens": 10},
        })


def test_secret_is_encrypted_masked_and_preserved_on_edit(db):
    service = LLMConfigService()
    result = service.add(openai_payload(), db)
    row = db.get(LLMConfig, result["llm_id"])
    assert row.content["api_key"] != "secret-key"
    assert LLMConfigCipher.decrypt(row.content["api_key"]) == "secret-key"
    assert result["content"]["api_key_configured"] is True
    assert "api_key" not in result["content"]

    edit = LLMConfigEditSchema.model_validate({
        "service_name": "Updated", "service_type": "deepseek",
        "content": {"base_url": "https://api.deepseek.com", "model_name": "deepseek-chat", "max_tokens": 1024},
    })
    asyncio.run(service.edit(row.llm_id, edit, db))
    assert LLMConfigCipher.decrypt(row.content["api_key"]) == "secret-key"


def test_missing_key_is_allowed_by_draft_but_rejected_by_service(db):
    draft = LLMConfigAddSchema.model_validate({
        "service_name": "vLLM", "service_type": "vllm",
        "content": {"base_url": "http://localhost:8000/v1", "model_name": "qwen"},
    })
    with pytest.raises(ValidationError, match="API Key"):
        LLMConfigService.add(draft, db)


def test_activation_failure_keeps_previous_active(db, monkeypatch):
    service = LLMConfigService()
    first = service.add(openai_payload("one"), db)
    second = service.add(openai_payload("two"), db)
    db.get(LLMConfig, first["llm_id"]).is_use = True
    db.commit()

    async def failed(*_):
        return {"connected": False, "message": "模型服务连接超时", "error_code": "timeout"}

    monkeypatch.setattr(service_module.llm_client_factory, "probe", failed)
    with pytest.raises(LLMConnectivityError):
        asyncio.run(service.activate(second["llm_id"], db))
    db.rollback()
    assert db.get(LLMConfig, first["llm_id"]).is_use is True
    assert db.get(LLMConfig, second["llm_id"]).is_use is False


def test_activation_switches_atomically_and_active_cannot_be_deleted(db, monkeypatch):
    service = LLMConfigService()
    first = service.add(openai_payload("one"), db)
    second = service.add(openai_payload("two"), db)
    db.get(LLMConfig, first["llm_id"]).is_use = True
    db.commit()

    async def connected(runtime):
        return {"connected": True, "message": "模型连接成功", "model_name": runtime.content["model_name"]}

    monkeypatch.setattr(service_module.llm_client_factory, "probe", connected)
    asyncio.run(service.activate(second["llm_id"], db))
    db.commit()
    assert db.get(LLMConfig, first["llm_id"]).is_use is False
    assert db.get(LLMConfig, second["llm_id"]).is_use is True
    with pytest.raises(ValidationError, match="不能删除"):
        service.drop(second["llm_id"], db)


def test_saved_test_override_reuses_existing_secret(db, monkeypatch):
    service = LLMConfigService()
    item = service.add(openai_payload(), db)
    seen = {}

    async def connected(runtime):
        seen.update(runtime.content)
        return {"connected": True}

    monkeypatch.setattr(service_module.llm_client_factory, "probe", connected)
    override = LLMConfigTestSchema.model_validate({
        "service_type": "deepseek",
        "content": {"base_url": "https://other.example/v1", "model_name": "other", "max_tokens": 100},
    })
    asyncio.run(service.test_saved(item["llm_id"], db, override))
    assert seen["api_key"] == "secret-key"
    assert seen["model_name"] == "other"


@pytest.mark.parametrize("service_type", ["vllm", "deepseek"])
def test_openai_compatible_factory_uses_provider_settings(monkeypatch, service_type):
    captured = {}
    monkeypatch.setitem(sys.modules, "langchain_openai", SimpleNamespace(
        ChatOpenAI=lambda **kwargs: captured.update(kwargs) or object()
    ))
    runtime = LLMRuntimeConfig(None, service_type, "provider", {
        "base_url": "https://example.test/v1", "api_key": "key",
        "model_name": "chat", "model_type": "chat", "max_tokens": 321,
    })
    LLMClientFactory.create(runtime, 12)
    assert captured["base_url"] == "https://example.test/v1"
    assert captured["api_key"] == "key"
    assert captured["max_tokens"] == 321
    assert captured["timeout"] == 12


def test_ollama_factory_uses_native_context_setting(monkeypatch):
    captured = {}
    monkeypatch.setitem(sys.modules, "langchain_ollama", SimpleNamespace(
        ChatOllama=lambda **kwargs: captured.update(kwargs) or object()
    ))
    runtime = LLMRuntimeConfig(None, "ollama", "local", {
        "base_url": "http://localhost:11434", "model_name": "qwen3",
        "model_type": "chat", "num_ctx": 16384,
    })
    LLMClientFactory.create(runtime)
    assert captured["base_url"] == "http://localhost:11434"
    assert captured["num_ctx"] == 16384
    assert "api_key" not in captured


def test_settings_endpoints_require_settings_page(monkeypatch):
    import app.domain.common.AuthDecorator as auth_decorator
    api = importlib.import_module("app.domain.settings.api.LLMConfigAPI")
    captured = []
    monkeypatch.setattr(
        auth_decorator, "check_page_permission",
        lambda _token, pages: captured.append(tuple(pages)) or True,
    )
    for endpoint in (api.list_llm_configs, api.add_llm_config, api.test_llm_draft):
        dependency = signature(endpoint).parameters["_auth"].default.dependency
        dependency("Bearer token")
    assert captured == [("settings",), ("settings",), ("settings",)]


def test_connectivity_http_status_reflects_result():
    import json
    api = importlib.import_module("app.domain.settings.api.LLMConfigAPI")
    success = api._connectivity_result({"connected": True, "message": "ok"})
    failure = api._connectivity_result({
        "connected": False, "error_code": "dependency_missing",
        "message": "模型依赖未安装：langchain-ollama",
    })
    assert success.status_code == 200
    assert failure.status_code == 502
    body = json.loads(failure.body)
    assert body["code"] == 502
    assert body["data"]["connected"] is False
