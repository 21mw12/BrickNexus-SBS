from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.domain.data.schema.HistorySchema import HistoryHeatmapQuerySchema
from app.domain.data.service.HistoryHeatmapService import HistoryHeatmapService
from app.domain.data.service.HistoryService import HistoryService


class _MeasurementRepository:
    def __init__(self, series):
        self.series = series

    def stream_history(self, point_id, start_time, end_time, db):
        points = self.series.get(point_id, [])
        return len(points), iter(points)


def test_heatmap_returns_aligned_dense_and_correlation_matrices() -> None:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    left = [
        (start + timedelta(seconds=1), 1.0),
        (start + timedelta(seconds=10), 2.0),
        (start + timedelta(seconds=19), 3.0),
    ]
    right = [(time, value * 2) for time, value in left]
    repository = _MeasurementRepository({"left": left, "right": right})
    service = HistoryHeatmapService(repository, HistoryService(repository))
    data = HistoryHeatmapQuerySchema(
        point_ids=["left", "right"],
        start_time="2026-08-01 08:00:00",
        end_time="2026-08-01 08:15:00",
        sample_count=100,
    )

    result = service.query(
        data,
        object(),
        now=datetime(2026, 8, 2, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert len(result["times"]) == 100
    assert result["sample_count"] == 100
    assert result["requested_sample_count"] == 100
    assert result["interval_seconds"] == 9
    assert result["points"][0]["values"][:3] == [1.0, 2.0, 3.0]
    assert result["points"][0]["values"][3:] == [None] * 97
    assert result["points"][0]["normalized_values"][:3] == [0.0, 50.0, 100.0]
    assert result["correlations"]["pair_counts"][0][1] == 3
    assert result["correlations"]["pearson"][0][1] == pytest.approx(1.0)
    assert result["correlations"]["spearman"][0][1] == pytest.approx(1.0)
