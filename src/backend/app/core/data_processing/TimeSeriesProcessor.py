"""与数据来源无关的时序采样、聚合和数值变换。"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from datetime import datetime, timedelta
from itertools import chain
from math import isfinite
from typing import Literal, TypeAlias

Coordinate: TypeAlias = datetime | int | float
SeriesPoint: TypeAlias = tuple[Coordinate, float | None]
NumericSeriesPoint: TypeAlias = tuple[Coordinate, float]
Aggregation = Literal["mean", "min", "max", "first", "last"]


def _x_value(value: Coordinate) -> float:
    return value.timestamp() if isinstance(value, datetime) else float(value)


def _read_exact(iterator: Iterator[NumericSeriesPoint], size: int) -> list[NumericSeriesPoint]:
    bucket: list[NumericSeriesPoint] = []
    for _ in range(size):
        try:
            bucket.append(next(iterator))
        except StopIteration as exc:
            raise ValueError("measurement count changed during query") from exc
    return bucket


def _average(bucket: Sequence[NumericSeriesPoint]) -> tuple[float, float]:
    size = len(bucket)
    return (sum(_x_value(item[0]) for item in bucket) / size, sum(item[1] for item in bucket) / size)


class TimeSeriesProcessor:
    """对 datetime 或数值横轴执行统一处理。"""

    @staticmethod
    def raw(points: Iterable[SeriesPoint]) -> list[SeriesPoint]:
        return list(points)

    @staticmethod
    def lttb(points: Iterable[NumericSeriesPoint], raw_count: int, threshold: int) -> list[NumericSeriesPoint]:
        """流式执行精确 LTTB；输入必须是不含 NULL 的有序序列。"""
        if threshold < 3:
            raise ValueError("LTTB threshold must be at least 3")
        iterator = iter(points)
        if raw_count <= threshold or raw_count < 3:
            return list(iterator)
        try:
            first = next(iterator)
        except StopIteration:
            return []
        bucket_count = threshold - 2
        interior_count = raw_count - 2
        boundaries = [1 + (index * interior_count) // bucket_count for index in range(bucket_count + 1)]
        candidate_bucket = _read_exact(iterator, boundaries[1] - boundaries[0])
        selected = [first]
        previous = first
        last: NumericSeriesPoint | None = None
        for bucket_index in range(bucket_count):
            if bucket_index + 1 < bucket_count:
                next_bucket = _read_exact(iterator, boundaries[bucket_index + 2] - boundaries[bucket_index + 1])
                average_x, average_y = _average(next_bucket)
            else:
                try:
                    last = next(iterator)
                except StopIteration as exc:
                    raise ValueError("measurement count changed during query") from exc
                next_bucket = []
                average_x, average_y = _x_value(last[0]), last[1]
            previous_x = _x_value(previous[0])
            previous_y = previous[1]
            best_point = candidate_bucket[0]
            best_area = -1.0
            for candidate in candidate_bucket:
                candidate_x = _x_value(candidate[0])
                area = abs((previous_x - average_x) * (candidate[1] - previous_y) - (previous_x - candidate_x) * (average_y - previous_y))
                if area > best_area:
                    best_area = area
                    best_point = candidate
            selected.append(best_point)
            previous = best_point
            candidate_bucket = next_bucket
        if last is None:
            raise ValueError("measurement count changed during query")
        selected.append(last)
        return selected

    @staticmethod
    def lttb_with_gaps(points: Sequence[SeriesPoint], threshold: int) -> list[SeriesPoint]:
        """对含 NULL 的序列分段采样，并保留每段缺失的边界。"""
        if len(points) <= threshold:
            return list(points)
        if threshold < 3:
            raise ValueError("LTTB threshold must be at least 3")
        compact: list[SeriesPoint] = []
        index = 0
        while index < len(points):
            if points[index][1] is not None:
                compact.append(points[index])
                index += 1
                continue
            start = index
            while index < len(points) and points[index][1] is None:
                index += 1
            compact.append(points[start])
            if index - start > 1:
                compact.append(points[index - 1])
        if len(compact) <= threshold:
            return compact
        numeric = [(coordinate, float(value)) for coordinate, value in compact if value is not None]
        gaps = [item for item in compact if item[1] is None]
        available = max(3, threshold - len(gaps))
        sampled = TimeSeriesProcessor.lttb(numeric, len(numeric), min(available, len(numeric))) if len(numeric) >= 3 else numeric
        return sorted([*sampled, *gaps], key=lambda item: _x_value(item[0]))

    @staticmethod
    def fixed_interval(points: Iterable[SeriesPoint], interval: float, aggregation: Aggregation = "mean", origin: Coordinate | None = None) -> list[SeriesPoint]:
        """按固定秒数或 tick 宽度聚合有序序列。"""
        if interval <= 0:
            raise ValueError("interval must be greater than zero")
        if aggregation not in {"mean", "min", "max", "first", "last"}:
            raise ValueError(f"unsupported aggregation: {aggregation}")
        source = iter(points)
        try:
            first_point = next(source)
        except StopIteration:
            return []
        anchor = origin if origin is not None else first_point[0]
        anchor_x = _x_value(anchor)
        buckets: dict[int, list[float]] = {}
        for coordinate, value in chain((first_point,), source):
            if value is None:
                continue
            bucket = int((_x_value(coordinate) - anchor_x) // interval)
            buckets.setdefault(bucket, []).append(float(value))
        result: list[SeriesPoint] = []
        for bucket, values in sorted(buckets.items()):
            if aggregation == "mean": value = sum(values) / len(values)
            elif aggregation == "min": value = min(values)
            elif aggregation == "max": value = max(values)
            elif aggregation == "first": value = values[0]
            else: value = values[-1]
            offset = bucket * interval
            coordinate = anchor + timedelta(seconds=offset) if isinstance(anchor, datetime) else type(anchor)(anchor_x + offset)
            result.append((coordinate, value))
        return result

    @staticmethod
    def dense_fixed_count(points: Iterable[SeriesPoint], start: Coordinate, end: Coordinate, bucket_count: int, aggregation: Aggregation = "mean") -> list[float | None]:
        """将区间 ``[start, end)`` 聚合为固定数量的稠密时间桶。"""
        if bucket_count <= 0:
            raise ValueError("bucket_count must be greater than zero")
        start_x, end_x = _x_value(start), _x_value(end)
        span = end_x - start_x
        if span <= 0:
            raise ValueError("end must be greater than start")
        if aggregation not in {"mean", "min", "max", "first", "last"}:
            raise ValueError(f"unsupported aggregation: {aggregation}")
        buckets: list[list[float]] = [[] for _ in range(bucket_count)]
        for coordinate, value in points:
            if value is None:
                continue
            numeric_value = float(value)
            if not isfinite(numeric_value):
                continue
            index = int(((_x_value(coordinate) - start_x) / span) * bucket_count)
            if 0 <= index < bucket_count:
                buckets[index].append(numeric_value)
        result: list[float | None] = []
        for values in buckets:
            if not values:
                result.append(None)
            elif aggregation == "mean": result.append(sum(values) / len(values))
            elif aggregation == "min": result.append(min(values))
            elif aggregation == "max": result.append(max(values))
            elif aggregation == "first": result.append(values[0])
            else: result.append(values[-1])
        return result

    @staticmethod
    def normalize_min_max(values: Sequence[float | None]) -> list[float | None]:
        """忽略缺失值，将单条序列映射到 0～100。"""
        numeric = [float(value) for value in values if value is not None]
        if not numeric:
            return [None] * len(values)
        minimum, maximum = min(numeric), max(numeric)
        if maximum == minimum:
            return [None if value is None else 50.0 for value in values]
        return [None if value is None else (float(value) - minimum) / (maximum - minimum) * 100.0 for value in values]

    @staticmethod
    def value_range(series: Sequence[Sequence[float | None]]) -> dict[str, float]:
        """计算多条序列的全局可绘制色阶。"""
        numeric = [float(value) for values in series for value in values if value is not None]
        if not numeric:
            return {"min": 0.0, "max": 1.0}
        minimum, maximum = min(numeric), max(numeric)
        if maximum == minimum:
            padding = abs(minimum) * 0.05 or 1.0
            return {"min": minimum - padding, "max": maximum + padding}
        return {"min": minimum, "max": maximum}


__all__ = ["Aggregation", "Coordinate", "NumericSeriesPoint", "SeriesPoint", "TimeSeriesProcessor"]
