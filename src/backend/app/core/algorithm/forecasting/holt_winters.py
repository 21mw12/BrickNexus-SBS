import numpy as np

from app.common.validators import ValidationError
from .common import finish_forecast


class HoltWintersForecaster:
    def _fit(self, train: np.ndarray, count: int, parameters: dict) -> np.ndarray:
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
        except ModuleNotFoundError as exc:
            raise ValidationError("后端运行环境缺少 statsmodels，无法执行 Holt-Winters 预测") from exc
        trend = parameters.get("trend", "additive")
        seasonal = parameters.get("seasonal", "none")
        trend_arg = None if trend == "none" else "add"
        seasonal_arg = None if seasonal == "none" else "add"
        periods = int(parameters.get("seasonal_periods", 0)) if seasonal_arg else None
        if seasonal_arg and (not periods or len(train) < periods * 2):
            raise ValidationError("Holt-Winters seasonality requires at least two complete periods")
        model = ExponentialSmoothing(train, trend=trend_arg, seasonal=seasonal_arg, seasonal_periods=periods, initialization_method="estimated").fit(optimized=True)
        return np.asarray(model.forecast(count), dtype=float)

    def run(self, values: np.ndarray, horizon: int, parameters: dict) -> dict:
        series = np.asarray(values, dtype=float).reshape(-1)
        split = len(series) - max(3, int(len(series) * float(parameters.get("backtest_ratio", 0.2))))
        backtest = self._fit(series[:split], len(series) - split, parameters)
        future = self._fit(series, horizon, parameters)
        return finish_forecast(series[split:], backtest, future, float(parameters.get("prediction_interval", 0.95)))
