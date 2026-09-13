from datetime import datetime, timedelta, timezone

import numpy as np

from app.core.data_processing import DataQualityAnalyzer, PreprocessingPipeline, TimeSeriesDataset


def _dataset() -> TimeSeriesDataset:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return TimeSeriesDataset(
        ["p1", "p2"],
        [start + timedelta(minutes=index) for index in range(5)],
        [[1, 10], [2, None], [None, 30], [4, 40], [5, 50]],
        {"p1": 4, "p2": 4},
        60,
    )


def test_quality_reports_missing_values() -> None:
    report = DataQualityAnalyzer.analyze(_dataset())
    assert report.raw_count == 8
    assert report.missing_count == 2
    assert report.missing_ratio == 0.2


def test_pipeline_interpolates_and_standardizes() -> None:
    result = PreprocessingPipeline().run(_dataset(), missing_strategy="interpolate", max_gap=1, scaling="standard")
    assert result.quality.interpolated_count == 2
    assert result.quality.dropped_count == 0
    assert np.allclose(np.mean(result.model_values, axis=0), [0, 0])
