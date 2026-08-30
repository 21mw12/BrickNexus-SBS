"""One-shot MQTT publishing transport."""

from __future__ import annotations

from dataclasses import dataclass

import paho.mqtt.client as mqtt

from .MQTTClient import (
    MQTTClientFactory,
    MQTTConnectionOptions,
    MQTTTransportError,
    close_mqtt_client,
    mqtt_result_code,
)


@dataclass(frozen=True, slots=True)
class MQTTPublishResult:
    message_id: int
    published: bool = True


class MQTTPublisher:
    def __init__(self, client_factory: MQTTClientFactory | None = None) -> None:
        self._client_factory = client_factory or MQTTClientFactory()

    def publish_once(
        self,
        options: MQTTConnectionOptions,
        *,
        topic: str,
        payload: str | bytes,
        qos: int,
        retain: bool,
        timeout: float,
    ) -> MQTTPublishResult:
        client = self._client_factory.create(
            options, temporary=True, purpose="publisher"
        )
        loop_started = False
        try:
            connect_result = client.connect(
                options.host, options.port, keepalive=options.keepalive
            )
            if connect_result is not None and mqtt_result_code(connect_result) != 0:
                raise MQTTTransportError(f"MQTT connect failed: rc={connect_result}")
            client.loop_start()
            loop_started = True
            published = client.publish(topic, payload, qos=qos, retain=retain)
            published.wait_for_publish(timeout=timeout)
            if mqtt_result_code(published.rc) != mqtt.MQTT_ERR_SUCCESS:
                raise MQTTTransportError(f"MQTT publish failed: rc={published.rc}")
            is_published = getattr(published, "is_published", None)
            if callable(is_published) and not is_published():
                raise MQTTTransportError("MQTT publish timed out")
            return MQTTPublishResult(message_id=published.mid)
        except MQTTTransportError:
            raise
        except Exception as exc:
            raise MQTTTransportError(str(exc)) from exc
        finally:
            close_mqtt_client(client, loop_started=loop_started)
