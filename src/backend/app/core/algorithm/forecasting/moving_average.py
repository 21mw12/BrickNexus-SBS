import numpy as np

from app.common.validators import ValidationError
from .common import finish_forecast


class MovingAverageForecaster:
    def run(self, values: np.ndarray, horizon: int, parameters: dict) -> dict:
        series = np.asarray(values, dtype=float).reshape(-1)
        window = int(parameters.get("window_size", 5))
        ratio = float(parameters.get("backtest_ratio", 0.2))
        split = len(series) - max(3, int(len(series) * ratio))
        if window < 2 or split < window:
            raise ValidationError("not enough samples for moving average window")
        predicted = [float(np.mean(series[max(0, index-window):index])) for index in range(split, len(series))]
        future = np.repeat(np.mean(series[-window:]), horizon)
        return finish_forecast(series[split:], np.array(predicted), future, float(parameters.get("prediction_interval", 0.95)))
