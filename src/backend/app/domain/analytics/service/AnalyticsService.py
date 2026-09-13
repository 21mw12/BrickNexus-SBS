"""Orchestrates on-demand analytics without persisting models or results."""

from datetime import timedelta
from time import perf_counter
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.core.algorithm import algorithm_registry
from app.core.config.ConfigLoader import config
from app.core.data_processing import DataQualityAnalyzer, PreprocessingPipeline, TimeSeriesDataset, TimeSeriesProcessor
from app.core.middleware.LogRecorder import get_logger
from app.domain.data.service.DataQueryService import DataQueryService, data_query_service
from app.domain.data.service.TimeRangeService import TimeRangeService, time_range_service

logger = get_logger(__name__)


class AnalyticsService:
    MAX_RAW_ROWS = 1_000_000

    def __init__(self, query_service: DataQueryService | None = None, range_service: TimeRangeService | None = None) -> None:
        self.query_service = query_service or data_query_service
        self.range_service = range_service or time_range_service
        self.pipeline = PreprocessingPipeline()

    def _load(self, data, resolved, db: Session) -> TimeSeriesDataset:
        interval = (resolved["end_utc"] - resolved["start_utc"]).total_seconds() / data.sample_count
        timestamps = [resolved["start_utc"] + timedelta(seconds=interval * index) for index in range(data.sample_count)]
        columns: list[list[float | None]] = []
        raw_counts: dict[str, int] = {}
        for point_id in data.point_ids:
            count, stream = self.query_service.stream_full(point_id, resolved["start_utc"], resolved["end_utc"], db)
            raw_counts[point_id] = count
            if sum(raw_counts.values()) > self.MAX_RAW_ROWS:
                close = getattr(stream, "close", None)
                if close:
                    close()
                raise ValidationError("analysis scans too many raw rows; shorten the range or reduce points")
            try:
                columns.append(TimeSeriesProcessor.dense_fixed_count(
                    stream, resolved["start_utc"], resolved["end_utc"], data.sample_count, data.preprocessing.aggregation
                ))
            finally:
                close = getattr(stream, "close", None)
                if close:
                    close()
        values = [list(row) for row in zip(*columns)]
        return TimeSeriesDataset(data.point_ids, timestamps, values, raw_counts, interval)

    @staticmethod
    def _warning(code: str, message: str, point_id: str | None = None) -> dict:
        return {"code": code, "level": "warning", "point_id": point_id, "message": message}

    def _prepare(self, dataset, preprocessing, scaling):
        return self.pipeline.run(dataset, missing_strategy=preprocessing.missing_strategy, max_gap=preprocessing.max_gap, scaling=scaling)

    @staticmethod
    def _effective_parameters(spec, supplied: dict) -> dict:
        defaults = {item["name"]: item.get("default") for item in spec.parameters}
        return {**defaults, **supplied}

    @staticmethod
    def _single_dataset(dataset: TimeSeriesDataset, column: int) -> TimeSeriesDataset:
        point_id = dataset.point_ids[column]
        return TimeSeriesDataset([point_id], dataset.timestamps, [[row[column]] for row in dataset.values], {point_id: dataset.raw_counts[point_id]}, dataset.interval_seconds)

    @staticmethod
    def _events(times, labels, scores, point_ids):
        events = []
        start = None
        indexes: list[int] = []
        for index, label in enumerate([*labels, False]):
            if label and start is None:
                start, indexes = index, [index]
            elif label:
                indexes.append(index)
            elif start is not None:
                events.append({"start_time": times[start], "end_time": times[indexes[-1]], "point_ids": point_ids, "sample_count": len(indexes), "max_score": max(scores[item] or 0 for item in indexes)})
                start, indexes = None, []
        return events

    @staticmethod
    def _expand_values(all_timestamps, model_timestamps, values, missing=None):
        """Map model-only output back onto the fixed bucket axis without inventing data."""
        by_time = {timestamp: value for timestamp, value in zip(model_timestamps, values)}
        return [by_time.get(timestamp, missing) for timestamp in all_timestamps]

    def _expand_anomaly_output(self, dataset, prepared, output, display_timezone):
        labels = self._expand_values(dataset.timestamps, prepared.model_timestamps, output["labels"], False)
        raw_scores = self._expand_values(dataset.timestamps, prepared.model_timestamps, output["raw_scores"])
        risk_scores = self._expand_values(dataset.timestamps, prepared.model_timestamps, output["risk_scores"])
        times = [self.range_service.format(item, display_timezone) for item in dataset.timestamps]
        return {
            **output,
            "times": times,
            "labels": labels,
            "raw_scores": raw_scores,
            "risk_scores": risk_scores,
        }

    def _anomaly(self, data, dataset, spec, warnings):
        mode = data.algorithm.mode
        if mode not in spec.modes:
            raise ValidationError(f"{spec.name} does not support {mode} mode")
        parameters = self._effective_parameters(spec, data.algorithm.parameters)
        results = []
        if mode == "joint":
            prepared = self._prepare(dataset, data.preprocessing, spec.scaling)
            if len(prepared.model_values) < spec.minimum_samples:
                raise ValidationError("not enough complete samples for anomaly detection")
            output = spec.factory().run(prepared.model_values, parameters)
            display_timezone = ZoneInfo(config.time.default_timezone)
            expanded = self._expand_anomaly_output(dataset, prepared, output, display_timezone)
            values_by_point = [[row[column] for row in dataset.values] for column in range(len(dataset.point_ids))]
            results.append({"point_ids": dataset.point_ids, "values_by_point": values_by_point, **expanded, "events": self._events(expanded["times"], expanded["labels"], expanded["risk_scores"], dataset.point_ids)})
            quality = prepared.quality
        else:
            quality = DataQualityAnalyzer.analyze(dataset)
            for column, point_id in enumerate(dataset.point_ids):
                prepared = self._prepare(self._single_dataset(dataset, column), data.preprocessing, spec.scaling)
                quality.interpolated_count += prepared.quality.interpolated_count
                quality.dropped_count += prepared.quality.dropped_count
                if len(prepared.model_values) < spec.minimum_samples:
                    warnings.append(self._warning("INSUFFICIENT_POINT_SAMPLES", "该测点有效样本不足，已跳过", point_id))
                    continue
                output = spec.factory().run(prepared.model_values[:, [0]], parameters)
                display_timezone = ZoneInfo(config.time.default_timezone)
                expanded = self._expand_anomaly_output(self._single_dataset(dataset, column), prepared, output, display_timezone)
                raw_values = [row[column] for row in dataset.values]
                results.append({"point_ids": [point_id], "values_by_point": [raw_values], **expanded, "events": self._events(expanded["times"], expanded["labels"], expanded["risk_scores"], [point_id])})
            if not results:
                raise ValidationError("all points failed anomaly detection")
        return {"series": results}, quality

    def _clustering(self, data, dataset, spec, warnings):
        if data.algorithm.mode not in spec.modes:
            raise ValidationError("K-Means requires joint mode")
        prepared = self._prepare(dataset, data.preprocessing, spec.scaling)
        usable = [index for index, point_id in enumerate(prepared.point_ids) if point_id not in prepared.quality.constant_point_ids]
        if len(usable) < 2:
            raise ValidationError("K-Means requires at least two non-constant points")
        if len(usable) != len(prepared.point_ids):
            warnings.append(self._warning("CONSTANT_POINTS_EXCLUDED", "恒定测点已从聚类特征中排除"))
        matrix = prepared.model_values[:, usable]
        output = spec.factory().run(matrix, self._effective_parameters(spec, data.algorithm.parameters))
        scaled_centers = np.asarray(output["centers"])
        feature_point_ids = [prepared.point_ids[index] for index in usable]
        output["feature_summaries"] = [
            {
                "cluster": cluster,
                "highlights": [
                    {
                        "point_id": feature_point_ids[index],
                        "direction": "high" if center[index] >= 0 else "low",
                        "strength": round(float(abs(center[index])), 4),
                    }
                    for index in np.argsort(np.abs(center))[::-1][: min(3, len(center))]
                ],
            }
            for cluster, center in enumerate(scaled_centers)
        ]
        centers = scaled_centers.copy()
        if prepared.center is not None and prepared.scale is not None:
            centers = centers * prepared.scale[usable] + prepared.center[usable]
        output["centers"] = centers.tolist()
        output["point_ids"] = feature_point_ids
        display_timezone = ZoneInfo(config.time.default_timezone)
        output["times"] = [self.range_service.format(item, display_timezone) for item in prepared.model_timestamps]
        output["cluster_sizes"] = [int(np.sum(np.asarray(output["labels"]) == index)) for index in range(output["cluster_count"])]
        output["summaries"] = [f"状态 {index + 1}：包含 {count} 个时间窗口" for index, count in enumerate(output["cluster_sizes"])]
        if output["silhouette_score"] < 0.25:
            warnings.append(self._warning("LOW_SILHOUETTE_SCORE", "聚类区分度较低，请谨慎解释结果"))
        return output, prepared.quality

    def _forecasting(self, data, dataset, spec, warnings):
        if data.algorithm.mode not in spec.modes:
            raise ValidationError(f"{spec.name} requires per_point mode")
        parameters = self._effective_parameters(spec, data.algorithm.parameters)
        horizon = int(parameters.pop("horizon", 20))
        ratio = float(parameters.pop("backtest_ratio", 0.2))
        interval_level = float(parameters.pop("prediction_interval", 0.95))
        if not 1 <= horizon <= 500 or not 0.1 <= ratio <= 0.4 or not 0.8 <= interval_level <= 0.99:
            raise ValidationError("invalid forecasting common parameters")
        parameters.update(backtest_ratio=ratio, prediction_interval=interval_level)
        results = []
        failures: list[str] = []
        quality = DataQualityAnalyzer.analyze(dataset)
        for column, point_id in enumerate(dataset.point_ids):
            try:
                prepared = self._prepare(self._single_dataset(dataset, column), data.preprocessing, "none")
                quality.interpolated_count += prepared.quality.interpolated_count
                quality.dropped_count += prepared.quality.dropped_count
                if len(prepared.model_values) < spec.minimum_samples:
                    raise ValidationError("not enough valid samples")
                series = prepared.model_values[:, 0]
                output = spec.factory().run(series, horizon, parameters)
                backtest_count = len(output["backtest_values"])
                future_times = [dataset.timestamps[-1] + timedelta(seconds=prepared.interval_seconds * (index + 1)) for index in range(horizon)]
                results.append({
                    "point_id": point_id,
                    "status": "success",
                    "history_times": [self.range_service.format(item, ZoneInfo(config.time.default_timezone)) for item in dataset.timestamps],
                    "history_values": [row[column] for row in dataset.values],
                    "backtest_times": [self.range_service.format(item, ZoneInfo(config.time.default_timezone)) for item in prepared.model_timestamps[-backtest_count:]],
                    "forecast_times": [self.range_service.format(item, ZoneInfo(config.time.default_timezone)) for item in future_times],
                    **output,
                })
            except Exception as exc:
                message = str(exc) or exc.__class__.__name__
                failures.append(f"{point_id}: {message}")
                warnings.append(self._warning("POINT_FORECAST_FAILED", message, point_id))
                results.append({"point_id": point_id, "status": "failed", "message": message})
        if not any(item["status"] == "success" for item in results):
            details = "；".join(failures[:3])
            raise ValidationError(f"所有测点预测均失败：{details}" if details else "所有测点预测均失败")
        return {"points": results, "horizon": horizon}, quality

    def run(self, data, db: Session, now=None) -> dict:
        started = perf_counter()
        spec = algorithm_registry.resolve(data.analysis_type, data.algorithm.name)
        if data.algorithm.mode not in spec.modes:
            raise ValidationError(f"{spec.name} does not support {data.algorithm.mode} mode")
        resolved = self.range_service.resolve(data, now)
        dataset = self._load(data, resolved, db)
        warnings: list[dict] = []
        if data.analysis_type == "anomaly":
            result, quality = self._anomaly(data, dataset, spec, warnings)
        elif data.analysis_type == "clustering":
            result, quality = self._clustering(data, dataset, spec, warnings)
        else:
            result, quality = self._forecasting(data, dataset, spec, warnings)
        if quality and quality.missing_ratio > 0.3:
            warnings.append(self._warning("HIGH_MISSING_RATIO", "缺失数据比例超过30%，结果可能不稳定"))
        timezone = resolved["business_timezone"]
        elapsed = (perf_counter() - started) * 1000
        logger.info("智能分析完成 type=%s algorithm=%s raw_count=%s duration_ms=%.2f", data.analysis_type, spec.name, sum(dataset.raw_counts.values()), elapsed)
        return {
            "analysis_type": data.analysis_type,
            "algorithm": spec.name,
            "mode": data.algorithm.mode,
            "parameters": self._effective_parameters(spec, data.algorithm.parameters),
            "timezone": config.time.default_timezone,
            "range": {
                "start_time": self.range_service.format(resolved["start_time"], timezone),
                "requested_end_time": self.range_service.format(resolved["requested_end_time"], timezone),
                "actual_end_time": self.range_service.format(resolved["actual_end_time"], timezone),
                "was_clipped": resolved["was_clipped"],
            },
            "sampling": {"requested_sample_count": data.sample_count, "actual_sample_count": data.sample_count, "interval_seconds": dataset.interval_seconds, "aggregation": data.preprocessing.aggregation},
            "preprocessing": {**data.preprocessing.model_dump(), "scaling": spec.scaling},
            "quality": quality.to_dict() if quality else {},
            "warnings": warnings,
            "result": result,
        }


analytics_service = AnalyticsService()
