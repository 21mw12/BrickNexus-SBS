from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.core.config.ConfigLoader import config
from app.core.utils.UUIDGenerator import uuid_generator
from app.domain.log.repository.models import Log
from app.domain.log.schema import LogQuery
from app.domain.user.repository.models import User
from app.domain.common.PermissionChecker import get_user_id_from_token


class LogService:
    TYPE_OPTIONS = (
        {"value": "rule_action", "label": "规则动作日志"},
        {"value": "rule_operation", "label": "规则操作日志"},
    )
    LEVEL_OPTIONS = (
        {"value": "DEBUG", "label": "调试"},
        {"value": "INFO", "label": "信息"},
        {"value": "WARNING", "label": "警告"},
        {"value": "ERROR", "label": "错误"},
        {"value": "CRITICAL", "label": "严重"},
    )
    LEVELS = {item["value"] for item in LEVEL_OPTIONS}
    TYPES = {item["value"] for item in TYPE_OPTIONS}

    @staticmethod
    def _day_bounds(value: date) -> tuple[datetime, datetime]:
        business_timezone = ZoneInfo(config.time.default_timezone)
        start = datetime.combine(value, time.min, tzinfo=business_timezone)
        return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)

    @staticmethod
    def create(db: Session, *, type: str, level: str, operator: str, content: str, time: datetime | None = None) -> Log:
        if type not in LogService.TYPES:
            raise ValidationError("invalid log type")
        if level not in LogService.LEVELS:
            raise ValidationError("invalid log level")
        if not operator or len(operator) > 30:
            raise ValidationError("invalid log operator")
        if not content:
            raise ValidationError("log content is required")
        item = Log(
            id=uuid_generator.random(), type=type, level=level,
            operator=operator, content=content, time=time or datetime.now(timezone.utc),
        )
        db.add(item)
        db.flush()
        return item

    @staticmethod
    def operator_from_token(authorization: str, db: Session) -> str:
        user_id = get_user_id_from_token(authorization)
        user = db.get(User, user_id)
        if user is None:
            raise ValidationError("user not found")
        return user.nickname

    @staticmethod
    def list_logs(db: Session, page: int, limit: int, filters: LogQuery | None = None) -> dict:
        conditions = []
        if filters:
            if filters.type:
                conditions.append(Log.type == filters.type)
            if filters.level:
                conditions.append(Log.level == filters.level)
            if filters.operator:
                conditions.append(Log.operator == filters.operator)
            if filters.time:
                start, end = LogService._day_bounds(filters.time)
                conditions.extend((Log.time >= start, Log.time < end))
        stmt = select(Log).where(*conditions).order_by(Log.time.desc(), Log.id.desc())
        total = db.scalar(select(func.count()).select_from(Log).where(*conditions)) or 0
        items = db.scalars(stmt.offset((page - 1) * limit).limit(limit)).all()
        return {"total": total, "items": [LogService.to_dict(item) for item in items]}

    @staticmethod
    def get_options() -> dict:
        return {
            "types": [dict(item) for item in LogService.TYPE_OPTIONS],
            "levels": [dict(item) for item in LogService.LEVEL_OPTIONS],
        }

    @staticmethod
    def to_dict(item: Log) -> dict:
        return {"id": item.id, "type": item.type, "level": item.level,
                "operator": item.operator, "content": item.content, "time": item.time}
