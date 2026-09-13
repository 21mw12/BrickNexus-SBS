from dataclasses import asdict, dataclass, field
from datetime import datetime

import numpy as np


@dataclass
class TimeSeriesDataset:
    point_ids: list[str]
    timestamps: list[datetime]
    values: list[list[float | None]]
    raw_counts: dict[str, int]
    interval_seconds: float


@dataclass
class DataQualityReport:
    raw_count: int
    bucket_count: int
    valid_count: int
    missing_count: int
    missing_ratio: float
    interpolated_count: int = 0
    dropped_count: int = 0
    constant_point_ids: list[str] = field(default_factory=list)
    low_variance_point_ids: list[str] = field(default_factory=list)
    max_consecutive_gap: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PreparedDataset:
    point_ids: list[str]
    timestamps: list[datetime]
    raw_values: list[list[float | None]]
    model_values: np.ndarray
    model_timestamps: list[datetime]
    interval_seconds: float
    quality: DataQualityReport
    center: np.ndarray | None = None
    scale: np.ndarray | None = None
    scaling: str = "none"
