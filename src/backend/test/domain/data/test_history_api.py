import importlib
import json

from app.domain.data.api.HistoryAPI import query_history
from app.domain.data.schema.HistorySchema import HistoryQuerySchema

history_api_module = importlib.import_module("app.domain.data.api.HistoryAPI")


class _Db:
    def __init__(self):
        self.rolled_back = False

    def rollback(self):
        self.rolled_back = True


def _schema() -> HistoryQuerySchema:
    return HistoryQuerySchema(
        point_ids=["point-1"],
        start_time="2026-08-01 00:00:00",
        end_time="2026-08-01 00:15:00",
        sample_count=100,
    )


def _content(response) -> dict:
    return json.loads(response.body)


def test_history_api_returns_400_when_any_point_is_invalid(monkeypatch) -> None:
    monkeypatch.setattr(
        history_api_module.sensor_point_repository,
        "get_sensor_ids_by_point_ids",
        lambda point_ids, db: {},
    )
    monkeypatch.setattr(
        history_api_module.history_service,
        "query",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not query")),
    )

    response = query_history(_schema(), "Bearer token", _Db())

    assert response.status_code == 400
    assert _content(response)["message"] == "invalid point_ids"


def test_history_api_returns_403_when_any_sensor_is_not_viewable(monkeypatch) -> None:
    monkeypatch.setattr(
        history_api_module.sensor_point_repository,
        "get_sensor_ids_by_point_ids",
        lambda point_ids, db: {"point-1": "sensor-1"},
    )
    monkeypatch.setattr(
        history_api_module,
        "check_asset_instance_permission",
        lambda token, asset_id, code, db: False,
    )
    monkeypatch.setattr(
        history_api_module.history_service,
        "query",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not query")),
    )

    response = query_history(_schema(), "Bearer token", _Db())

    assert response.status_code == 403
    assert _content(response)["message"] == "permission denied"


def test_history_api_wraps_successful_result(monkeypatch) -> None:
    expected = {"timezone": "Asia/Shanghai", "points": []}
    monkeypatch.setattr(
        history_api_module.sensor_point_repository,
        "get_sensor_ids_by_point_ids",
        lambda point_ids, db: {"point-1": "sensor-1"},
    )
    monkeypatch.setattr(
        history_api_module,
        "check_asset_instance_permission",
        lambda token, asset_id, code, db: True,
    )
    monkeypatch.setattr(
        history_api_module.history_service,
        "query",
        lambda data, db: expected,
    )

    response = query_history(_schema(), "Bearer token", _Db())

    assert response.status_code == 200
    assert _content(response)["data"] == expected
