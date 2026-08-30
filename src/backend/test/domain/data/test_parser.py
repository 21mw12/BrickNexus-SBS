"""API/MQTT 共用解析器测试。"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.domain.collector.parser.data_parser import DataParser
from app.domain.collector.parser.time_parser import TimeParser


def test_time_parser_uses_configured_time() -> None:
    fallback = datetime(2026, 8, 5, tzinfo=timezone.utc)

    result = TimeParser().parse(
        {"time": "2026-08-05 14:30:20"},
        "$.time",
        "yyyy-MM-dd hh:mm:ss",
        fallback,
    )

    assert result == datetime(2026, 8, 5, 14, 30, 20, tzinfo=ZoneInfo("Asia/Shanghai"))


def test_time_parser_falls_back_when_time_is_missing_or_invalid() -> None:
    fallback = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
    parser = TimeParser()

    assert parser.parse({}, "$.time", "yyyy-MM-dd hh:mm:ss", fallback) == fallback
    assert parser.parse({"time": "bad"}, "$.time", "yyyy-MM-dd hh:mm:ss", fallback) == fallback
    assert parser.parse({"time": "2026-08-05"}, "$.[", "yyyy-MM-dd", fallback) == fallback
    assert parser.parse({}, "", "", fallback) == fallback


def test_time_parser_system_fallback_uses_shanghai_timezone() -> None:
    result = TimeParser().parse({}, "", "")

    assert result.tzinfo == ZoneInfo("Asia/Shanghai")


def test_data_parser_marks_sensor_online_when_any_point_succeeds() -> None:
    points = [
        {"point_id": "point-1", "sensor_id": "sensor-1", "terminal_id": "terminal-1", "json_path": "$.ok"},
        {"point_id": "point-2", "sensor_id": "sensor-1", "terminal_id": "terminal-1", "json_path": "$.missing"},
    ]
    parser = DataParser()

    result = parser.parse({"ok": 10}, points, parser.compile_json_paths(points))

    assert result["sensor_statuses"] == {"sensor-1": True}
    assert len(result["measurements"]) == 1
