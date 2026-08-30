"""Largest-Triangle-Three-Buckets（LTTB）时间序列压缩。"""

from collections.abc import Iterable, Iterator
from datetime import datetime

HistoryPoint = tuple[datetime, float]


def _read_exact(iterator: Iterator[HistoryPoint], size: int) -> list[HistoryPoint]:
    """从流中读取指定数量；计数与实际结果不一致时明确报错。"""
    bucket = []
    for _ in range(size):
        try:
            bucket.append(next(iterator))
        except StopIteration as exc:
            raise ValueError("measurement count changed during history query") from exc
    return bucket


def _average(bucket: list[HistoryPoint]) -> tuple[float, float]:
    """计算下一个时间桶的平均时间戳和值。"""
    size = len(bucket)
    return (
        sum(item[0].timestamp() for item in bucket) / size,
        sum(item[1] for item in bucket) / size,
    )


def lttb_downsample(
    points: Iterable[HistoryPoint],
    raw_count: int,
    threshold: int,
) -> list[HistoryPoint]:
    """
    流式执行精确 LTTB。

    内存中仅保留当前桶、下一个桶和最终结果。面积相同时保留时间更早的点，
    因此相同输入始终得到相同结果。
    """
    if threshold < 3:
        raise ValueError("LTTB threshold must be at least 3")
    iterator = iter(points)
    if raw_count <= threshold:
        return list(iterator)
    if raw_count < 3:
        return list(iterator)

    try:
        first = next(iterator)
    except StopIteration:
        return []

    bucket_count = threshold - 2
    interior_count = raw_count - 2
    # 使用整数除法计算边界，避免浮点数舍入使桶遗漏或重复数据。
    boundaries = [
        1 + (index * interior_count) // bucket_count
        for index in range(bucket_count + 1)
    ]
    candidate_bucket = _read_exact(iterator, boundaries[1] - boundaries[0])
    selected = [first]
    previous = first
    last: HistoryPoint | None = None

    for bucket_index in range(bucket_count):
        if bucket_index + 1 < bucket_count:
            next_bucket = _read_exact(
                iterator,
                boundaries[bucket_index + 2] - boundaries[bucket_index + 1],
            )
            average_x, average_y = _average(next_bucket)
        else:
            try:
                last = next(iterator)
            except StopIteration as exc:
                raise ValueError("measurement count changed during history query") from exc
            next_bucket = []
            average_x, average_y = last[0].timestamp(), last[1]

        previous_x = previous[0].timestamp()
        previous_y = previous[1]
        best_point = candidate_bucket[0]
        best_area = -1.0
        for candidate in candidate_bucket:
            candidate_x = candidate[0].timestamp()
            # 三角形面积无需除以 2；只比较大小。使用 > 可在相同面积时保留较早数据。
            area = abs(
                (previous_x - average_x) * (candidate[1] - previous_y)
                - (previous_x - candidate_x) * (average_y - previous_y)
            )
            if area > best_area:
                best_area = area
                best_point = candidate

        selected.append(best_point)
        previous = best_point
        candidate_bucket = next_bucket

    if last is None:
        raise ValueError("measurement count changed during history query")
    selected.append(last)
    return selected
