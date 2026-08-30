"""Unit tests for reusable MQTT transport infrastructure."""

from types import SimpleNamespace

import pytest

from app.infra.MQTT import (
    MQTTClientFactory,
    MQTTConnectionOptions,
    MQTTProbe,
    MQTTPublisher,
    MQTTTransportError,
)


class _Client:
    def __init__(self, *, payload: bytes | None = None, connect_rc=0, subscribe_rc=0):
        self.payload = payload
        self.connect_rc = connect_rc
        self.subscribe_rc = subscribe_rc
        self.credentials = None
        self.connected_to = None
        self.subscriptions = []
        self.published = None
        self.loop_started = False
        self.disconnected = False
        self.on_connect = None
        self.on_message = None
        self.publish_rc = 0

    def username_pw_set(self, username, password):
        self.credentials = (username, password)

    def connect(self, host, port, keepalive):
        self.connected_to = (host, port, keepalive)
        return 0

    def loop_start(self):
        self.loop_started = True
        if self.on_connect is not None:
            self.on_connect(self, None, {}, self.connect_rc)
        if self.payload is not None and self.connect_rc == 0 and self.on_message is not None:
            self.on_message(self, None, SimpleNamespace(payload=self.payload))

    def loop_stop(self):
        self.loop_started = False

    def disconnect(self):
        self.disconnected = True

    def subscribe(self, topic, qos=0):
        self.subscriptions.append((topic, qos))
        return self.subscribe_rc, 1

    def publish(self, topic, payload, qos, retain):
        self.published = (topic, payload, qos, retain)
        return _PublishInfo(self.publish_rc)


class _PublishInfo:
    def __init__(self, rc):
        self.rc = rc
        self.mid = 42
        self.wait_timeout = None
        self.completed = True

    def wait_for_publish(self, timeout):
        self.wait_timeout = timeout

    def is_published(self):
        return self.completed


class _Factory:
    def __init__(self, client):
        self.client = client
        self.calls = []

    def create(self, options, **kwargs):
        self.calls.append((options, kwargs))
        if options.username is not None:
            self.client.username_pw_set(options.username, options.password)
        return self.client


def test_client_factory_supports_callback_v1_and_credentials():
    clients = []

    class FakePaho:
        CallbackAPIVersion = SimpleNamespace(VERSION1="v1")

        @staticmethod
        def Client(**kwargs):
            client = _Client()
            client.constructor_kwargs = kwargs
            clients.append(client)
            return client

    factory = MQTTClientFactory(FakePaho)
    options = MQTTConnectionOptions(
        host="mqtt.test",
        client_id="stable-client",
        username="user",
        password="secret",
    )
    client = factory.create(options)

    assert "secret" not in repr(options)
    assert client.constructor_kwargs == {
        "callback_api_version": "v1",
        "client_id": "stable-client",
        "clean_session": True,
    }
    assert client.credentials == ("user", "secret")

    temporary = factory.create(options, temporary=True, purpose="probe")
    assert temporary.constructor_kwargs["client_id"].startswith("stable-client-probe-")
    assert temporary.constructor_kwargs["client_id"] != "stable-client"


def test_client_factory_supports_paho_without_callback_api_version():
    captured = {}

    def client_constructor(**kwargs):
        captured.update(kwargs)
        return _Client()

    factory = MQTTClientFactory(SimpleNamespace(Client=client_constructor))
    factory.create(MQTTConnectionOptions(host="mqtt.test", client_id="legacy"))

    assert captured == {"client_id": "legacy", "clean_session": True}


def test_publisher_sends_parameters_and_always_closes_client():
    client = _Client()
    factory = _Factory(client)
    publisher = MQTTPublisher(factory)
    options = MQTTConnectionOptions(
        host="mqtt.test", port=1884, username="user", password="secret", keepalive=20
    )

    result = publisher.publish_once(
        options,
        topic="building/control",
        payload="on",
        qos=2,
        retain=True,
        timeout=5,
    )

    assert result.message_id == 42
    assert result.published is True
    assert client.connected_to == ("mqtt.test", 1884, 20)
    assert client.credentials == ("user", "secret")
    assert client.published == ("building/control", "on", 2, True)
    assert client.disconnected is True
    assert client.loop_started is False
    assert factory.calls[0][1] == {"temporary": True, "purpose": "publisher"}


def test_publisher_wraps_failure_and_closes_client():
    client = _Client()
    client.publish_rc = 1

    with pytest.raises(MQTTTransportError, match="publish failed"):
        MQTTPublisher(_Factory(client)).publish_once(
            MQTTConnectionOptions(host="mqtt.test"),
            topic="control",
            payload="on",
            qos=1,
            retain=False,
            timeout=1,
        )

    assert client.disconnected is True
    assert client.loop_started is False


def test_publisher_reports_wait_timeout():
    client = _Client()

    def publish(*args, **kwargs):
        result = _PublishInfo(0)
        result.completed = False
        return result

    client.publish = publish
    with pytest.raises(MQTTTransportError, match="timed out"):
        MQTTPublisher(_Factory(client)).publish_once(
            MQTTConnectionOptions(host="mqtt.test"),
            topic="control",
            payload="on",
            qos=1,
            retain=False,
            timeout=0.01,
        )

    assert client.disconnected is True


def test_publisher_wraps_connection_error_and_closes_client():
    client = _Client()

    def connect(*args, **kwargs):
        raise OSError("broker unavailable")

    client.connect = connect
    with pytest.raises(MQTTTransportError, match="broker unavailable"):
        MQTTPublisher(_Factory(client)).publish_once(
            MQTTConnectionOptions(host="mqtt.test"),
            topic="control",
            payload="on",
            qos=1,
            retain=False,
            timeout=1,
        )

    assert client.disconnected is True
    assert client.loop_started is False


def test_probe_returns_first_raw_payload_and_subscription():
    client = _Client(payload=b'{"value": 12}')
    probe = MQTTProbe(_Factory(client))

    result = probe.receive_once(
        MQTTConnectionOptions(host="mqtt.test"),
        topic="building/data",
        qos=1,
        timeout=0.01,
    )

    assert result.connected is True
    assert result.payload == b'{"value": 12}'
    assert client.subscriptions == [("building/data", 1)]
    assert client.disconnected is True


def test_probe_allows_connected_broker_without_message():
    result = MQTTProbe(_Factory(_Client())).receive_once(
        MQTTConnectionOptions(host="mqtt.test"),
        topic="building/data",
        qos=0,
        timeout=0.001,
    )

    assert result.connected is True
    assert result.payload is None


@pytest.mark.parametrize(
    ("client", "message"),
    [
        (_Client(connect_rc=5), "connect failed"),
        (_Client(subscribe_rc=1), "subscribe failed"),
    ],
)
def test_probe_reports_connection_and_subscription_failures(client, message):
    with pytest.raises(MQTTTransportError, match=message):
        MQTTProbe(_Factory(client)).receive_once(
            MQTTConnectionOptions(host="mqtt.test"),
            topic="building/data",
            qos=1,
            timeout=0.01,
        )

    assert client.disconnected is True
