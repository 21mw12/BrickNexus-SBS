"""Control configuration API schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _ControlCommon(_StrictSchema):
    name: str = Field(min_length=1, max_length=30)
    channel_id: str = Field(min_length=1, max_length=100)
    asset_type: Literal["terminal", "sensor"]
    asset_id: str = Field(min_length=1, max_length=100)


class ControlAddSchema(_ControlCommon):
    type: Literal["mqtt", "http"]
    mqtt_topic: str | None = Field(default=None, min_length=1, max_length=30)
    mqtt_retained: bool | None = None
    mqtt_payload: str | None = Field(default=None, min_length=1)
    http_method: Literal["GET", "POST"] | None = None
    http_path: str | None = Field(default=None, min_length=1, max_length=100)
    http_header: dict[str, str] | None = None
    http_params: dict | None = None
    http_body: dict | None = None

    @model_validator(mode="after")
    def validate_method_payload(self):
        if self.type == "mqtt":
            if not self.mqtt_topic or not self.mqtt_payload:
                raise ValueError("mqtt_topic and mqtt_payload are required")
            if any(value is not None for value in (self.http_method, self.http_path, self.http_header, self.http_params, self.http_body)):
                raise ValueError("MQTT control cannot configure HTTP fields")
            if self.mqtt_retained is None:
                self.mqtt_retained = False
            return self
        if not self.http_method or not self.http_path:
            raise ValueError("http_method and http_path are required")
        if any(value is not None for value in (self.mqtt_topic, self.mqtt_retained, self.mqtt_payload)):
            raise ValueError("HTTP control cannot configure MQTT fields")
        if self.http_method == "GET" and self.http_body is not None:
            raise ValueError("GET control cannot configure http_body")
        if self.http_method == "POST" and self.http_params is not None:
            raise ValueError("POST control cannot configure http_params")
        return self

class ControlEditSchema(_StrictSchema):
    name: str | None = Field(default=None, min_length=1, max_length=30)
    type: Literal["mqtt", "http"] | None = None
    channel_id: str | None = Field(default=None, min_length=1, max_length=100)
    asset_type: Literal["terminal", "sensor"] | None = None
    asset_id: str | None = Field(default=None, min_length=1, max_length=100)
    mqtt_topic: str | None = Field(default=None, min_length=1, max_length=30)
    mqtt_retained: bool | None = None
    mqtt_payload: str | None = Field(default=None, min_length=1)
    http_method: Literal["GET", "POST"] | None = None
    http_path: str | None = Field(default=None, min_length=1, max_length=100)
    http_header: dict[str, str] | None = None
    http_params: dict | None = None
    http_body: dict | None = None


class ControlQuerySchema(_StrictSchema):
    name: str | None = Field(default=None, max_length=30)
    type: Literal["mqtt", "http"] | None = None
    status: bool | None = None
    asset_type: Literal["terminal", "sensor"] | None = None
    asset_id: str | None = Field(default=None, max_length=100)
