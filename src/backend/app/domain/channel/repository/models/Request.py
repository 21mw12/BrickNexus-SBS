"""采集请求数据库模型。"""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base


# Protocol constraints distinguish SQL NULL from the JSON literal ``null``.
# Persist Python None as SQL NULL so MQTT rows satisfy the HTTP-field checks.
JSON_TYPE = JSONB(none_as_null=True).with_variant(JSON(none_as_null=True), "sqlite")


class Request(Base):
    __tablename__ = "request"
    __table_args__ = (
        CheckConstraint("type IN ('mqtt', 'http')", name="ck_request_type"),
        CheckConstraint("interval_seconds > 0", name="ck_request_interval_positive"),
        CheckConstraint(
            "(type = 'mqtt' AND mqtt_topic IS NOT NULL "
            "AND http_method IS NULL AND http_path IS NULL "
            "AND http_header IS NULL AND http_params IS NULL AND http_body IS NULL) OR "
            "(type = 'http' AND mqtt_topic IS NULL "
            "AND http_method IN ('GET', 'POST') AND http_path IS NOT NULL)",
            name="ck_request_protocol_fields",
        ),
        UniqueConstraint("name", name="uq_request_name"),
        Index("ix_request_type_status", "type", "status"),
        Index("ix_request_channel_id", "channel_id"),
    )

    request_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(100), nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    time_json_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    time_format: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    mqtt_topic: Mapped[str | None] = mapped_column(String(30), nullable=True)
    http_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    http_path: Mapped[str | None] = mapped_column(String(100), nullable=True)
    http_header: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    http_params: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    http_body: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)

    @property
    def request_type(self) -> str:
        """兼容采集事件和 Loader 使用的既有属性名。"""
        return self.type

    @property
    def is_active(self) -> bool:
        return self.status

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.status = value

    @property
    def time_parse(self) -> str | None:
        return self.time_format
