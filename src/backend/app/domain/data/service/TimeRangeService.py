"""Shared business-time range parsing for historical point data."""

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.common.validators import ValidationError
from app.core.config.ConfigLoader import config


class TimeRangeService:
    TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    TIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
    MIN_RANGE = timedelta(minutes=15)
    MAX_RANGE = timedelta(days=31)

    @classmethod
    def parse(cls, value: str, field: str, business_timezone: ZoneInfo) -> datetime:
        if not isinstance(value, str) or cls.TIME_PATTERN.fullmatch(value) is None:
            raise ValidationError(f"{field} must use yyyy-MM-dd HH:mm:ss")
        try:
            parsed = datetime.strptime(value, cls.TIME_FORMAT)
        except ValueError as exc:
            raise ValidationError(f"{field} is invalid") from exc
        return parsed.replace(tzinfo=business_timezone)

    @classmethod
    def format(cls, value: datetime, business_timezone: ZoneInfo) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(business_timezone).strftime(cls.TIME_FORMAT)

    def resolve(self, data, now: datetime | None = None, *, require_start_alignment: bool = True, require_min_range: bool = True) -> dict:
        business_timezone = ZoneInfo(config.time.default_timezone)
        current = now or datetime.now(business_timezone)
        current = current.replace(tzinfo=business_timezone) if current.tzinfo is None else current.astimezone(business_timezone)
        start = self.parse(data.start_time, "start_time", business_timezone)
        requested_end = self.parse(data.end_time, "end_time", business_timezone)
        if require_start_alignment and (start.minute not in (0, 15, 30, 45) or start.second != 0 or start.microsecond != 0):
            raise ValidationError("start_time must align to a 15-minute boundary")
        if start >= current:
            raise ValidationError("start_time must be earlier than current time")
        requested_range = requested_end - start
        if requested_range <= timedelta(0):
            raise ValidationError("end_time must be later than start_time")
        if require_min_range and requested_range < self.MIN_RANGE:
            raise ValidationError("time range must be at least 15 minutes")
        if requested_range > self.MAX_RANGE:
            raise ValidationError("time range must not exceed 31 days")
        actual_end = min(requested_end, current)
        return {
            "business_timezone": business_timezone,
            "start_time": start,
            "requested_end_time": requested_end,
            "actual_end_time": actual_end,
            "start_utc": start.astimezone(timezone.utc),
            "end_utc": actual_end.astimezone(timezone.utc),
            "was_clipped": requested_end > current,
        }


time_range_service = TimeRangeService()
