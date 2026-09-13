"""多测点历史数据查询服务。"""

from datetime import datetime
from time import perf_counter

from sqlalchemy.orm import Session

from app.core.config.ConfigLoader import config
from app.core.data_processing import TimeSeriesProcessor
from app.core.middleware.LogRecorder import get_logger
from app.domain.data.repository.MeasurementRepository import MeasurementRepository
from app.domain.data.schema.HistorySchema import HistoryQuerySchema
from app.domain.data.service.DataQueryService import DataQueryService, data_query_service
from app.domain.data.service.TimeRangeService import TimeRangeService, time_range_service

logger = get_logger(__name__)


class HistoryService:
    """校验时间、查询并下采样历史测量数据。"""

    TIME_FORMAT = TimeRangeService.TIME_FORMAT
    MIN_RANGE = TimeRangeService.MIN_RANGE
    MAX_RANGE = TimeRangeService.MAX_RANGE

    def __init__(
        self,
        measurement_repository: MeasurementRepository | None = None,
        query_service: DataQueryService | None = None,
    ) -> None:
        # measurement_repository remains accepted for compatibility with existing
        # callers/tests; all reads still pass through the shared query service.
        self.query_service = query_service or (
            DataQueryService(measurement_repository)
            if measurement_repository is not None
            else data_query_service
        )

    @classmethod
    def _parse_time(cls, value, field, business_timezone):
        return time_range_service.parse(value, field, business_timezone)

    @classmethod
    def _format_time(cls, value, business_timezone):
        return time_range_service.format(value, business_timezone)

    def resolve_range(self, data, now: datetime | None = None) -> dict:
        """统一解析并校验历史查询使用的业务时间范围。"""
        return time_range_service.resolve(data, now)

    def query(self, data: HistoryQuerySchema, db: Session, now: datetime | None = None) -> dict:
        """
        查询历史测量数据，并按需执行 LTTB 下采样。
        :param data: 查询参数
        :param db: 数据库会话
        :param now: 可选的当前时间（用于测试）
        """
        started_at = perf_counter()
        resolved = self.resolve_range(data, now)
        business_timezone = resolved["business_timezone"]
        start_time = resolved["start_time"]
        requested_end_time = resolved["requested_end_time"]
        actual_end_time = resolved["actual_end_time"]
        start_utc = resolved["start_utc"]
        end_utc = resolved["end_utc"]
        was_clipped = resolved["was_clipped"]
        point_results: list[dict] = []
        total_raw_count = 0
        total_returned_count = 0

        # 7. 对每个测点 ID 查询历史数据，并按需执行 LTTB 下采样
        for point_id in data.point_ids:
            # 查询测点的历史数据流和原始数据点数量
            raw_count, point_stream = self.query_service.stream_full(
                point_id,
                start_utc,
                end_utc,
                db,
            )
            try:
                selected = TimeSeriesProcessor.lttb(
                    point_stream, raw_count, data.sample_count
                )
            finally:
                close = getattr(point_stream, "close", None)
                if close is not None:
                    close()

            # 将查询结果格式化为前端所需的时间字符串和数值列表
            times = [self._format_time(item[0], business_timezone) for item in selected]
            values = [item[1] for item in selected]
            normalized_values = TimeSeriesProcessor.normalize_min_max(values)
            returned_count = len(selected)
            if returned_count != len(times) or returned_count != len(values):
                raise RuntimeError("history response arrays are inconsistent")

            # 累积总原始数据点数量和总返回数据点数量
            total_raw_count += raw_count
            total_returned_count += returned_count
            point_results.append(
                {
                    "point_id": point_id,
                    "original_count": raw_count,
                    "returned_count": returned_count,
                    "downsampled": raw_count > data.sample_count,
                    "times": times,
                    "values": values,
                    "normalized_values": normalized_values,
                }
            )

        logger.info(
            "历史数据查询完成 point_count=%s raw_count=%s returned_count=%s clipped=%s duration_ms=%.2f",
            len(data.point_ids),
            total_raw_count,
            total_returned_count,
            was_clipped,
            (perf_counter() - started_at) * 1000,
        )
        return {
            "timezone": config.time.default_timezone,
            "start_time": self._format_time(start_time, business_timezone),
            "requested_end_time": self._format_time(requested_end_time, business_timezone),
            "actual_end_time": self._format_time(actual_end_time, business_timezone),
            "sample_count": data.sample_count,
            "points": point_results,
        }


history_service = HistoryService(query_service=data_query_service)
