"""历史时间矩阵及相关性分析服务。"""

from __future__ import annotations

from datetime import timedelta
from time import perf_counter

from sqlalchemy.orm import Session

from app.core.algorithm import CorrelationAnalyzer
from app.core.data_processing import TimeSeriesProcessor
from app.core.config.ConfigLoader import config
from app.core.middleware.LogRecorder import get_logger
from app.domain.data.repository.MeasurementRepository import MeasurementRepository
from app.domain.data.schema.HistorySchema import HistoryHeatmapQuerySchema
from app.domain.data.service.DataQueryService import DataQueryService, data_query_service
from app.domain.data.service.HistoryService import HistoryService, history_service

logger = get_logger(__name__)


class HistoryHeatmapService:
    def __init__(
        self,
        measurement_repository: MeasurementRepository | None = None,
        range_service: HistoryService | None = None,
        query_service: DataQueryService | None = None,
    ) -> None:
        self.query_service = query_service or (
            DataQueryService(measurement_repository)
            if measurement_repository is not None
            else data_query_service
        )
        self.range_service = range_service or history_service

    def query(self, data: HistoryHeatmapQuerySchema, db: Session, now=None) -> dict:
        started_at = perf_counter()
        resolved = self.range_service.resolve_range(data, now)
        start_utc = resolved["start_utc"]
        end_utc = resolved["end_utc"]
        business_timezone = resolved["business_timezone"]
        interval_seconds = (end_utc - start_utc).total_seconds() / data.sample_count
        bucket_times = [
            self.range_service._format_time(
                start_utc + timedelta(seconds=interval_seconds * index),
                business_timezone,
            )
            for index in range(data.sample_count)
        ]

        point_results: list[dict] = []
        raw_matrix: list[list[float | None]] = []
        total_raw_count = 0
        for point_id in data.point_ids:
            raw_count, point_stream = self.query_service.stream_full(
                point_id, start_utc, end_utc, db
            )
            try:
                values = TimeSeriesProcessor.dense_fixed_count(
                    point_stream, start_utc, end_utc, data.sample_count
                )
            finally:
                close = getattr(point_stream, "close", None)
                if close is not None:
                    close()
            raw_matrix.append(values)
            total_raw_count += raw_count
            point_results.append(
                {
                    "point_id": point_id,
                    "original_count": raw_count,
                    "non_null_count": sum(value is not None for value in values),
                }
            )

        # 固定时间轴必须保留全局空桶。折线图据此断线，热力图则用灰色格子
        # 表示缺失；删除这些桶会让相隔很久的真实数据在视觉上错误地相连。
        times = bucket_times
        for point_result, values in zip(point_results, raw_matrix):
            point_result["values"] = values
            point_result["normalized_values"] = (
                TimeSeriesProcessor.normalize_min_max(values)
            )

        logger.info(
            "历史热力图查询完成 point_count=%s raw_count=%s bucket_count=%s duration_ms=%.2f",
            len(data.point_ids),
            total_raw_count,
            data.sample_count,
            (perf_counter() - started_at) * 1000,
        )
        return {
            "timezone": config.time.default_timezone,
            "start_time": self.range_service._format_time(
                resolved["start_time"], business_timezone
            ),
            "requested_end_time": self.range_service._format_time(
                resolved["requested_end_time"], business_timezone
            ),
            "actual_end_time": self.range_service._format_time(
                resolved["actual_end_time"], business_timezone
            ),
            "sample_count": data.sample_count,
            "requested_sample_count": data.sample_count,
            "interval_seconds": interval_seconds,
            "times": times,
            "value_range": TimeSeriesProcessor.value_range(raw_matrix),
            "points": point_results,
            "correlations": CorrelationAnalyzer.calculate(raw_matrix),
        }


history_heatmap_service = HistoryHeatmapService(query_service=data_query_service)
