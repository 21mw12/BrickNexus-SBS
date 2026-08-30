"""Temporary MQTT subscription used by channel connectivity tests."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock

from .MQTTClient import (
    MQTTClientFactory,
    MQTTConnectionOptions,
    MQTTTransportError,
    close_mqtt_client,
    mqtt_result_code,
    subscribe_checked,
)


@dataclass(frozen=True, slots=True)
class MQTTProbeResult:
    connected: bool
    payload: bytes | None


class MQTTProbe:
    def __init__(self, client_factory: MQTTClientFactory | None = None) -> None:
        self._client_factory = client_factory or MQTTClientFactory()

    def receive_once(
        self,
        options: MQTTConnectionOptions,
        *,
        topic: str,
        qos: int,
        timeout: float,
    ) -> MQTTProbeResult:
        client = self._client_factory.create(
            options, temporary=True, purpose="probe"
        )
        completed = Event()
        state_lock = Lock()
        state: dict[str, object] = {
            "connected": False,
            "payload": None,
            "error": None,
        }

        def fail(error: Exception) -> None:
            with state_lock:
                state["error"] = error
            completed.set()

        def on_connect(mqtt_client, userdata, flags, rc, properties=None):
            if mqtt_result_code(rc) != 0:
                fail(MQTTTransportError(f"MQTT connect failed: rc={rc}"))
                return
            with state_lock:
                state["connected"] = True
            try:
                subscribe_checked(mqtt_client, topic, qos)
            except Exception as exc:
                fail(exc)

        def on_message(mqtt_client, userdata, message):
            with state_lock:
                if state["payload"] is None:
                    state["payload"] = bytes(message.payload)
            completed.set()

        client.on_connect = on_connect
        client.on_message = on_message
        loop_started = False
        try:
            connect_result = client.connect(
                options.host, options.port, keepalive=options.keepalive
            )
            if connect_result is not None and mqtt_result_code(connect_result) != 0:
                raise MQTTTransportError(f"MQTT connect failed: rc={connect_result}")
            client.loop_start()
            loop_started = True
            completed.wait(timeout)
            with state_lock:
                error = state["error"]
                connected = bool(state["connected"])
                payload = state["payload"]
            if error is not None:
                raise error
            if not connected:
                raise MQTTTransportError("MQTT connection timed out")
            return MQTTProbeResult(connected=True, payload=payload)
        except MQTTTransportError:
            raise
        except Exception as exc:
            raise MQTTTransportError(str(exc)) from exc
        finally:
            close_mqtt_client(client, loop_started=loop_started)
