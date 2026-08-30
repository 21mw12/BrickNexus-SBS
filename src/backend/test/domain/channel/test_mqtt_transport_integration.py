"""Channel services delegate MQTT transport work to app.infra.MQTT."""

import importlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain import *  # noqa: F401,F403
from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.repository.models.AssetSensor import AssetSensor
from app.domain.channel.schema.ChannelSchema import MqttChannelAddSchema
from app.domain.channel.schema.ControlSchema import ControlAddSchema
from app.domain.channel.service.ChannelService import ChannelService
from app.domain.channel.service.ControlService import ControlService
from app.domain.channel.service.RequestService import RequestService
from app.infra.DB.SQLConnection import Base
from app.infra.MQTT import MQTTPublishResult, MQTTProbeResult, MQTTTransportError


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_mqtt_control_uses_infra_publisher(db: Session, monkeypatch):
    db.add(Asset(asset_id="sensor-1", asset_type="sensor", name="Sensor", is_use=True))
    db.add(AssetSensor(asset_id="sensor-1", is_online=False))
    db.flush()
    channel = ChannelService.add_mqtt(
        db,
        MqttChannelAddSchema(
            broker_host="mqtt.test", username="user", password="secret", qos=2
        ),
    )
    control = ControlService.add(
        db,
        ControlAddSchema(
            name="switch",
            type="mqtt",
            channel_id=channel["channel_mqtt_id"],
            asset_type="sensor",
            asset_id="sensor-1",
            mqtt_topic="building/control",
            mqtt_retained=True,
            mqtt_payload="on",
        ),
    )
    ControlService.toggle(db, control["control_id"])

    class FakePublisher:
        def __init__(self):
            self.calls = []

        def publish_once(self, options, **kwargs):
            self.calls.append((options, kwargs))
            return MQTTPublishResult(message_id=7)

    publisher = FakePublisher()
    module = importlib.import_module("app.domain.channel.service.ControlService")
    monkeypatch.setattr(module, "mqtt_publisher", publisher)

    result = ControlService.execute(db, control["control_id"])

    options, arguments = publisher.calls[0]
    assert options.host == "mqtt.test"
    assert options.username == "user"
    assert options.password == "secret"
    assert arguments == {
        "topic": "building/control",
        "payload": "on",
        "qos": 2,
        "retain": True,
        "timeout": 20,
    }
    assert result["result"] == {
        "protocol": "mqtt",
        "message_id": 7,
        "published": True,
    }


@pytest.mark.parametrize(
    ("payload", "expected_data", "expected_message"),
    [
        (b'{"value": 12}', {"value": 12}, "ok"),
        (b"plain text", "plain text", "ok"),
        (None, None, "connected; no message received before timeout"),
    ],
)
def test_mqtt_request_test_uses_probe_and_preserves_response(
    monkeypatch, payload, expected_data, expected_message
):
    class FakeProbe:
        def receive_once(self, options, **kwargs):
            return MQTTProbeResult(connected=True, payload=payload)

    module = importlib.import_module("app.domain.channel.service.RequestService")
    monkeypatch.setattr(module, "mqtt_probe", FakeProbe())
    info = {
        "address": "mqtt.test:1883",
        "client_id": "channel-client",
        "username": "user",
        "password": "secret",
        "topic": "building/data",
        "qos": 1,
    }

    result = RequestService._test_mqtt(info, timeout=0.01)

    assert result == {"ok": True, "data": expected_data, "message": expected_message}


def test_mqtt_request_test_preserves_error_response(monkeypatch):
    class FailingProbe:
        def receive_once(self, options, **kwargs):
            raise MQTTTransportError("authentication failed")

    module = importlib.import_module("app.domain.channel.service.RequestService")
    monkeypatch.setattr(module, "mqtt_probe", FailingProbe())

    result = RequestService._test_mqtt(
        {
            "address": "mqtt.test:1883",
            "topic": "building/data",
            "qos": 1,
        },
        timeout=0.01,
    )

    assert result == {
        "ok": False,
        "data": None,
        "message": "authentication failed",
    }
