"""Shared numerical result helpers."""

import numpy as np


def risk_0_100(scores: np.ndarray) -> list[float]:
    values = np.asarray(scores, dtype=float)
    if not len(values):
        return []
    minimum, maximum = float(np.min(values)), float(np.max(values))
    if maximum == minimum:
        return [0.0] * len(values)
    return [round(float(value), 6) for value in ((values - minimum) / (maximum - minimum) * 100)]


def regression_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    error = np.asarray(actual, dtype=float) - np.asarray(predicted, dtype=float)
    denominator = np.abs(actual) + np.abs(predicted)
    smape_values = np.where(denominator == 0, 0.0, 200 * np.abs(error) / denominator)
    return {
        "mae": round(float(np.mean(np.abs(error))), 6),
        "rmse": round(float(np.sqrt(np.mean(error ** 2))), 6),
        "smape": round(float(np.mean(smape_values)), 6),
    }
