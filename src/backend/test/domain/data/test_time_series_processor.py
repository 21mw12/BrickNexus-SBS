from datetime import datetime, timedelta, timezone

from app.domain.data.service.TimeSeriesProcessor import TimeSeriesProcessor
from app.core.algorithm import TimeSeriesProcessor as CoreTimeSeriesProcessor
from app.core.algorithm import CorrelationAnalyzer
import pytest


def test_lttb_supports_tick_axis_and_keeps_endpoints() -> None:
    points = [(tick, float((tick * tick) % 17)) for tick in range(200)]

    result = TimeSeriesProcessor.lttb(iter(points), len(points), 40)

    assert len(result) == 40
    assert result[0] == points[0]
    assert result[-1] == points[-1]


def test_fixed_interval_supports_datetime_and_tick() -> None:
    ticks = TimeSeriesProcessor.fixed_interval(
        [(0, 1.0), (1, 3.0), (2, 8.0), (3, None)], 2, "mean", 0
    )
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    times = TimeSeriesProcessor.fixed_interval(
        [(started_at, 1.0), (started_at + timedelta(seconds=5), 5.0)],
        10,
        "max",
        started_at,
    )

    assert ticks == [(0, 2.0), (2, 8.0)]
    assert times == [(started_at, 5.0)]


def test_lttb_with_gaps_preserves_missing_boundary() -> None:
    points = [(index, None if 20 <= index <= 24 else float(index)) for index in range(100)]

    result = TimeSeriesProcessor.lttb_with_gaps(points, 20)

    missing = [item for item in result if item[1] is None]
    assert missing == [(20, None), (24, None)]
    assert result == sorted(result)


def test_compatibility_import_uses_core_processor() -> None:
    assert TimeSeriesProcessor is CoreTimeSeriesProcessor


def test_dense_fixed_count_preserves_empty_buckets_and_boundaries() -> None:
    result = TimeSeriesProcessor.dense_fixed_count(
        [(0, 1.0), (1, 3.0), (4, 8.0), (9, 10.0), (10, 99.0)],
        0,
        10,
        5,
    )

    assert result == [2.0, None, 8.0, None, 10.0]


def test_dense_fixed_count_treats_non_finite_measurements_as_missing() -> None:
    result = TimeSeriesProcessor.dense_fixed_count(
        [(0, 1.0), (1, float("nan")), (2, float("inf")), (3, 4.0)],
        0,
        4,
        4,
    )

    assert result == [1.0, None, None, 4.0]


def test_min_max_normalization_handles_null_empty_and_constant_series() -> None:
    assert TimeSeriesProcessor.normalize_min_max([2.0, None, 6.0]) == [
        0.0,
        None,
        100.0,
    ]
    assert TimeSeriesProcessor.normalize_min_max([4.0, None, 4.0]) == [
        50.0,
        None,
        50.0,
    ]
    assert TimeSeriesProcessor.normalize_min_max([None, None]) == [None, None]


def test_correlation_is_pairwise_and_missing_value_aware() -> None:
    result = CorrelationAnalyzer.calculate(
        [[1.0, 2.0, None, 4.0], [2.0, 4.0, 9.0, 8.0]]
    )
    assert result["pair_counts"] == [[3, 3], [3, 4]]
    assert result["pearson"][0][1] == pytest.approx(1.0)
    assert result["spearman"][1][0] == pytest.approx(1.0)


def test_spearman_uses_average_ranks_for_ties() -> None:
    result = CorrelationAnalyzer.calculate(
        [[1.0, 1.0, 2.0, 3.0], [1.0, 2.0, 3.0, 4.0]]
    )
    assert result["spearman"][0][1] == pytest.approx(0.9486832980505138)


def test_correlation_returns_null_for_too_few_pairs_or_constant_values() -> None:
    result = CorrelationAnalyzer.calculate(
        [[1.0, 1.0, None], [2.0, 3.0, 4.0], [1.0, 2.0, None]]
    )
    assert result["pearson"][0][1] is None
    assert result["spearman"][0][0] is None
    assert result["pair_counts"][1][2] == 2
