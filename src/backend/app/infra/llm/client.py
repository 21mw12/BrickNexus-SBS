"""Provider-specific LangChain clients and normalized model calls."""

import asyncio
import importlib
import sys
from dataclasses import dataclass
from time import perf_counter
from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.middleware.LogRecorder import get_logger


logger = get_logger()
OutputModel = TypeVar("OutputModel", bound=BaseModel)


class LLMClientConfigurationError(RuntimeError):
    """The configured provider cannot be constructed in this process."""


@dataclass(frozen=True)
class LLMRuntimeConfig:
    llm_id: str | None
    service_type: str
    service_name: str
    content: dict[str, Any]


class LLMClientFactory:
    PROBE_TIMEOUT_SECONDS = 15

    @staticmethod
    def _dependency(module_name: str, package_name: str):
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            logger.exception(
                "模型依赖导入失败 package=%s module=%s python=%s missing=%s",
                package_name,
                module_name,
                sys.executable,
                exc.name,
            )
            if exc.name == module_name or (exc.name or "").startswith(f"{module_name}."):
                raise LLMClientConfigurationError(
                    f"模型依赖未安装：{package_name}（当前 Python：{sys.executable}）"
                ) from exc
            raise LLMClientConfigurationError(
                f"模型依赖加载失败：{package_name}（缺少 {exc.name}，当前 Python：{sys.executable}）"
            ) from exc
        except ImportError as exc:
            logger.exception(
                "模型依赖加载异常 package=%s module=%s python=%s",
                package_name,
                module_name,
                sys.executable,
            )
            raise LLMClientConfigurationError(
                f"模型依赖加载失败：{package_name}（当前 Python：{sys.executable}）"
            ) from exc

    @classmethod
    def create(cls, runtime: LLMRuntimeConfig, timeout_seconds: int = 90):
        content = runtime.content
        if runtime.service_type == "ollama":
            module = cls._dependency("langchain_ollama", "langchain-ollama")
            return module.ChatOllama(
                base_url=content["base_url"],
                model=content["model_name"],
                num_ctx=content["num_ctx"],
                temperature=0,
            )
        module = cls._dependency("langchain_openai", "langchain-openai")
        return module.ChatOpenAI(
            base_url=content["base_url"],
            model=content["model_name"],
            api_key=content["api_key"],
            max_tokens=content["max_tokens"],
            timeout=timeout_seconds,
            max_retries=0,
            temperature=0,
        )

    @classmethod
    async def invoke(cls, runtime: LLMRuntimeConfig, messages, timeout_seconds: int = 90):
        model = cls.create(runtime, timeout_seconds)
        return await asyncio.wait_for(model.ainvoke(messages), timeout=timeout_seconds)

    @classmethod
    def bind_tools(cls, model, definitions):
        return model.bind_tools(definitions)

    @classmethod
    def structured(cls, model, output_schema: type[OutputModel]):
        return model.with_structured_output(output_schema, method="function_calling")

    @classmethod
    async def probe(cls, runtime: LLMRuntimeConfig) -> dict[str, Any]:
        started = perf_counter()
        try:
            response = await cls.invoke(
                runtime,
                "这是一次连通性测试，请只回复 OK。",
                cls.PROBE_TIMEOUT_SECONDS,
            )
            content = getattr(response, "content", None)
            if content is None or (isinstance(content, str) and not content.strip()):
                raise ValueError("empty model response")
            return {
                "connected": True,
                "latency_ms": round((perf_counter() - started) * 1000),
                "service_type": runtime.service_type,
                "model_name": runtime.content["model_name"],
                "message": "模型连接成功",
            }
        except Exception as exc:
            return {
                "connected": False,
                "latency_ms": round((perf_counter() - started) * 1000),
                "service_type": runtime.service_type,
                "model_name": runtime.content.get("model_name", ""),
                "error_code": cls._error_code(exc),
                "message": cls._error_message(exc),
            }

    @staticmethod
    def _status_code(exc: Exception) -> int | None:
        direct = getattr(exc, "status_code", None)
        if isinstance(direct, int):
            return direct
        response = getattr(exc, "response", None)
        value = getattr(response, "status_code", None)
        return value if isinstance(value, int) else None

    @classmethod
    def _error_code(cls, exc: Exception) -> str:
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or "timeout" in type(exc).__name__.lower():
            return "timeout"
        status = cls._status_code(exc)
        if status in {401, 403}:
            return "authentication_failed"
        if status == 404:
            return "model_not_found"
        if isinstance(exc, LLMClientConfigurationError):
            return "dependency_missing"
        return "provider_error"

    @classmethod
    def _error_message(cls, exc: Exception) -> str:
        messages = {
            "timeout": "模型服务连接超时",
            "authentication_failed": "模型服务鉴权失败",
            "model_not_found": "模型或接口地址不存在",
            "dependency_missing": str(exc),
            "provider_error": "模型服务请求失败",
        }
        return messages[cls._error_code(exc)]


llm_client_factory = LLMClientFactory()
