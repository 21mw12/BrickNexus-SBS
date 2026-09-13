"""兼容入口；新代码应直接使用 :class:`TimeSeriesProcessor`。"""

from collections.abc import Iterable
from datetime import datetime

from .TimeSeriesProcessor import TimeSeriesProcessor

HistoryPoint = tuple[datetime, float]


def lttb_downsample(
    points: Iterable[HistoryPoint], raw_count: int, threshold: int
) -> list[HistoryPoint]:
    return TimeSeriesProcessor.lttb(points, raw_count, threshold)
