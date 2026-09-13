from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ServiceType = Literal["vllm", "ollama", "deepseek"]


class _StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base_url cannot contain credentials, query, or fragment")
    return value


class OpenAICompatibleContent(_StrictSchema):
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=4096)
    model_name: str = Field(min_length=1, max_length=200)
    model_type: Literal["chat"] = "chat"
    max_tokens: int = Field(default=4096, ge=1, le=1048576)

    _normalize_url = field_validator("base_url")(_base_url)

    @field_validator("api_key", "model_name")
    @classmethod
    def strip_values(cls, value):
        return value.strip() if isinstance(value, str) else value


class OllamaContent(_StrictSchema):
    base_url: str = Field(min_length=1, max_length=500)
    model_name: str = Field(min_length=1, max_length=200)
    model_type: Literal["chat"] = "chat"
    num_ctx: int = Field(default=8192, ge=1, le=1048576)

    _normalize_url = field_validator("base_url")(_base_url)

    @field_validator("model_name")
    @classmethod
    def strip_model(cls, value: str):
        return value.strip()


def validate_provider_content(service_type: ServiceType, content: dict[str, Any]) -> dict:
    model = OllamaContent if service_type == "ollama" else OpenAICompatibleContent
    return model.model_validate(content).model_dump(exclude_none=True)


class LLMConfigBaseSchema(_StrictSchema):
    service_name: str = Field(min_length=1, max_length=50)
    service_type: ServiceType
    content: dict[str, Any]

    @field_validator("service_name")
    @classmethod
    def strip_name(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("service_name cannot be empty")
        return value

    @model_validator(mode="after")
    def validate_content(self):
        self.content = validate_provider_content(self.service_type, self.content)
        return self


class LLMConfigAddSchema(LLMConfigBaseSchema):
    pass


class LLMConfigEditSchema(LLMConfigBaseSchema):
    pass


class LLMConfigTestSchema(_StrictSchema):
    service_type: ServiceType
    content: dict[str, Any]

    @model_validator(mode="after")
    def validate_content(self):
        self.content = validate_provider_content(self.service_type, self.content)
        return self


class LLMConfigQuerySchema(_StrictSchema):
    service_name: str | None = Field(default=None, max_length=50)
    service_type: ServiceType | None = None
    is_use: bool | None = None

