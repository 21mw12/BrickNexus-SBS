"""MQTT Broker 分组、Topic 合并和消息处理测试。"""

from datetime import datetime, timedelta, timezone
from threading import Thread
from types import SimpleNamespace

import pytest

from app.domain.collector.loader.mqtt_request_loader import MqttRequestLoader
from app.domain.collector.loader.request_data_loader import request_data_loader
from app.domain.collector.storage.request_state_storage import request_state_storage
from app.domain.collector.event import CollectionRequestStartedEvent
from app.domain.data.service.CollectionEventConsumer import CollectionDataConsumer
from app.domain.data.storage.redis_storage import redis_storage
from app.domain.data.storage.sql_storage import sql_storage
from app.domain.data.storage.status_storage import status_storage
from app.infra.Scheduler.SchedulerManager import scheduler


@pytest.fixture(autouse=True)
def _disable_real_scheduler(monkeypatch):
    """单元测试只验证任务登记，不向全局 APScheduler 写真实 Job。"""
    monkeypatch.setattr(scheduler, "add_task", lambda *args, **kwargs: None)
    monkeypatch.setattr(scheduler, "remove_task", lambda *args, **kwargs: None)


@pytest.fixture
def data_consumer():
    """通过 data 消费者验证 collector 发布后的持久化语义。"""
    consumer = CollectionDataConsumer()
    consumer.start()
    try:
        yield consumer
    finally:
        consumer.shutdown()


class _FakeClient:
    def __init__(self) -> None:
        self.username = None
        self.password = None
        self.connected_to = None
        self.loop_started = False
        self.subscriptions = []
        self.unsubscriptions = []
        self.disconnected = False
        self.on_connect = None
        self.on_disconnect = None
        self.on_message = None
        self.subscribe_rc = 0

    def username_pw_set(self, username, password) -> None:
        self.username = username
        self.password = password

    def connect_async(self, host, port, keepalive) -> None:
        self.connected_to = (host, port, keepalive)

    def loop_start(self) -> None:
        self.loop_started = True

    def loop_stop(self) -> None:
        self.loop_started = False

    def subscribe(self, topic, qos=0):
        self.subscriptions.append((topic, qos))
        return (self.subscribe_rc, len(self.subscriptions))

    def unsubscribe(self, topic):
        self.unsubscriptions.append(topic)
        return (0, len(self.unsubscriptions))

    def disconnect(self) -> None:
        self.disconnected = True


class _FakeClientFactory:
    def __init__(self, client=None) -> None:
        self._client = client
        self.clients = []
        self.options = []

    def create(self, options, **kwargs):
        client = self._client or _FakeClient()
        self.clients.append(client)
        self.options.append(options)
        return client


def _request(
    request_id: str,
    topic: str,
    *,
    username="user",
    password="secret",
    storage_interval_seconds=None,
):
    request_info = {
        "address": "mqtt.example.com:1883",
        "topic": topic,
        "username": username,
        "password": password,
        "qos": 1,
        "connect_timeout_second": 20,
        "data_timeout": 60,
    }
    if storage_interval_seconds is not None:
        request_info["storage_interval_seconds"] = storage_interval_seconds
    return SimpleNamespace(
        request_id=request_id,
        request_type="mqtt",
        request_info=request_info,
    )


def _request_data():
    return {
        "terminal_list": ["terminal-1"],
        "point_list": [
            {
                "point_id": "point-1",
                "sensor_id": "sensor-1",
                "terminal_id": "terminal-1",
                "json_path": "$.value",
                "unit": "kW",
            }
        ],
        "time_json_path": "",
        "time_parse": "",
    }


def _event_request_data():
    request_data = _request_data()
    return {
        "terminal_list": request_data["terminal_list"],
        "point_list": [
            {
                "point_id": point["point_id"],
                "sensor_id": point["sensor_id"],
                "terminal_id": point["terminal_id"],
                "unit": point.get("unit") or "",
                "point_description": point.get("point_description") or "",
            }
            for point in request_data["point_list"]
        ],
    }


def test_same_address_reuses_one_connection_and_merges_topics(monkeypatch) -> None:
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    factory = _FakeClientFactory()
    loader = MqttRequestLoader(factory)

    loader.start(_request("mqtt-1", "building/one"))
    loader.start(_request("mqtt-2", "building/two"))

    assert len(factory.clients) == 1
    assert len(loader.brokers) == 1
    broker = loader.brokers["mqtt.example.com:1883"]
    assert set(broker["topics"]) == {"building/one", "building/two"}
    assert factory.clients[0].connected_to == ("mqtt.example.com", 1883, 60)

    loader._on_connect("mqtt.example.com:1883", 0)
    assert set(factory.clients[0].subscriptions) == {
        ("building/one", 1),
        ("building/two", 1),
    }

    loader.stop("mqtt-1")
    assert factory.clients[0].disconnected is False
    assert set(broker["topics"]) == {"building/two"}

    loader.stop("mqtt-2")
    assert factory.clients[0].disconnected is True
    assert loader.brokers == {}


