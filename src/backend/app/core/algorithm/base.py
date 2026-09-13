"""Task-specific contracts for reusable analytics algorithms."""

from typing import Any, Protocol

import numpy as np


class AnomalyDetector(Protocol):
    def run(self, values: np.ndarray, parameters: dict[str, Any]) -> dict: ...


class ClusterAnalyzer(Protocol):
    def run(self, values: np.ndarray, parameters: dict[str, Any]) -> dict: ...


class Forecaster(Protocol):
    def run(self, values: np.ndarray, horizon: int, parameters: dict[str, Any]) -> dict: ...
