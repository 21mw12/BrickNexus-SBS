"""多测点历史数据查询服务。"""

import re
from datetime import datetime, timedelta, timezone
from time import perf_counter
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.core.config.ConfigLoader import config
from app.core.middleware.LogRecorder import get_logger
from app.domain.data.repository.MeasurementRepository import MeasurementRepository
from app.domain.data.schema.HistorySchema import HistoryQuerySchema
from app.domain.data.service.LttbDownsampler import lttb_downsample

logger = get_logger(__name__)


class HistoryService:
    """校验时间、查询并下采样历史测量数据。"""

    TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    TIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
    MIN_RANGE = timedelta(minutes=15)
    MAX_RANGE = timedelta(days=31)

    def __init__(
        self,
        measurement_repository: MeasurementRepository | None = None,
    ) -> None:
        self.measurement_repository = measurement_repository or MeasurementRepository()

    @classmethod
    def _parse_time(cls, value: str, field: str, business_timezone: ZoneInfo) -> datetime:
        if not isinstance(value, str) or cls.TIME_PATTERN.fullmatch(value) is None:
            raise ValidationError(f"{field} must use yyyy-MM-dd HH:mm:ss")
        try:
            parsed = datetime.strptime(value, cls.TIME_FORMAT)
        except ValueError as exc:
            raise ValidationError(f"{field} is invalid") from exc
        return parsed.replace(tzinfo=business_timezone)

    @classmethod
    def _format_time(cls, value: datetime, business_timezone: ZoneInfo) -> str:
        if value.tzinfo is None:
            # measurement 在 PostgreSQL 中是 timestamptz；SQLite 测试往返时会丢失 tzinfo。
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(business_timezone).strftime(cls.TIME_FORMAT)

    def query(self, data: HistoryQuerySchema, db: Session, now: datetime | None = None) -> dict:
        """
        查询历史测量数据，并按需执行 LTTB 下采样。
        :param data: 查询参数
        :param db: 数据库会话
        :param now: 可选的当前时间（用于测试）
        """
        # 1. 校验时间范围、对齐 15 分钟边界、裁剪未来时间
        started_at = perf_counter()
        business_timezone = ZoneInfo(config.time.default_timezone)
        current_time = now or datetime.now(business_timezone)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=business_timezone)
        else:
            current_time = current_time.astimezone(business_timezone)

        # 2. 解析时间字符串为 datetime 对象，并设置时区
        start_time = self._parse_time(data.start_time, "start_time", business_timezone)
        requested_end_time = self._parse_time(data.end_time, "end_time", business_timezone)

        # 3. 校验时间对齐和范围
        if start_time.minute not in (0, 15, 30, 45) or start_time.second != 0:
            raise ValidationError("start_time must align to a 15-minute boundary")
        if start_time >= current_time:
            raise ValidationError("start_time must be earlier than current time")

        # 4. 校验时间范围是否在允许的最小和最大范围内
        requested_range = requested_end_time - start_time
        if requested_range < self.MIN_RANGE:
            raise ValidationError("time range must be at least 15 minutes")
        if requested_range > self.MAX_RANGE:
            raise ValidationError("time range must not exceed 31 days")

        # 5. 裁剪未来时间，确保实际结束时间不超过当前时间
        was_clipped = requested_end_time > current_time
        actual_end_time = current_time if was_clipped else requested_end_time

        # 6. 将时间转换为 UTC，以便与数据库中的测量数据进行比较
        start_utc = start_time.astimezone(timezone.utc)
        end_utc = actual_end_time.astimezone(timezone.utc)
        point_results: list[dict] = []
        total_raw_count = 0
        total_returned_count = 0

        # 7. 对每个测点 ID 查询历史数据，并按需执行 LTTB 下采样
        for point_id in data.point_ids:
            # 查询测点的历史数据流和原始数据点数量
            raw_count, point_stream = self.measurement_repository.stream_history(
                point_id,
                start_utc,
                end_utc,
                db,
            )
            try:
                selected = lttb_downsample(point_stream, raw_count, data.sample_count)
            finally:
                close = getattr(point_stream, "close", None)
                if close is not None:
                    close()

            # 将查询结果格式化为前端所需的时间字符串和数值列表
            times = [self._format_time(item[0], business_timezone) for item in selected]
            values = [item[1] for item in selected]
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


history_service = HistoryService()
