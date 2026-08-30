"""SQL 与 Redis 存储测试。"""

import json
import importlib
from contextlib import nullcontext
from datetime import datetime, timezone

from app.domain.data.storage.redis_storage import RedisStorage
from app.domain.collector.storage.request_state_storage import RequestStateStorage
from app.domain.data.storage.sql_storage import SqlStorage
from app.domain.data.storage.status_storage import status_storage
from app.infra.DB.SQLConnection import sql_manager
from app.infra.Redis.RedisManager import redis_manager


def test_sql_storage_writes_measurement_rows(monkeypatch) -> None:
    storage = SqlStorage()
    saved = {}
    monkeypatch.setattr(sql_manager, "get_db", lambda _key: nullcontext(object()))
    monkeypatch.setattr(
        storage.repository,
        "upsert_many",
        lambda rows, db: saved.update(rows=rows) or len(rows),
    )
    measurement_time = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)

    count = storage.save(
        [
            {
                "point_id": "point-1",
                "sensor_id": "sensor-1",
                "terminal_id": "terminal-1",
                "time": measurement_time,
                "value": 12.5,
            }
        ]
    )

    assert count == 1
    assert saved["rows"] == [
        {"point_id": "point-1", "time": measurement_time, "value": 12.5}
    ]


def test_redis_storage_builds_terminal_tree_and_preserves_old_value(monkeypatch) -> None:
    cache = {}
    published = []

    class _Pipeline:
        def set(self, key, value):
            cache[key] = value
            return self

        def publish(self, channel, message):
            published.append((channel, message))
            return self

        def execute(self):
            return []

    monkeypatch.setattr(redis_manager, "get", lambda key: cache.get(key))
    monkeypatch.setattr(redis_manager, "pipeline", lambda transaction=True: _Pipeline())
    storage = RedisStorage()
    request_data = {
        "terminal_list": ["terminal-1"],
        "point_list": [
            {"point_id": "point-1", "sensor_id": "sensor-1", "terminal_id": "terminal-1", "json_path": "$.a", "unit": "kW", "point_description": "设备当前有功功率"},
            {"point_id": "point-2", "sensor_id": "sensor-1", "terminal_id": "terminal-1", "json_path": "$.b", "unit": "V", "point_description": "设备当前电压"},
        ],
    }
    first_time = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
    storage.save(
        request_data,
        [{"point_id": "point-1", "value": 10}, {"point_id": "point-2", "value": 20}],
        {"sensor-1": True},
        True,
        first_time,
    )

    second_time = datetime(2026, 8, 5, 12, 1, tzinfo=timezone.utc)
    storage.save(
        request_data,
        [{"point_id": "point-1", "value": 11}],
        {"sensor-1": True},
        True,
        second_time,
    )

    snapshot = json.loads(cache["terminal:latest:terminal-1"])
    assert snapshot == {
        "terminal_id": "terminal-1",
        "terminal_status": True,
        "sensor_list": [
            {
                "sensor_id": "sensor-1",
                "sensor_status": True,
                "point_list": [
                    {"point_id": "point-1", "value": 11, "unit": "kW", "point_description": "设备当前有功功率"},
                    {"point_id": "point-2", "value": 20, "unit": "V", "point_description": "设备当前电压"},
                ],
            }
        ],
        "time": second_time.isoformat(),
    }
    assert published == [
        ("terminal:updates", "terminal-1"),
        ("terminal:updates", "terminal-1"),
    ]


def test_request_state_storage_deactivates_request(monkeypatch) -> None:
    """采集器自动停止时只执行一次 Request 状态 UPDATE。"""
    executed = []

    class _FakeDb:
        def execute(self, statement):
            executed.append(statement)

    monkeypatch.setattr(sql_manager, "get_db", lambda _key: nullcontext(_FakeDb()))

    RequestStateStorage().deactivate("request-1")

    assert len(executed) == 1
    assert executed[0].compile().params["status"] is False


def test_offline_status_refreshes_redis_and_triggers_notification_path(monkeypatch) -> None:
    """离线状态也通过 RedisStorage.save 写快照，因此会走相同发布通知路径。"""
    saved = []

    class _FakeDb:
        def execute(self, statement):
            return None

    request_data = {
        "terminal_list": ["terminal-1"],
        "point_list": [{"sensor_id": "sensor-1"}],
    }
    monkeypatch.setattr(sql_manager, "get_db", lambda key: nullcontext(_FakeDb()))
    status_storage_module = importlib.import_module(
        "app.domain.data.storage.status_storage"
    )
    monkeypatch.setattr(
        status_storage_module.redis_storage,
        "save",
        lambda *args, **kwargs: saved.append((args, kwargs)),
    )

    status_storage.set_all_offline(request_data)

    assert len(saved) == 1
    args, kwargs = saved[0]
    assert args[0] == request_data
    assert kwargs["terminal_status"] is False
    assert kwargs["sensor_statuses"] == {"sensor-1": False}
