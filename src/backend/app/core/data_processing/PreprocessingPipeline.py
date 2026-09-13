import numpy as np

from app.common.validators import ValidationError
from .DataQualityAnalyzer import DataQualityAnalyzer
from .types import PreparedDataset, TimeSeriesDataset


class PreprocessingPipeline:
    @staticmethod
    def _fill_column(values: np.ndarray, strategy: str, max_gap: int) -> tuple[np.ndarray, int]:
        result = values.copy()
        filled = 0
        index = 0
        while index < len(result):
            if not np.isnan(result[index]):
                index += 1
                continue
            start = index
            while index < len(result) and np.isnan(result[index]):
                index += 1
            length = index - start
            if length > max_gap:
                continue
            if strategy == "forward_fill" and start > 0:
                result[start:index] = result[start - 1]
                filled += length
            elif strategy == "interpolate" and start > 0 and index < len(result):
                result[start:index] = np.linspace(result[start - 1], result[index], length + 2)[1:-1]
                filled += length
        return result, filled

    def run(self, dataset: TimeSeriesDataset, *, missing_strategy: str, max_gap: int, scaling: str) -> PreparedDataset:
        quality = DataQualityAnalyzer.analyze(dataset)
        matrix = np.array(dataset.values, dtype=float)
        if not matrix.size or quality.valid_count == 0:
            raise ValidationError("no data available for analysis")
        if missing_strategy == "reject" and np.isnan(matrix).any():
            raise ValidationError("dataset contains missing values")
        filled = 0
        if missing_strategy in {"interpolate", "forward_fill"}:
            for column in range(matrix.shape[1]):
                matrix[:, column], count = self._fill_column(matrix[:, column], missing_strategy, max_gap)
                filled += count
        valid_mask = ~np.isnan(matrix).any(axis=1)
        quality.interpolated_count = filled
        quality.dropped_count = int((~valid_mask).sum())
        model = matrix[valid_mask]
        if not len(model):
            raise ValidationError("no complete samples remain after preprocessing")
        center = scale = None
        if scaling == "standard":
            center, scale = np.mean(model, axis=0), np.std(model, axis=0)
        elif scaling == "robust":
            center = np.median(model, axis=0)
            scale = np.percentile(model, 75, axis=0) - np.percentile(model, 25, axis=0)
        if center is not None:
            scale = np.where(scale == 0, 1.0, scale)
            model = (model - center) / scale
        return PreparedDataset(
            point_ids=dataset.point_ids,
            timestamps=dataset.timestamps,
            raw_values=dataset.values,
            model_values=model,
            model_timestamps=[time for time, valid in zip(dataset.timestamps, valid_mask) if valid],
            interval_seconds=dataset.interval_seconds,
            quality=quality,
            center=center,
            scale=scale,
            scaling=scaling,
        )
