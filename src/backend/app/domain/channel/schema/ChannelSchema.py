"""MQTT and HTTP channel API schemas."""

from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MqttChannelAddSchema(_StrictSchema):
    broker_host: str = Field(min_length=1, max_length=30)
    broker_port: int = Field(default=1883, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=20)
    password: str | None = Field(default=None, max_length=1024)
    qos: int = Field(default=1, ge=0, le=2)
    connect_timeout: int = Field(default=20, gt=0)
    data_timeout: int = Field(default=120, gt=0)


class MqttChannelEditSchema(_StrictSchema):
    broker_host: str | None = Field(default=None, min_length=1, max_length=30)
    broker_port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=20)
    # omitted means retain, explicit null means clear
    password: str | None = Field(default=None, max_length=1024)
    qos: int | None = Field(default=None, ge=0, le=2)
    connect_timeout: int | None = Field(default=None, gt=0)
    data_timeout: int | None = Field(default=None, gt=0)


class MqttChannelQuerySchema(_StrictSchema):
    broker_host: str | None = Field(default=None, max_length=30)
    username: str | None = Field(default=None, max_length=20)


def _validate_base_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute HTTP(S) URL")
    return value.rstrip("/")


class HttpChannelAddSchema(_StrictSchema):
    base_url: str = Field(min_length=1, max_length=200)
    default_headers: dict[str, str] | None = None
    default_timeout: int = Field(default=20, gt=0)

    _base_url = field_validator("base_url")(_validate_base_url)


class HttpChannelEditSchema(_StrictSchema):
    base_url: str | None = Field(default=None, min_length=1, max_length=200)
    default_headers: dict[str, str] | None = None
    default_timeout: int | None = Field(default=None, gt=0)

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value: str | None):
        return None if value is None else _validate_base_url(value)


class HttpChannelQuerySchema(_StrictSchema):
    base_url: str | None = Field(default=None, max_length=200)
