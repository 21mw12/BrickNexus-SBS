import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.core.utils.HTTPRequestor import HttpUtil
from app.domain import *  # noqa: F401,F403
from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.repository.models.AssetSensor import AssetSensor
from app.domain.channel.repository.models.ChannelMqtt import ChannelMqtt
from app.domain.channel.schema.ChannelSchema import HttpChannelAddSchema, MqttChannelAddSchema, MqttChannelEditSchema
from app.domain.channel.schema.ControlSchema import ControlAddSchema, ControlQuerySchema
from app.domain.channel.schema.RequestSchema import RequestAddSchema, RequestQuerySchema
from app.domain.channel.service.ChannelCipher import ChannelCipher
from app.domain.channel.service.ChannelResolver import ChannelResolver
from app.domain.channel.service.ChannelService import ChannelService
from app.domain.channel.service.ControlService import ControlService
from app.domain.channel.service.RequestService import RequestService
from app.infra.DB.SQLConnection import Base


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_mqtt_password_is_encrypted_masked_and_can_be_cleared(db: Session) -> None:
    result = ChannelService.add_mqtt(db, MqttChannelAddSchema(broker_host="mqtt.test", password="secret"))
    row = db.get(ChannelMqtt, result["channel_mqtt_id"])
    assert row.password != "secret"
    assert ChannelCipher.decrypt(row.password) == "secret"
    assert result["password_configured"] is True
    assert "password" not in result

    retained = ChannelService.edit_mqtt(db, row.channel_mqtt_id, MqttChannelEditSchema(qos=2))
    assert retained["password_configured"] is True
    cleared = ChannelService.edit_mqtt(db, row.channel_mqtt_id, MqttChannelEditSchema(password=None))
    assert cleared["password_configured"] is False


def test_wrong_encryption_key_is_reported() -> None:
    encrypted_with_another_key = Fernet(Fernet.generate_key()).encrypt(b"secret").decode()
    with pytest.raises(ValidationError, match="cannot be decrypted"):
        ChannelCipher.decrypt(encrypted_with_another_key)


def test_channel_lists_only_return_summary_fields(db: Session) -> None:
    mqtt_channel = ChannelService.add_mqtt(
        db, MqttChannelAddSchema(broker_host="mqtt.test")
    )
    http_channel = ChannelService.add_http(
        db, HttpChannelAddSchema(base_url="https://http.test")
    )

    mqtt_item = ChannelService.list_mqtt(db, 1, 20, None)["items"][0]
    http_item = ChannelService.list_http(db, 1, 20, None)["items"][0]

    assert mqtt_item == {
        key: mqtt_channel[key]
        for key in ("channel_mqtt_id", "broker_host", "broker_port", "created_at")
    }
    assert http_item == {
        key: http_channel[key]
        for key in ("channel_http_id", "base_url", "created_at")
    }


def test_http_channel_accepts_base_url_up_to_200_characters(db: Session) -> None:
    long_url = "https://example.com/" + "a" * 180
    assert len(long_url) == 200
    result = ChannelService.add_http(db, HttpChannelAddSchema(base_url=long_url))
    assert result["base_url"] == long_url

    with pytest.raises(PydanticValidationError):
        HttpChannelAddSchema(base_url=long_url + "a")


def test_request_and_control_filters_reject_channel_id() -> None:
    with pytest.raises(PydanticValidationError):
        RequestQuerySchema(channel_id="channel-1")
    with pytest.raises(PydanticValidationError):
        ControlQuerySchema(channel_id="channel-1")
    with pytest.raises(PydanticValidationError):
        ControlQuerySchema(sensor_id="sensor-1")


def test_http_request_resolves_url_headers_and_default_period(db: Session) -> None:
    channel = ChannelService.add_http(db, HttpChannelAddSchema(base_url="https://api.test/root", default_headers={"X": "common"}))
    result = RequestService.create_request(
        RequestAddSchema(
            name="temperature", type="http", channel_id=channel["channel_http_id"],
            http_method="GET", http_path="/values", http_header={"X": "request"},
        ), db,
    )
    resolved = ChannelResolver.resolve_request(db, db.get(Request, result["request_id"]))
    assert resolved.request_info["url"] == "https://api.test/root/values"
    assert resolved.request_info["headers"] == {"X": "request"}
    assert result["interval_seconds"] == 60

    list_item = RequestService.list_requests(db)["items"][0]
    assert set(list_item) == {"request_id", "name", "type", "status", "created_at"}


def test_mqtt_request_persists_unused_http_json_fields_as_sql_null(db: Session) -> None:
    channel = ChannelService.add_mqtt(db, MqttChannelAddSchema(broker_host="mqtt.test"))
    result = RequestService.create_request(
        RequestAddSchema(
            name="mqtt request",
            type="mqtt",
            channel_id=channel["channel_mqtt_id"],
            mqtt_topic="/gateway/measurements",
        ),
        db,
    )
    db.flush()

    row = db.get(Request, result["request_id"])
    assert row.http_header is None
    assert row.http_params is None
    assert row.http_body is None


