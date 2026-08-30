"""Resolve normalized channel rows into the legacy-shaped collector runtime input."""

from dataclasses import dataclass
from urllib.parse import urljoin

from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.channel.repository.models.ChannelHttp import ChannelHttp
from app.domain.channel.repository.models.ChannelMqtt import ChannelMqtt
from app.domain.channel.repository.models.Request import Request
from .ChannelCipher import ChannelCipher


@dataclass(frozen=True)
class ResolvedRequest:
    request_id: str
    request_type: str
    request_info: dict
    time_json_path: str | None
    time_parse: str | None
    is_active: bool


def join_http_url(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


class ChannelResolver:
    @staticmethod
    def get_channel(db: Session, channel_type: str, channel_id: str):
        model = ChannelMqtt if channel_type == "mqtt" else ChannelHttp if channel_type == "http" else None
        if model is None:
            raise ValidationError("type must be 'mqtt' or 'http'")
        channel = db.get(model, channel_id)
        if channel is None:
            raise ValidationError(f"{channel_type} channel not found")
        return channel

    @classmethod
    def resolve_request(cls, db: Session, request: Request) -> ResolvedRequest:
        channel = cls.get_channel(db, request.type, request.channel_id)
        if request.type == "http":
            headers = dict(channel.default_headers or {})
            headers.update(request.http_header or {})
            info = {
                "method": request.http_method,
                "url": join_http_url(channel.base_url, request.http_path),
                "headers": headers,
                "params": request.http_params,
                "body": request.http_body,
                "timeout_seconds": channel.default_timeout,
                "interval_seconds": request.interval_seconds,
            }
        else:
            info = {
                "channel_id": channel.channel_mqtt_id,
                "address": f"{channel.broker_host}:{channel.broker_port}",
                "client_id": channel.client_id,
                "username": channel.username,
                "password": ChannelCipher.decrypt(channel.password),
                "qos": channel.qos,
                "connect_timeout_seconds": channel.connect_timeout,
                "data_timeout": channel.data_timeout,
                "topic": request.mqtt_topic,
                # MQTT always keeps the last batch in each configured period.
                "storage_interval_seconds": request.interval_seconds,
            }
        return ResolvedRequest(
            request_id=request.request_id,
            request_type=request.type,
            request_info=info,
            time_json_path=request.time_json_path,
            time_parse=request.time_format,
            is_active=request.status,
        )
