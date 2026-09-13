import numpy as np

from app.common.validators import ValidationError
from app.core.algorithm.result import regression_metrics


def finish_forecast(actual: np.ndarray, backtest: np.ndarray, future: np.ndarray, interval: float) -> dict:
    if len(actual) != len(backtest):
        raise ValidationError("backtest result length mismatch")
    residual = np.abs(actual - backtest)
    margin = float(np.quantile(residual, interval)) if len(residual) >= 3 else None
    return {
        "backtest_values": backtest.tolist(),
        "forecast_values": future.tolist(),
        "lower": None if margin is None else (future - margin).tolist(),
        "upper": None if margin is None else (future + margin).tolist(),
        "metrics": regression_metrics(actual, backtest),
    }
