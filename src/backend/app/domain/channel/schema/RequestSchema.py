"""Request API input schemas for the split channel model."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _RequestCommon(_StrictSchema):
    name: str = Field(min_length=1, max_length=20)
    channel_id: str = Field(min_length=1, max_length=100)
    interval_seconds: int = Field(default=60, gt=0)
    time_json_path: str | None = Field(default=None, max_length=200)
    time_format: str | None = Field(default=None, max_length=50)


class RequestAddSchema(_RequestCommon):
    type: Literal["mqtt", "http"]
    mqtt_topic: str | None = Field(default=None, min_length=1, max_length=30)
    http_method: Literal["GET", "POST"] | None = None
    http_path: str | None = Field(default=None, min_length=1, max_length=100)
    http_header: dict[str, str] | None = None
    http_params: dict | None = None
    http_body: dict | None = None

    @model_validator(mode="after")
    def validate_method_payload(self):
        if self.type == "mqtt":
            if not self.mqtt_topic:
                raise ValueError("mqtt_topic is required for MQTT request")
            if any(value is not None for value in (self.http_method, self.http_path, self.http_header, self.http_params, self.http_body)):
                raise ValueError("MQTT request cannot configure HTTP fields")
            return self
        if not self.http_method or not self.http_path:
            raise ValueError("http_method and http_path are required for HTTP request")
        if self.mqtt_topic is not None:
            raise ValueError("HTTP request cannot configure mqtt_topic")
        if self.http_method == "GET" and self.http_body is not None:
            raise ValueError("GET request cannot configure http_body")
        if self.http_method == "POST" and self.http_params is not None:
            raise ValueError("POST request cannot configure http_params")
        return self

class RequestEditSchema(_StrictSchema):
    name: str | None = Field(default=None, min_length=1, max_length=20)
    type: Literal["mqtt", "http"] | None = None
    channel_id: str | None = Field(default=None, min_length=1, max_length=100)
    interval_seconds: int | None = Field(default=None, gt=0)
    time_json_path: str | None = Field(default=None, max_length=200)
    time_format: str | None = Field(default=None, max_length=50)
    mqtt_topic: str | None = Field(default=None, min_length=1, max_length=30)
    http_method: Literal["GET", "POST"] | None = None
    http_path: str | None = Field(default=None, min_length=1, max_length=100)
    http_header: dict[str, str] | None = None
    http_params: dict | None = None
    http_body: dict | None = None


class RequestQuerySchema(_StrictSchema):
    name: str | None = Field(default=None, max_length=20)
    type: Literal["mqtt", "http"] | None = None
    status: bool | None = None