def test_referenced_channel_cannot_be_deleted(db: Session) -> None:
    channel = ChannelService.add_http(db, HttpChannelAddSchema(base_url="https://api.test"))
    RequestService.create_request(RequestAddSchema(name="request", type="http", channel_id=channel["channel_http_id"], http_method="GET", http_path="/v"), db)
    with pytest.raises(ValidationError, match="referenced"):
        ChannelService.drop_http(db, channel["channel_http_id"])


def test_http_control_requires_enabled_sensor_and_executes_saved_config(db: Session, monkeypatch) -> None:
    db.add(Asset(asset_id="sensor-1", asset_type="sensor", name="Sensor", is_use=True))
    db.add(AssetSensor(asset_id="sensor-1", is_online=False))
    db.flush()
    channel = ChannelService.add_http(db, HttpChannelAddSchema(base_url="https://api.test", default_headers={"A": "1"}))
    control = ControlService.add(db, ControlAddSchema(
        name="switch", type="http", channel_id=channel["channel_http_id"],
        asset_type="sensor", asset_id="sensor-1",
        http_method="POST", http_path="/switch", http_header={"A": "2"}, http_body={"on": True},
    ))
    list_item = ControlService.list_controls(db, 1, 20, None, None)["items"][0]
    assert set(list_item) == {
        "control_id", "name", "type", "asset_type", "asset_name", "status", "created_at"
    }
    assert list_item["asset_type"] == "sensor"
    assert list_item["asset_name"] == "Sensor"
    with pytest.raises(ValidationError, match="disabled"):
        ControlService.execute(db, control["control_id"])

    assert ControlService.toggle(db, control["control_id"]) is True
    calls = []
    monkeypatch.setattr(HttpUtil, "_request", lambda **kwargs: calls.append(kwargs) or (True, {"accepted": True}))
    executed = ControlService.execute(db, control["control_id"])
    assert executed["success"] is True
    assert calls[0]["url"] == "https://api.test/switch"
    assert calls[0]["headers"] == {"A": "2"}
    assert calls[0]["json"] == {"on": True}


def test_mqtt_control_persists_unused_http_json_fields_as_sql_null(db: Session) -> None:
    db.add(Asset(asset_id="sensor-mqtt", asset_type="sensor", name="MQTT Sensor", is_use=True))
    db.add(AssetSensor(asset_id="sensor-mqtt", is_online=False))
    db.flush()
    channel = ChannelService.add_mqtt(db, MqttChannelAddSchema(broker_host="mqtt.test"))
    result = ControlService.add(
        db,
        ControlAddSchema(
            name="mqtt control",
            type="mqtt",
            channel_id=channel["channel_mqtt_id"],
            asset_type="sensor",
            asset_id="sensor-mqtt",
            mqtt_topic="/gateway/control",
            mqtt_payload="on",
        ),
    )
    db.flush()

    row = db.get(Control, result["control_id"])
    assert row.http_header is None
    assert row.http_params is None
    assert row.http_body is None


def test_terminal_control_and_asset_type_filter(db: Session) -> None:
    db.add_all([
        Asset(asset_id="terminal-1", asset_type="terminal", name="Terminal", is_use=True),
        Asset(asset_id="sensor-1", asset_type="sensor", name="Sensor", is_use=True),
        AssetSensor(asset_id="sensor-1", is_online=False),
    ])
    db.flush()
    channel = ChannelService.add_http(
        db, HttpChannelAddSchema(base_url="https://api.test")
    )
    controls = {}
    for name, asset_type, asset_id in (
        ("terminal control", "terminal", "terminal-1"),
        ("sensor control", "sensor", "sensor-1"),
    ):
        controls[asset_type] = ControlService.add(db, ControlAddSchema(
            name=name, type="http", channel_id=channel["channel_http_id"],
            asset_type=asset_type, asset_id=asset_id,
            http_method="POST", http_path="/switch", http_body={"on": True},
        ))

    terminal = ControlService.list_controls(
        db, 1, 20, ControlQuerySchema(asset_type="terminal"), None
    )
    assert terminal["total"] == 1
    assert terminal["items"][0]["asset_type"] == "terminal"
    assert terminal["items"][0]["asset_name"] == "Terminal"

    sensor = ControlService.list_controls(
        db, 1, 20, ControlQuerySchema(asset_type="sensor"), None
    )
    assert sensor["total"] == 1
    assert sensor["items"][0]["asset_type"] == "sensor"

    # get_viewable_asset_ids 对 root 返回 None，None 必须表示不限制，而不是无权限。
    root_result = ControlService.list_controls(db, 1, 20, None, None)
    assert root_result["total"] == 2

    assert ControlService.toggle(db, controls["sensor"]["control_id"]) is True
    exact_sensor = ControlService.list_controls(
        db,
        1,
        20,
        ControlQuerySchema(
            status=True, asset_type="sensor", asset_id="sensor-1"
        ),
        {"sensor-1"},
    )
    assert exact_sensor["total"] == 1
    assert exact_sensor["items"][0]["control_id"] == controls["sensor"]["control_id"]
    assert ControlService.get_bound_asset_id(
        db, controls["sensor"]["control_id"]
    ) == "sensor-1"
    assert ControlService.get_bound_asset_id(db, "missing-control") is None
