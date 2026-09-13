import numpy as np

from app.common.validators import ValidationError
from .common import finish_forecast


class LinearTrendForecaster:
    @staticmethod
    def _predict(train: np.ndarray, count: int, window: int | None) -> np.ndarray:
        selected = train[-window:] if window else train
        if len(selected) < 3:
            raise ValidationError("linear trend requires at least 3 training samples")
        x = np.arange(len(selected), dtype=float)
        slope, intercept = np.polyfit(x, selected, 1)
        return intercept + slope * np.arange(len(selected), len(selected) + count)

    def run(self, values: np.ndarray, horizon: int, parameters: dict) -> dict:
        series = np.asarray(values, dtype=float).reshape(-1)
        split = len(series) - max(3, int(len(series) * float(parameters.get("backtest_ratio", 0.2))))
        requested = parameters.get("training_window", "auto")
        window = None if requested == "auto" else int(requested)
        backtest = self._predict(series[:split], len(series) - split, window)
        future = self._predict(series, horizon, window)
        return finish_forecast(series[split:], backtest, future, float(parameters.get("prediction_interval", 0.95)))