def test_stopping_last_request_does_not_deadlock_with_disconnect_callback(monkeypatch) -> None:
    """loop_stop 等待断开回调时，Loader 不应继续持有回调所需的锁。"""

    class _DisconnectCallbackClient(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.callback_thread = None

        def disconnect(self) -> None:
            super().disconnect()
            # 模拟 Paho 网络线程在 disconnect 后执行 on_disconnect 回调。
            self.callback_thread = Thread(
                target=lambda: self.on_disconnect(self, None, 0),
                daemon=True,
            )
            self.callback_thread.start()

        def loop_stop(self) -> None:
            # 真实 Paho 会等待网络线程结束；设置超时让回归测试不会真的卡死。
            self.callback_thread.join(timeout=0.5)
            if self.callback_thread.is_alive():
                raise TimeoutError("disconnect callback is waiting for loader lock")
            super().loop_stop()

    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    client = _DisconnectCallbackClient()
    loader = MqttRequestLoader(_FakeClientFactory(client))
    loader.start(_request("mqtt-1", "building/one"))
    loader._on_connect("mqtt.example.com:1883", 0)

    loader.stop("mqtt-1")

    assert client.disconnected is True
    assert client.callback_thread.is_alive() is False
    assert loader.requests == {}
    assert loader.brokers == {}


def test_same_address_rejects_different_credentials(monkeypatch) -> None:
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    loader = MqttRequestLoader(_FakeClientFactory())
    loader.start(_request("mqtt-1", "building/one"))

    with pytest.raises(ValueError, match="same credentials"):
        loader.start(_request("mqtt-2", "building/two", username="other"))


def test_topic_message_is_parsed_and_stored_for_matching_request(monkeypatch, data_consumer) -> None:
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    loader = MqttRequestLoader(_FakeClientFactory())
    loader.start(_request("mqtt-1", "building/one"))
    statuses = {}
    stored = {}
    monkeypatch.setattr(
        status_storage,
        "update_online_statuses",
        lambda terminals, sensors, measurement_time: statuses.update(
            terminals=terminals,
            sensors=sensors,
            measurement_time=measurement_time,
        ),
    )
    monkeypatch.setattr(sql_storage, "save", lambda measurements: stored.update(sql=measurements))
    monkeypatch.setattr(
        redis_storage,
        "save",
        lambda request_data, measurements, sensor_statuses, terminal_status, measurement_time: stored.update(
            redis=measurements,
            terminal_status=terminal_status,
        ),
    )

    loader._on_message("mqtt.example.com:1883", "building/one", b'{"value":12.5}')

    assert statuses["terminals"] == ["terminal-1"]
    assert statuses["sensors"] == {"sensor-1": True}
    assert statuses["measurement_time"] == stored["sql"][0]["time"]
    assert stored["sql"][0]["point_id"] == "point-1"
    assert stored["sql"][0]["value"] == 12.5
    assert stored["sql"][0]["time"].tzinfo is not None
    assert stored["redis"] == stored["sql"]
    assert stored["terminal_status"] is True


def test_storage_interval_keeps_realtime_updates_and_writes_last_message(monkeypatch, data_consumer) -> None:
    """周期内 Redis/状态逐消息更新，PostgreSQL 只保存最后一条消息。"""
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    loader = MqttRequestLoader(_FakeClientFactory())
    loader.start(
        _request("mqtt-1", "building/one", storage_interval_seconds=60)
    )

    status_values = []
    redis_values = []
    sql_batches = []
    monkeypatch.setattr(
        status_storage,
        "update_online_statuses",
        lambda terminals, sensors, measurement_time: status_values.append(sensors),
    )
    monkeypatch.setattr(
        redis_storage,
        "save",
        lambda request_data, measurements, sensor_statuses, terminal_status, measurement_time:
        redis_values.append(measurements[0]["value"]),
    )
    monkeypatch.setattr(
        sql_storage,
        "save",
        lambda measurements: sql_batches.append(measurements),
    )

    loader._on_message("mqtt.example.com:1883", "building/one", b'{"value":10}')
    loader._on_message("mqtt.example.com:1883", "building/one", b'{"value":12.5}')

    assert status_values == [{"sensor-1": True}, {"sensor-1": True}]
    assert redis_values == [10.0, 12.5]
    assert sql_batches == []

    # 模拟从 Request 启动时间计算的固定周期已经到达。
    data_consumer.persistence._requests["mqtt-1"]["next_storage_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    data_consumer.persistence.flush_due()

    assert len(sql_batches) == 1
    assert sql_batches[0][0]["value"] == 12.5
    assert sql_batches[0][0]["time"].tzinfo is not None
    assert data_consumer.persistence._requests["mqtt-1"]["pending_measurements"] is None


def test_empty_storage_period_does_not_write_database(monkeypatch, data_consumer) -> None:
    """固定周期内没有成功测点时，不执行空批次数据库写入。"""
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    loader = MqttRequestLoader(_FakeClientFactory())
    loader.start(
        _request("mqtt-1", "building/one", storage_interval_seconds=60)
    )
    data_consumer.persistence.register(
        CollectionRequestStartedEvent(
            request_id="mqtt-1",
            request_type="mqtt",
            started_at=datetime.now(timezone.utc) - timedelta(seconds=61),
            storage_interval_seconds=60,
        )
    )
    sql_batches = []
    monkeypatch.setattr(sql_storage, "save", lambda measurements: sql_batches.append(measurements))

    data_consumer.persistence.flush_due()

    assert sql_batches == []
    assert data_consumer.persistence._requests["mqtt-1"]["next_storage_at"] > datetime.now(timezone.utc)


def test_messages_in_different_storage_periods_are_each_written(monkeypatch, data_consumer) -> None:
    """消息间隔大于存储周期时，各周期的消息都应分别写入数据库。"""
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    loader = MqttRequestLoader(_FakeClientFactory())
    loader.start(
        _request("mqtt-1", "building/one", storage_interval_seconds=60)
    )
    monkeypatch.setattr(status_storage, "update_online_statuses", lambda *args: None)
    monkeypatch.setattr(redis_storage, "save", lambda *args, **kwargs: None)
    stored_values = []
    monkeypatch.setattr(
        sql_storage,
        "save",
        lambda measurements: stored_values.append(measurements[0]["value"]),
    )

    loader._on_message("mqtt.example.com:1883", "building/one", b'{"value":10}')
    data_consumer.persistence._requests["mqtt-1"]["next_storage_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    data_consumer.persistence.flush_due()

    loader._on_message("mqtt.example.com:1883", "building/one", b'{"value":20}')
    data_consumer.persistence._requests["mqtt-1"]["next_storage_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    data_consumer.persistence.flush_due()

    assert stored_values == [10.0, 20.0]


def test_failed_periodic_write_retries_latest_message(monkeypatch, data_consumer) -> None:
    """SQL 失败后继续重试；重试前的新消息覆盖旧的失败批次。"""
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    loader = MqttRequestLoader(_FakeClientFactory())
    loader.start(
        _request("mqtt-1", "building/one", storage_interval_seconds=60)
    )
    monkeypatch.setattr(status_storage, "update_online_statuses", lambda *args: None)
    monkeypatch.setattr(redis_storage, "save", lambda *args, **kwargs: None)

    attempts = []

    def save_with_first_failure(measurements):
        attempts.append(measurements[0]["value"])
        if len(attempts) == 1:
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(sql_storage, "save", save_with_first_failure)
    loader._on_message("mqtt.example.com:1883", "building/one", b'{"value":10}')
    data_consumer.persistence._requests["mqtt-1"]["next_storage_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    data_consumer.persistence.flush_due()

    loader._on_message("mqtt.example.com:1883", "building/one", b'{"value":20}')
    data_consumer.persistence.flush_due()

    assert attempts == [10.0, 20.0]
    assert data_consumer.persistence._requests["mqtt-1"]["pending_measurements"] is None


def test_stop_discards_pending_periodic_measurements(monkeypatch, data_consumer) -> None:
    """停止 Request 时不补写尚未到期的周期数据。"""
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    loader = MqttRequestLoader(_FakeClientFactory())
    loader.start(
        _request("mqtt-1", "building/one", storage_interval_seconds=60)
    )
    monkeypatch.setattr(status_storage, "update_online_statuses", lambda *args: None)
    monkeypatch.setattr(redis_storage, "save", lambda *args, **kwargs: None)
    sql_batches = []
    monkeypatch.setattr(sql_storage, "save", lambda measurements: sql_batches.append(measurements))

    loader._on_message("mqtt.example.com:1883", "building/one", b'{"value":10}')
    loader.stop("mqtt-1")
    data_consumer.persistence.flush_due()

    assert sql_batches == []
    assert "mqtt-1" not in loader.requests


@pytest.mark.parametrize("invalid_value", [0, -1, True, "60", float("inf")])
def test_loader_rejects_invalid_storage_interval(monkeypatch, invalid_value) -> None:
    """Loader 启动时对历史库或绕过 API 写入的非法配置进行防御校验。"""
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    loader = MqttRequestLoader()

    with pytest.raises(ValueError, match="storage_interval_seconds"):
        loader.start(
            _request(
                "mqtt-1",
                "building/one",
                storage_interval_seconds=invalid_value,
            )
        )


def test_connect_timeout_marks_request_assets_offline(monkeypatch, data_consumer) -> None:
    """connect_timeout_second 内未连接成功时执行公共离线处理。"""
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    loader = MqttRequestLoader(_FakeClientFactory())
    request = _request("mqtt-1", "building/one")
    request.request_info["connect_timeout_second"] = 1
    loader.start(request)

    old_time = datetime.now(timezone.utc) - timedelta(seconds=2)
    loader.requests["mqtt-1"]["started_at"] = old_time
    loader.brokers["mqtt.example.com:1883"]["connection_started_at"] = old_time
    offline = []
    monkeypatch.setattr(
        status_storage,
        "set_all_offline",
        lambda structure, status_time: offline.append((structure, status_time)),
    )
    deactivated = []
    monkeypatch.setattr(
        request_state_storage,
        "deactivate",
        lambda request_id: deactivated.append(request_id),
    )

    loader.health_check()
    loader.health_check()

    assert len(offline) == 1
    assert offline[0][0] == _event_request_data()
    assert deactivated == ["mqtt-1"]
    assert "mqtt-1" not in loader.requests
    assert loader.brokers == {}


def test_data_timeout_marks_request_assets_offline(monkeypatch, data_consumer) -> None:
    """Broker 已连接但 data_timeout 内没有消息时执行公共离线处理。"""
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    loader = MqttRequestLoader(_FakeClientFactory())
    request = _request("mqtt-1", "building/one")
    request.request_info["data_timeout"] = 1
    loader.start(request)
    loader._on_connect("mqtt.example.com:1883", 0)
    loader.requests["mqtt-1"]["data_wait_started_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=2)
    )
    offline = []
    monkeypatch.setattr(
        status_storage,
        "set_all_offline",
        lambda structure, status_time: offline.append((structure, status_time)),
    )
    deactivated = []
    monkeypatch.setattr(
        request_state_storage,
        "deactivate",
        lambda request_id: deactivated.append(request_id),
    )

    loader.health_check()

    assert len(offline) == 1
    assert offline[0][0] == _event_request_data()
    assert deactivated == ["mqtt-1"]
    assert "mqtt-1" not in loader.requests


def test_received_message_resets_data_timeout(monkeypatch) -> None:
    """收到 Topic 消息后刷新 last_message_at，不会继续沿用旧超时状态。"""
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    loader = MqttRequestLoader(_FakeClientFactory())
    loader.start(_request("mqtt-1", "building/one"))
    loader.requests["mqtt-1"]["offline_marked"] = True
    monkeypatch.setattr(loader, "_process_message", lambda request_id, response: None)

    loader._on_message("mqtt.example.com:1883", "building/one", b'{"value":12.5}')

    assert loader.requests["mqtt-1"]["last_message_at"] is not None
    assert loader.requests["mqtt-1"]["offline_marked"] is False


def test_subscription_failure_stops_matching_request(monkeypatch, data_consumer) -> None:
    """Broker 连接后 Topic 订阅失败，由健康任务停用并移除该 Request。"""
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    client = _FakeClient()
    client.subscribe_rc = 1
    loader = MqttRequestLoader(_FakeClientFactory(client))
    loader.start(_request("mqtt-1", "building/one"))
    monkeypatch.setattr(status_storage, "set_all_offline", lambda *args: None)
    deactivated = []
    monkeypatch.setattr(
        request_state_storage,
        "deactivate",
        lambda request_id: deactivated.append(request_id),
    )

    loader._on_connect("mqtt.example.com:1883", 0)
    assert loader.requests["mqtt-1"]["fatal_error_reason"] is not None

    loader.health_check()

    assert deactivated == ["mqtt-1"]
    assert "mqtt-1" not in loader.requests
    assert client.disconnected is True


def test_authentication_failure_stops_broker_requests(monkeypatch, data_consumer) -> None:
    """明确的 MQTT 认证失败无需等待 connect_timeout。"""
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: _request_data())
    loader = MqttRequestLoader(_FakeClientFactory())
    loader.start(_request("mqtt-1", "building/one"))
    monkeypatch.setattr(status_storage, "set_all_offline", lambda *args: None)
    deactivated = []
    monkeypatch.setattr(
        request_state_storage,
        "deactivate",
        lambda request_id: deactivated.append(request_id),
    )

    loader._on_connect("mqtt.example.com:1883", 5)
    loader.health_check()

    assert deactivated == ["mqtt-1"]
    assert "mqtt-1" not in loader.requests
