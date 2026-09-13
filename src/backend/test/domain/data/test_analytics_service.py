from datetime import datetime, timedelta
from math import sin
from zoneinfo import ZoneInfo

import pytest

from app.domain.analytics.schema import AnalyticsRequest
from app.domain.analytics.service import AnalyticsService


class _QueryService:
    def stream_full(self, point_id, start_time, end_time, db):
        offset = 10 if point_id == "p2" else 0
        rows = [(start_time + timedelta(minutes=index), sin(index / 5) + offset) for index in range(100)]
        return len(rows), iter(rows)


class _SparseQueryService:
    """模拟三小时只有约 68 条原始数据、但请求 500 个展示桶的真实场景。"""

    def stream_full(self, point_id, start_time, end_time, db):
        offset = 3 if point_id == "p2" else 0
        span = (end_time - start_time).total_seconds()
        rows = [
            (
                start_time + timedelta(seconds=span * index / 68),
                20 + offset + index * 0.03 + sin(index / 4),
            )
            for index in range(68)
        ]
        return len(rows), iter(rows)


def test_service_uses_shared_reader_and_returns_fixed_buckets() -> None:
    request = AnalyticsRequest(
        analysis_type="clustering",
        point_ids=["p1", "p2"],
        start_time="2026-09-01 00:00:00",
        end_time="2026-09-01 02:00:00",
        sample_count=100,
        algorithm={"name": "kmeans", "mode": "joint", "parameters": {"cluster_count": 2}},
    )
    service = AnalyticsService(query_service=_QueryService())
    result = service.run(request, object(), now=datetime(2026, 9, 2, tzinfo=ZoneInfo("Asia/Shanghai")))
    assert result["sampling"]["actual_sample_count"] == 100
    assert result["result"]["cluster_count"] == 2
    assert result["timezone"] == "Asia/Shanghai"


def test_anomaly_result_preserves_missing_buckets_on_display_axis() -> None:
    request = AnalyticsRequest(
        analysis_type="anomaly",
        point_ids=["p1"],
        start_time="2026-09-01 00:00:00",
        end_time="2026-09-01 02:00:00",
        sample_count=100,
        algorithm={"name": "robust_zscore", "mode": "per_point", "parameters": {}},
    )
    result = AnalyticsService(query_service=_QueryService()).run(
        request, object(), now=datetime(2026, 9, 2, tzinfo=ZoneInfo("Asia/Shanghai"))
    )["result"]["series"][0]

    assert len(result["times"]) == 100
    assert len(result["labels"]) == 100
    assert len(result["values_by_point"][0]) == 100
    assert None in result["values_by_point"][0]


def test_forecast_history_preserves_raw_missing_buckets() -> None:
    request = AnalyticsRequest(
        analysis_type="forecasting",
        point_ids=["p1"],
        start_time="2026-09-01 00:00:00",
        end_time="2026-09-01 02:00:00",
        sample_count=100,
        algorithm={"name": "moving_average", "mode": "per_point", "parameters": {}},
    )
    result = AnalyticsService(query_service=_QueryService()).run(
        request, object(), now=datetime(2026, 9, 2, tzinfo=ZoneInfo("Asia/Shanghai"))
    )["result"]["points"][0]

    assert len(result["history_times"]) == 100
    assert len(result["history_values"]) == 100
    assert None in result["history_values"]


@pytest.mark.parametrize("algorithm", ["holt_winters", "autoregression"])
def test_statistical_forecasts_support_sparse_three_hour_500_bucket_request(algorithm: str) -> None:
    parameters = {"lags": 5} if algorithm == "autoregression" else {
        "trend": "additive",
        "seasonal": "none",
        "seasonal_periods": 24,
    }
    request = AnalyticsRequest(
        analysis_type="forecasting",
        point_ids=["p1", "p2"],
        start_time="2026-08-12 19:00:00",
        end_time="2026-08-12 22:00:00",
        sample_count=500,
        preprocessing={"aggregation": "mean", "missing_strategy": "interpolate", "max_gap": 3},
        algorithm={
            "name": algorithm,
            "mode": "per_point",
            "parameters": {
                "horizon": 20,
                "backtest_ratio": 0.2,
                "prediction_interval": 0.95,
                **parameters,
            },
        },
    )

    result = AnalyticsService(query_service=_SparseQueryService()).run(
        request,
        object(),
        now=datetime(2026, 9, 2, tzinfo=ZoneInfo("Asia/Shanghai")),
    )["result"]

    assert len(result["points"]) == 2
    assert all(point["status"] == "success" for point in result["points"])
    assert all(len(point["forecast_values"]) == 20 for point in result["points"])
