from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.common.validators import ValidationError
from app.domain.data.schema.HistorySchema import HistoryQuerySchema
from app.domain.data.service.HistoryService import HistoryService


class _MeasurementRepository:
    def __init__(self, series: dict[str, list[tuple[datetime, float]]]):
        self.series = series
        self.calls = []

    def stream_history(self, point_id, start_time, end_time, db):
        self.calls.append((point_id, start_time, end_time))
        points = self.series.get(point_id, [])
        return len(points), iter(points)


def _schema(**overrides) -> HistoryQuerySchema:
    payload = {
        "point_ids": ["point-1"],
        "start_time": "2026-08-13 14:45:00",
        "end_time": "2026-08-13 15:15:00",
        "sample_count": 100,
    }
    payload.update(overrides)
    return HistoryQuerySchema(**payload)


def test_schema_deduplicates_points_and_preserves_order() -> None:
    data = _schema(point_ids=[" point-2 ", "point-1", "point-2"])

    assert data.point_ids == ["point-2", "point-1"]


@pytest.mark.parametrize(
    "payload",
    [
        {"point_ids": []},
        {"point_ids": [str(index) for index in range(11)]},
        {"point_ids": [" "]},
        {"sample_count": 99},
        {"sample_count": 1001},
    ],
)
def test_schema_rejects_invalid_bounds(payload: dict) -> None:
    with pytest.raises(PydanticValidationError):
        _schema(**payload)


def test_future_end_is_clipped_and_short_actual_range_is_queried() -> None:
    business_timezone = ZoneInfo("Asia/Shanghai")
    now = datetime(2026, 8, 13, 14, 50, 30, tzinfo=business_timezone)
    measurement_time = datetime(2026, 8, 13, 6, 46, tzinfo=timezone.utc)
    measurements = _MeasurementRepository(
        {"point-1": [(measurement_time, 12.5)]}
    )
    service = HistoryService(measurements)

    result = service.query(_schema(), object(), now=now)

    assert result["actual_end_time"] == "2026-08-13 14:50:30"
    assert result["points"] == [
        {
            "point_id": "point-1",
            "original_count": 1,
            "returned_count": 1,
            "downsampled": False,
            "times": ["2026-08-13 14:46:00"],
            "values": [12.5],
        }
    ]
    assert measurements.calls[0][1] == datetime(2026, 8, 13, 6, 45, tzinfo=timezone.utc)
    assert measurements.calls[0][2] == now.astimezone(timezone.utc)


def test_each_point_is_downsampled_independently() -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    first = [(start + timedelta(minutes=index), float(index)) for index in range(200)]
    second = [(start + timedelta(minutes=index), float(index)) for index in range(2)]
    measurements = _MeasurementRepository({"point-1": first, "point-2": second})
    service = HistoryService(measurements)
    data = HistoryQuerySchema(
        point_ids=["point-2", "point-1"],
        start_time="2026-08-01 08:00:00",
        end_time="2026-08-01 12:00:00",
        sample_count=100,
    )

    result = service.query(
        data,
        object(),
        now=datetime(2026, 8, 2, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert [item["point_id"] for item in result["points"]] == ["point-2", "point-1"]
    assert result["points"][0]["returned_count"] == 2
    assert result["points"][0]["downsampled"] is False
    assert result["points"][1]["returned_count"] == 100
    assert result["points"][1]["downsampled"] is True
    for item in result["points"]:
        assert item["returned_count"] == len(item["times"]) == len(item["values"])


@pytest.mark.parametrize(
    ("start_time", "end_time", "message"),
    [
        ("2026-08-13T14:45:00", "2026-08-13 15:15:00", "must use"),
        ("2026-08-13 14:46:00", "2026-08-13 15:15:00", "15-minute"),
        ("2026-08-13 14:45:00", "2026-08-13 14:59:59", "at least"),
        ("2026-07-01 00:00:00", "2026-08-02 00:00:01", "31 days"),
    ],
)
def test_time_validation(start_time: str, end_time: str, message: str) -> None:
    service = HistoryService(_MeasurementRepository({}))

    with pytest.raises(ValidationError, match=message):
        service.query(
            _schema(start_time=start_time, end_time=end_time),
            object(),
            now=datetime(2026, 8, 14, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
