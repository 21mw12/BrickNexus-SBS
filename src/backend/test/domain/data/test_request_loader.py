"""简化版 RequestLoader 测试。"""

from contextlib import nullcontext
from types import SimpleNamespace

from app.domain.collector.loader.request_loader import RequestLoader
from app.domain.collector.event import CollectionRequestStartedEvent
from app.domain.collector.loader.request_loader import collection_event_bus
from app.domain.collector.storage.request_state_storage import request_state_storage
from app.infra.DB.SQLConnection import sql_manager


class _FakeDb:
    def __init__(self, requests) -> None:
        self.requests = requests

    def execute(self, _statement):
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(
                unique=lambda: SimpleNamespace(all=lambda: list(self.requests))
            )
        )


def _request(request_id: str, request_type: str):
    return SimpleNamespace(
        request_id=request_id,
        request_type=request_type,
        is_active=True,
    )


def test_load_active_requests_returns_dict_and_dispatches(monkeypatch) -> None:
    db = _FakeDb(
        [
            _request("http-1", "http"),
            _request("mqtt-1", "mqtt"),
        ]
    )
    monkeypatch.setattr(sql_manager, "get_db", lambda _key: nullcontext(db))
    loader = RequestLoader()
    http_started = []
    mqtt_started = []
    monkeypatch.setattr(loader.http_loader, "start", lambda request: http_started.append(request.request_id))
    monkeypatch.setattr(loader.mqtt_loader, "start", lambda request: mqtt_started.append(request.request_id))

    result = loader.load_active_requests()

    assert result == {"http": ["http-1"], "mqtt": ["mqtt-1"]}
    assert http_started == ["http-1"]
    assert mqtt_started == ["mqtt-1"]


def test_http_and_mqtt_loaders_have_the_same_lifecycle_methods() -> None:
    loader = RequestLoader()

    for protocol_loader in (loader.http_loader, loader.mqtt_loader):
        assert callable(protocol_loader.start)
        assert callable(protocol_loader.stop)
        assert callable(protocol_loader.stop_all)


def test_start_dispatches_one_request_by_type(monkeypatch) -> None:
    """接口动态启用 Request 时复用统一的协议分发入口。"""
    loader = RequestLoader()
    started = []
    monkeypatch.setattr(loader.http_loader, "start", lambda request: started.append(("http", request.request_id)) or {})
    monkeypatch.setattr(loader.mqtt_loader, "start", lambda request: started.append(("mqtt", request.request_id)) or {})

    loader.start(_request("http-1", "http"))
    loader.start(_request("mqtt-1", "mqtt"))

    assert started == [("http", "http-1"), ("mqtt", "mqtt-1")]


def test_start_event_precedes_protocol_loader(monkeypatch) -> None:
    """data 必须先建立周期状态，collector 才能开放网络接收。"""
    loader = RequestLoader()
    order = []
    monkeypatch.setattr(
        collection_event_bus,
        "publish",
        lambda event: order.append(("event", type(event))),
    )
    monkeypatch.setattr(
        loader.mqtt_loader,
        "start",
        lambda request: order.append(("loader", request.request_id)) or {},
    )
    request = _request("mqtt-1", "mqtt")
    request.request_info = {"storage_interval_seconds": 60}

    loader.start(request)

    assert order == [
        ("event", CollectionRequestStartedEvent),
        ("loader", "mqtt-1"),
    ]


def test_point_description_update_refreshes_http_and_mqtt_caches() -> None:
    """型号说明同步后，已加载的两种采集任务都应立即刷新内存。"""
    loader = RequestLoader()
    http_point = {"point_id": "point-http", "point_description": "旧说明"}
    mqtt_point = {"point_id": "point-mqtt", "point_description": "旧说明"}
    loader.http_loader.requests["http-1"] = {"point_list": [http_point]}
    loader.mqtt_loader.requests["mqtt-1"] = {
        "request_data": {"point_list": [mqtt_point]}
    }

    updated = loader.update_point_descriptions(
        {
            "point-http": "HTTP 新说明",
            "point-mqtt": "MQTT 新说明",
        }
    )

    assert updated == 2
    assert http_point["point_description"] == "HTTP 新说明"
    assert mqtt_point["point_description"] == "MQTT 新说明"


def test_one_invalid_active_request_does_not_block_other_requests(monkeypatch) -> None:
    """启动阶段按 Request 隔离异常，坏配置只跳过自身。"""
    db = _FakeDb([_request("http-bad", "http"), _request("mqtt-good", "mqtt")])
    monkeypatch.setattr(sql_manager, "get_db", lambda _key: nullcontext(db))
    loader = RequestLoader()
    stopped = []
    deactivated = []
    monkeypatch.setattr(
        loader.http_loader,
        "start",
        lambda request: (_ for _ in ()).throw(ValueError("bad config")),
    )
    monkeypatch.setattr(loader.http_loader, "stop", lambda request_id: stopped.append(request_id))
    monkeypatch.setattr(loader.mqtt_loader, "start", lambda request: {})
    monkeypatch.setattr(
        request_state_storage,
        "deactivate",
        lambda request_id: deactivated.append(request_id),
    )

    result = loader.load_active_requests()

    assert result == {"http": [], "mqtt": ["mqtt-good"]}
    assert stopped == ["http-bad"]
    assert deactivated == ["http-bad"]
