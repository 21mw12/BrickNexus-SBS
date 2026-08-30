"""HTTP Request 定时任务测试。"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.domain.collector.loader.http_request_loader import HttpRequestLoader
from app.domain.collector.loader.request_data_loader import request_data_loader
from app.domain.collector.parser.data_parser import data_parser
from app.domain.collector.storage.request_state_storage import request_state_storage
from app.domain.data.storage.redis_storage import redis_storage
from app.domain.data.storage.sql_storage import sql_storage
from app.domain.data.storage.status_storage import status_storage
from app.domain.data.service.CollectionEventConsumer import CollectionDataConsumer
from app.infra.Scheduler.SchedulerManager import scheduler


def _request():
    return SimpleNamespace(
        request_id="http-1",
        request_type="http",
        request_info={
            "method": "POST",
            "url": "https://example.com/data",
            "headers": {"X-Test": "1"},
            "params": {"terminal": "1"},
            "body": {"query": "latest"},
            "timeout_seconds": 12,
            "interval_seconds": 30,
        },
    )


def _event_request_data(request_data: dict) -> dict:
    """事件只携带 data 消费所需的非解析配置。"""
    return {
        "terminal_list": list(request_data["terminal_list"]),
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


@pytest.fixture
def data_consumer(monkeypatch):
    """让 Loader 发布的事件通过新的 data 边界执行原有存储逻辑。"""
    monkeypatch.setattr(scheduler, "add_task", lambda *args, **kwargs: None)
    monkeypatch.setattr(scheduler, "remove_task", lambda *args, **kwargs: None)
    consumer = CollectionDataConsumer()
    consumer.start()
    try:
        yield consumer
    finally:
        consumer.shutdown()


def test_start_loads_structure_and_creates_interval_task(monkeypatch) -> None:
    request_data = {"terminal_list": [], "point_list": [], "time_json_path": "", "time_parse": ""}
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: request_data)
    scheduled = {}

    def add_task(task_id, func, interval_seconds, initial_delay_seconds=None):
        scheduled.update(
            task_id=task_id,
            func=func,
            interval_seconds=interval_seconds,
            initial_delay_seconds=initial_delay_seconds,
        )

    monkeypatch.setattr(scheduler, "add_task", add_task)
    monkeypatch.setattr(
        "app.domain.collector.loader.http_request_loader.random.uniform",
        lambda start, end: 12.5,
    )
    loader = HttpRequestLoader()

    result = loader.start(_request())

    assert result == request_data
    assert scheduled["task_id"] == "collector:http:http-1"
    assert scheduled["interval_seconds"] == 30
    assert scheduled["initial_delay_seconds"] == 12.5


def test_scheduled_task_requests_then_calls_parse_placeholder(monkeypatch) -> None:
    request_data = {"terminal_list": ["terminal-1"], "point_list": [], "time_json_path": "", "time_parse": ""}
    monkeypatch.setattr(request_data_loader, "load", lambda request_id: request_data)
    scheduled = {}
    monkeypatch.setattr(
        scheduler,
        "add_task",
        lambda task_id, func, interval_seconds, initial_delay_seconds=None: scheduled.update(func=func),
    )

    sent = {}

    def http_request(**kwargs):
        sent.update(kwargs)
        return True, {"value": 10}

    monkeypatch.setattr(
        "app.domain.collector.loader.http_request_loader.HttpUtil._request",
        http_request,
    )
    parsed = {}
    loader = HttpRequestLoader()
    monkeypatch.setattr(
        loader,
        "parse_response",
        lambda request_id, response_data, structure, measurement_time: parsed.update(
            request_id=request_id,
            response_data=response_data,
            structure=structure,
            measurement_time=measurement_time,
        ),
    )
    loader.start(_request())

    scheduled["func"]()

    assert sent["method"] == "POST"
    assert sent["json"] == {"query": "latest"}
    assert sent["timeout"] == 12
    assert parsed == {
        "request_id": "http-1",
        "response_data": {"value": 10},
        "structure": request_data,
        "measurement_time": parsed["measurement_time"],
    }
    assert parsed["measurement_time"].tzinfo is not None


def test_parse_response_updates_statuses_and_calls_storage(monkeypatch, data_consumer) -> None:
    request_data = {
        "terminal_list": ["terminal-1", "terminal-2"],
        "point_list": [
            {
                "point_id": "point-1",
                "sensor_id": "sensor-1",
                "terminal_id": "terminal-1",
                "json_path": "$.data.value",
            },
            {
                "point_id": "point-2",
                "sensor_id": "sensor-2",
                "terminal_id": "terminal-2",
                "json_path": "$.data.missing",
            },
        ],
        "time_json_path": "",
        "time_parse": "",
    }
    loader = HttpRequestLoader()
    loader.json_paths["http-1"] = data_parser.compile_json_paths(request_data["point_list"])
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
    monkeypatch.setattr(sql_storage, "save", lambda measurements: stored.update(measurements=measurements))
    monkeypatch.setattr(
        redis_storage,
        "save",
        lambda structure, measurements, statuses, terminal_status, measurement_time: stored.update(
            latest=measurements,
            terminal_status=terminal_status,
        ),
    )

    measurement_time = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
    result = loader.parse_response(
        "http-1",
        {"data": {"value": "12.5"}},
        request_data,
        measurement_time,
    )

    assert result["measurements"] == [
        {
            "point_id": "point-1",
            "sensor_id": "sensor-1",
            "terminal_id": "terminal-1",
            "value": 12.5,
            "time": measurement_time,
        }
    ]
    assert statuses == {
        "terminals": ["terminal-1", "terminal-2"],
        "sensors": {"sensor-1": True, "sensor-2": False},
        "measurement_time": measurement_time,
    }
    assert stored["measurements"] == result["measurements"]
    assert stored["latest"] == result["measurements"]
    assert stored["terminal_status"] is True


def test_online_status_update_uses_bulk_statements_without_select(monkeypatch) -> None:
    executed = []

    class _FakeDb:
        def execute(self, statement):
            executed.append(statement)

    from contextlib import nullcontext
    from app.infra.DB.SQLConnection import sql_manager

    monkeypatch.setattr(sql_manager, "get_db", lambda _key: nullcontext(_FakeDb()))

    measurement_time = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
    status_storage.update_online_statuses(
        ["terminal-1", "terminal-2"],
        {"sensor-1": True, "sensor-2": False},
        measurement_time,
    )

    assert len(executed) == 3
    params = [statement.compile().params for statement in executed]
    assert params[0]["last_receive_time"] == measurement_time
    assert params[1]["last_receive_time"] == measurement_time
    assert "last_receive_time" not in params[2]


def test_http_failure_marks_all_terminals_and_sensors_offline(monkeypatch, data_consumer) -> None:
    request_data = {
        "terminal_list": ["terminal-1", "terminal-2"],
        "point_list": [
            {"point_id": "point-1", "sensor_id": "sensor-1", "terminal_id": "terminal-1", "json_path": "$.a"},
            {"point_id": "point-2", "sensor_id": "sensor-1", "terminal_id": "terminal-1", "json_path": "$.b"},
            {"point_id": "point-3", "sensor_id": "sensor-2", "terminal_id": "terminal-2", "json_path": "$.c"},
        ],
        "time_json_path": "",
        "time_parse": "",
    }
    loader = HttpRequestLoader()
    loader.requests["http-1"] = request_data
    loader.request_info["http-1"] = {"method": "GET", "url": "https://example.com"}
    loader.failure_counts["http-1"] = 0
    monkeypatch.setattr(
        "app.domain.collector.loader.http_request_loader.HttpUtil._request",
        lambda **kwargs: (False, "connection failed"),
    )
    offline = []
    monkeypatch.setattr(status_storage, "set_all_offline", lambda structure, *args: offline.append(structure))

    loader.execute_request("http-1")

    assert offline == [_event_request_data(request_data)]


def test_set_all_offline_uses_two_bulk_updates_and_deduplicates_sensors(monkeypatch) -> None:
    executed = []

    class _FakeDb:
        def execute(self, statement):
            executed.append(statement)

    from contextlib import nullcontext
    from app.infra.DB.SQLConnection import sql_manager

    monkeypatch.setattr(sql_manager, "get_db", lambda _key: nullcontext(_FakeDb()))
    monkeypatch.setattr(redis_storage, "save", lambda *args, **kwargs: None)
    status_storage.set_all_offline(
        {
            "terminal_list": ["terminal-1", "terminal-2"],
            "point_list": [
                {"sensor_id": "sensor-1"},
                {"sensor_id": "sensor-1"},
                {"sensor_id": "sensor-2"},
            ],
        }
    )

    assert len(executed) == 2


def test_http_failure_marks_offline_immediately_and_stops_after_three_failures(monkeypatch, data_consumer) -> None:
    """每次失败立即离线，连续第三次失败后停用并移除任务。"""
    request_data = {
        "terminal_list": ["terminal-1"],
        "point_list": [
            {
                "point_id": "point-1",
                "sensor_id": "sensor-1",
                "terminal_id": "terminal-1",
            }
        ],
        "time_json_path": "",
        "time_parse": "",
    }
    loader = HttpRequestLoader()
    loader.requests["http-1"] = request_data
    loader.request_info["http-1"] = {
        "method": "GET",
        "url": "https://example.com",
        "interval_seconds": 60,
    }
    loader.failure_counts["http-1"] = 0
    monkeypatch.setattr(
        "app.domain.collector.loader.http_request_loader.HttpUtil._request",
        lambda **kwargs: (False, "connection failed"),
    )
    offline = []
    removed = []
    deactivated = []
    monkeypatch.setattr(status_storage, "set_all_offline", lambda structure, *args: offline.append(structure))
    monkeypatch.setattr(scheduler, "remove_task", lambda task_id: removed.append(task_id))
    monkeypatch.setattr(
        request_state_storage,
        "deactivate",
        lambda request_id: deactivated.append(request_id),
    )

    loader.execute_request("http-1")
    assert "http-1" in loader.requests
    assert offline == [_event_request_data(request_data)]
    assert removed == []

    loader.execute_request("http-1")
    assert "http-1" in loader.requests

    loader.execute_request("http-1")

    assert offline == [_event_request_data(request_data)] * 3
    assert removed == ["collector:http:http-1"]
    assert deactivated == ["http-1"]
    assert "http-1" not in loader.requests


def test_http_success_resets_consecutive_failure_count(monkeypatch) -> None:
    """中间成功一次后，连续失败次数从零重新计算。"""
    request_data = {
        "terminal_list": [],
        "point_list": [],
        "time_json_path": "",
        "time_parse": "",
    }
    loader = HttpRequestLoader()
    loader.requests["http-1"] = request_data
    loader.request_info["http-1"] = {"method": "GET", "url": "https://example.com"}
    loader.failure_counts["http-1"] = 2
    monkeypatch.setattr(
        "app.domain.collector.loader.http_request_loader.HttpUtil._request",
        lambda **kwargs: (True, {}),
    )
    monkeypatch.setattr(loader, "parse_response", lambda *args: None)

    loader.execute_request("http-1")

    assert loader.failure_counts["http-1"] == 0


def test_all_points_failed_counts_as_http_failure(monkeypatch, data_consumer) -> None:
    """HTTP 成功但全部 Point 解析失败时仍按一次 Request 失败处理。"""
    request_data = {
        "terminal_list": ["terminal-1"],
        "point_list": [
            {
                "point_id": "point-1",
                "sensor_id": "sensor-1",
                "terminal_id": "terminal-1",
                "json_path": "$.missing",
            }
        ],
        "time_json_path": "",
        "time_parse": "",
    }
    loader = HttpRequestLoader()
    loader.requests["http-1"] = request_data
    loader.request_info["http-1"] = {
        "method": "GET",
        "url": "https://example.com",
        "interval_seconds": 60,
    }
    loader.json_paths["http-1"] = data_parser.compile_json_paths(request_data["point_list"])
    loader.failure_counts["http-1"] = 0
    monkeypatch.setattr(
        "app.domain.collector.loader.http_request_loader.HttpUtil._request",
        lambda **kwargs: (True, {}),
    )
    offline = []
    monkeypatch.setattr(status_storage, "set_all_offline", lambda structure, *args: offline.append(structure))

    loader.execute_request("http-1")

    assert loader.failure_counts["http-1"] == 1
    assert offline == [_event_request_data(request_data)]


def test_storage_exception_counts_as_http_failure(monkeypatch, data_consumer) -> None:
    """解析后的 SQL/Redis 处理异常不能被误判为一次成功请求。"""
    request_data = {
        "terminal_list": [],
        "point_list": [],
        "time_json_path": "",
        "time_parse": "",
    }
    loader = HttpRequestLoader()
    loader.requests["http-1"] = request_data
    loader.request_info["http-1"] = {
        "method": "GET",
        "url": "https://example.com",
        "interval_seconds": 60,
    }
    loader.failure_counts["http-1"] = 0
    monkeypatch.setattr(
        "app.domain.collector.loader.http_request_loader.HttpUtil._request",
        lambda **kwargs: (True, {}),
    )
    monkeypatch.setattr(status_storage, "update_online_statuses", lambda *args: None)
    monkeypatch.setattr(sql_storage, "save", lambda measurements: 0)
    monkeypatch.setattr(redis_storage, "save", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("redis failed")))
    offline = []
    monkeypatch.setattr(status_storage, "set_all_offline", lambda structure, *args: offline.append(structure))

    loader.execute_request("http-1")

    assert loader.failure_counts["http-1"] == 1
    assert offline == [_event_request_data(request_data)]
