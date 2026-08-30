"""共用 Request 数据处理结构加载测试。"""

from contextlib import nullcontext
from types import SimpleNamespace

from app.domain.collector.loader.request_data_loader import RequestDataLoader
from app.infra.DB.SQLConnection import sql_manager


class _FakeDb:
    def get(self, _model, request_id):
        return SimpleNamespace(
            request_id=request_id,
            time_json_path="$.time",
            time_parse="yyyy-MM-dd hh:mm:ss",
        )

    def scalars(self, _statement):
        return SimpleNamespace(all=lambda: ["terminal-1", "terminal-2"])

    def execute(self, _statement):
        return SimpleNamespace(
            all=lambda: [
                SimpleNamespace(
                    point_id="point-1",
                    sensor_id="sensor-1",
                    terminal_id="terminal-1",
                    json_path="$.data.value",
                    unit="kW",
                    point_description="设备当前有功功率",
                ),
                SimpleNamespace(
                    point_id="point-2",
                    sensor_id="sensor-2",
                    terminal_id="terminal-2",
                    json_path="$.data.temperature",
                    unit="°C",
                    point_description="设备周围环境温度",
                ),
            ]
        )


def test_load_returns_processing_json_by_request_id(monkeypatch) -> None:
    monkeypatch.setattr(sql_manager, "get_db", lambda _key: nullcontext(_FakeDb()))

    result = RequestDataLoader().load("api-1")

    assert result == {
        "terminal_list": ["terminal-1", "terminal-2"],
        "point_list": [
            {
                "point_id": "point-1",
                "sensor_id": "sensor-1",
                "terminal_id": "terminal-1",
                "json_path": "$.data.value",
                "unit": "kW",
                "point_description": "设备当前有功功率",
            },
            {
                "point_id": "point-2",
                "sensor_id": "sensor-2",
                "terminal_id": "terminal-2",
                "json_path": "$.data.temperature",
                "unit": "°C",
                "point_description": "设备周围环境温度",
            },
        ],
        "time_json_path": "$.time",
        "time_parse": "yyyy-MM-dd hh:mm:ss",
    }
