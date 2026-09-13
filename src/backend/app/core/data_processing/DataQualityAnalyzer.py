import numpy as np

from .types import DataQualityReport, TimeSeriesDataset


class DataQualityAnalyzer:
    @staticmethod
    def analyze(dataset: TimeSeriesDataset) -> DataQualityReport:
        matrix = np.array(dataset.values, dtype=float)
        missing = int(np.isnan(matrix).sum()) if matrix.size else 0
        total = int(matrix.size)
        constants: list[str] = []
        low_variance: list[str] = []
        for index, point_id in enumerate(dataset.point_ids):
            values = matrix[:, index]
            values = values[~np.isnan(values)]
            if values.size and np.ptp(values) == 0:
                constants.append(point_id)
            elif values.size and float(np.var(values)) < 1e-12:
                low_variance.append(point_id)
        longest = 0
        if matrix.size:
            for column in range(matrix.shape[1]):
                run = 0
                for missing_value in np.isnan(matrix[:, column]):
                    run = run + 1 if missing_value else 0
                    longest = max(longest, run)
        return DataQualityReport(
            raw_count=sum(dataset.raw_counts.values()),
            bucket_count=len(dataset.timestamps),
            valid_count=int(np.sum(~np.all(np.isnan(matrix), axis=1))) if matrix.size else 0,
            missing_count=missing,
            missing_ratio=missing / total if total else 1.0,
            constant_point_ids=constants,
            low_variance_point_ids=low_variance,
            max_consecutive_gap=longest,
        )
