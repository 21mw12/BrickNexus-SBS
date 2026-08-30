"""MQTT client primitives shared by domain services.

This module intentionally knows nothing about SQL models, application settings, or
collection/control semantics. Callers resolve those concerns before constructing
``MQTTConnectionOptions``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import paho.mqtt.client as mqtt


class MQTTTransportError(RuntimeError):
    """An MQTT connection, subscription, or publish operation failed."""


@dataclass(frozen=True, slots=True)
class MQTTConnectionOptions:
    """Plain connection parameters for an MQTT client."""

    host: str
    port: int = 1883
    client_id: str | None = None
    username: str | None = None
    password: str | None = field(default=None, repr=False)
    keepalive: int = 60


def mqtt_result_code(value: Any) -> int:
    """Normalize Paho integer and ReasonCode values."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return 1


def subscribe_checked(client: Any, topic: str, qos: int) -> Any:
    """Subscribe and raise a transport error for a non-success Paho result."""

    result = client.subscribe(topic, qos=qos)
    result_code = result[0] if isinstance(result, tuple) else getattr(result, "rc", result)
    if mqtt_result_code(result_code) != 0:
        raise MQTTTransportError(f"MQTT subscribe failed: rc={result_code}")
    return result


def close_mqtt_client(client: Any, *, loop_started: bool = True) -> None:
    """Best-effort disconnect and network-loop cleanup."""

    try:
        client.disconnect()
    except Exception:
        pass
    if loop_started:
        try:
            client.loop_stop()
        except Exception:
            pass


class MQTTClientFactory:
    """Create consistently configured Paho clients."""

    def __init__(self, mqtt_module: Any = mqtt) -> None:
        self._mqtt = mqtt_module

    @staticmethod
    def temporary_client_id(base_client_id: str | None, purpose: str) -> str:
        base = base_client_id or "smart-building"
        return f"{base}-{purpose}-{uuid.uuid4().hex[:12]}"

    def create(
        self,
        options: MQTTConnectionOptions,
        *,
        temporary: bool = False,
        purpose: str = "client",
    ) -> Any:
        client_id = options.client_id
        if temporary or not client_id:
            client_id = self.temporary_client_id(client_id, purpose)

        if hasattr(self._mqtt, "CallbackAPIVersion"):
            client = self._mqtt.Client(
                callback_api_version=self._mqtt.CallbackAPIVersion.VERSION1,
                client_id=client_id,
                clean_session=True,
            )
        else:
            client = self._mqtt.Client(client_id=client_id, clean_session=True)

        if options.username is not None:
            client.username_pw_set(options.username, options.password)
        return client
