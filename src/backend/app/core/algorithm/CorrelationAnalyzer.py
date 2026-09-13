"""缺失值感知的相关性分析算法。"""

from __future__ import annotations

from collections.abc import Sequence
from math import sqrt

NullableSeries = Sequence[float | None]


class CorrelationAnalyzer:
    MIN_PAIR_COUNT = 3

    @staticmethod
    def _pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
        count = len(left)
        if count < CorrelationAnalyzer.MIN_PAIR_COUNT:
            return None
        left_mean, right_mean = sum(left) / count, sum(right) / count
        left_delta = [value - left_mean for value in left]
        right_delta = [value - right_mean for value in right]
        left_square = sum(value * value for value in left_delta)
        right_square = sum(value * value for value in right_delta)
        if left_square == 0 or right_square == 0:
            return None
        covariance = sum(left_value * right_value for left_value, right_value in zip(left_delta, right_delta))
        return max(-1.0, min(1.0, covariance / sqrt(left_square * right_square)))

    @staticmethod
    def _average_ranks(values: Sequence[float]) -> list[float]:
        order = sorted(range(len(values)), key=values.__getitem__)
        ranks = [0.0] * len(values)
        start = 0
        while start < len(order):
            end = start + 1
            while end < len(order) and values[order[end]] == values[order[start]]:
                end += 1
            average_rank = (start + 1 + end) / 2.0
            for position in range(start, end):
                ranks[order[position]] = average_rank
            start = end
        return ranks

    @classmethod
    def calculate(cls, series: Sequence[NullableSeries]) -> dict[str, list[list]]:
        """一次生成 Pearson、Spearman 和逐对有效样本数量矩阵。"""
        size = len(series)
        if series and any(len(values) != len(series[0]) for values in series[1:]):
            raise ValueError("all series must have the same length")
        pearson: list[list[float | None]] = [[None] * size for _ in range(size)]
        spearman: list[list[float | None]] = [[None] * size for _ in range(size)]
        pair_counts: list[list[int]] = [[0] * size for _ in range(size)]
        for left_index in range(size):
            for right_index in range(left_index, size):
                paired = [(float(left), float(right)) for left, right in zip(series[left_index], series[right_index]) if left is not None and right is not None]
                left_values = [item[0] for item in paired]
                right_values = [item[1] for item in paired]
                count = len(paired)
                pearson_value = cls._pearson(left_values, right_values)
                spearman_value = cls._pearson(cls._average_ranks(left_values), cls._average_ranks(right_values))
                for row, column in ((left_index, right_index), (right_index, left_index)):
                    pair_counts[row][column] = count
                    pearson[row][column] = pearson_value
                    spearman[row][column] = spearman_value
        return {"pearson": pearson, "spearman": spearman, "pair_counts": pair_counts}
