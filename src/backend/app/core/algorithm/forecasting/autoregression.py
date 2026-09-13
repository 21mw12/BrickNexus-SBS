import numpy as np

from app.common.validators import ValidationError
from .common import finish_forecast


class AutoRegressionForecaster:
    @staticmethod
    def _fit(train: np.ndarray, count: int, lags: int) -> np.ndarray:
        try:
            from statsmodels.tsa.ar_model import AutoReg
        except ModuleNotFoundError as exc:
            raise ValidationError("后端运行环境缺少 statsmodels，无法执行自回归预测") from exc
        if len(train) < max(20, lags * 3):
            raise ValidationError("autoregression requires at least max(20, lags * 3) training samples")
        # statsmodels 0.15 已移除 old_names；不传该兼容参数可同时支持 0.14 和 0.15。
        model = AutoReg(train, lags=lags, trend="ct").fit()
        return np.asarray(model.predict(len(train), len(train) + count - 1), dtype=float)

    def run(self, values: np.ndarray, horizon: int, parameters: dict) -> dict:
        series = np.asarray(values, dtype=float).reshape(-1)
        lags = int(parameters.get("lags", 5))
        if not 1 <= lags <= 100:
            raise ValidationError("lags must be between 1 and 100")
        split = len(series) - max(3, int(len(series) * float(parameters.get("backtest_ratio", 0.2))))
        backtest = self._fit(series[:split], len(series) - split, lags)
        future = self._fit(series, horizon, lags)
        return finish_forecast(series[split:], backtest, future, float(parameters.get("prediction_interval", 0.95)))
