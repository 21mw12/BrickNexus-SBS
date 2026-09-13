import numpy as np

from app.common.validators import ValidationError
from app.core.algorithm.result import risk_0_100


class RobustZScoreDetector:
    @staticmethod
    def _scores(values: np.ndarray) -> np.ndarray:
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        if mad == 0:
            if np.ptp(values) == 0:
                return np.zeros_like(values, dtype=float)
            return np.where(values == median, 0.0, np.sign(values - median) * 1_000_000.0)
        return 0.6745 * (values - median) / mad

    def run(self, values: np.ndarray, parameters: dict) -> dict:
        series = np.asarray(values, dtype=float).reshape(-1)
        threshold = float(parameters.get("threshold", 3.5))
        baseline = parameters.get("baseline", "global")
        direction = parameters.get("direction", "both")
        if threshold < 1 or threshold > 10 or baseline not in {"global", "rolling"} or direction not in {"both", "high", "low"}:
            raise ValidationError("invalid Robust Z-Score parameters")
        scores = np.full(len(series), np.nan)
        if baseline == "global":
            scores = self._scores(series)
        else:
            window = int(parameters.get("window_size", 20))
            if window < 10 or window >= len(series):
                raise ValidationError("window_size must be between 10 and sample_count - 1")
            for index in range(window, len(series)):
                baseline_values = series[index - window:index]
                combined = np.append(baseline_values, series[index])
                scores[index] = self._scores(combined)[-1]
        comparable = np.abs(scores) if direction == "both" else scores if direction == "high" else -scores
        labels = np.where(np.isnan(comparable), False, comparable >= threshold)
        return {
            "raw_scores": [None if np.isnan(value) else round(float(value), 6) for value in scores],
            "risk_scores": [None if np.isnan(value) else risk for value, risk in zip(scores, risk_0_100(np.nan_to_num(comparable, nan=0.0)))],
            "labels": labels.tolist(),
            "threshold": threshold,
        }
