import numpy as np

from app.core.algorithm import algorithm_registry
from app.core.algorithm.anomaly import IsolationForestDetector, RobustZScoreDetector
from app.core.algorithm.clustering import KMeansAnalyzer
from app.core.algorithm.forecasting import AutoRegressionForecaster, HoltWintersForecaster, LinearTrendForecaster, MovingAverageForecaster


def test_robust_zscore_marks_large_outlier() -> None:
    values = np.array([10.0] * 20 + [100.0])
    result = RobustZScoreDetector().run(values, {"threshold": 3.5})
    assert result["labels"][-1] is True
    assert sum(result["labels"]) == 1


def test_isolation_forest_is_deterministic() -> None:
    values = np.array([[float(index % 5)] for index in range(50)] + [[100.0]])
    first = IsolationForestDetector().run(values, {"contamination": 0.02})
    second = IsolationForestDetector().run(values, {"contamination": 0.02})
    assert first == second
    assert first["labels"][-1] is True


def test_kmeans_auto_selects_and_returns_pca() -> None:
    values = np.vstack((np.zeros((20, 2)), np.ones((20, 2)) * 10))
    result = KMeansAnalyzer().run(values, {"cluster_count": "auto"})
    assert result["cluster_count"] == 2
    assert len(result["pca"]["coordinates"]) == 40
    assert result["silhouette_score"] > 0.9


def test_simple_forecasters_return_backtest_metrics_and_future() -> None:
    values = np.arange(1, 101, dtype=float)
    for model, parameters in (
        (MovingAverageForecaster(), {"window_size": 5}),
        (LinearTrendForecaster(), {"training_window": "auto"}),
    ):
        result = model.run(values, 10, {**parameters, "backtest_ratio": 0.2, "prediction_interval": 0.95})
        assert len(result["forecast_values"]) == 10
        assert set(result["metrics"]) == {"mae", "rmse", "smape"}


def test_statsmodels_forecasters_return_backtest_metrics_and_future() -> None:
    ticks = np.arange(120, dtype=float)
    values = 20 + ticks * 0.05 + np.sin(ticks * 2 * np.pi / 12)
    for model, parameters in (
        (HoltWintersForecaster(), {"trend": "additive", "seasonal": "none"}),
        (AutoRegressionForecaster(), {"lags": 5}),
    ):
        result = model.run(values, 10, {**parameters, "backtest_ratio": 0.2, "prediction_interval": 0.95})
        assert len(result["forecast_values"]) == 10
        assert set(result["metrics"]) == {"mae", "rmse", "smape"}


def test_algorithm_catalog_contains_parameter_help_and_chinese_options() -> None:
    catalog = algorithm_registry.catalog()
    robust = next(item for item in catalog["anomaly"] if item["name"] == "robust_zscore")
    baseline = next(item for item in robust["parameters"] if item["name"] == "baseline")

    assert robust["description"]
    assert baseline["label"] == "基线类型"
    assert baseline["description"]
    assert baseline["option_labels"] == {"global": "全局基线", "rolling": "滚动基线"}
