"""终端或传感器控制配置数据库模型。"""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base


# Protocol constraints distinguish SQL NULL from the JSON literal ``null``.
# Persist Python None as SQL NULL so MQTT rows satisfy the HTTP-field checks.
JSON_TYPE = JSONB(none_as_null=True).with_variant(JSON(none_as_null=True), "sqlite")


class Control(Base):
    __tablename__ = "control"
    __table_args__ = (
        CheckConstraint("type IN ('mqtt', 'http')", name="ck_control_type"),
        CheckConstraint("asset_type IN ('terminal', 'sensor')", name="ck_control_asset_type"),
        CheckConstraint(
            "(type = 'mqtt' AND mqtt_topic IS NOT NULL AND mqtt_payload IS NOT NULL "
            "AND http_method IS NULL AND http_path IS NULL "
            "AND http_header IS NULL AND http_params IS NULL AND http_body IS NULL) OR "
            "(type = 'http' AND mqtt_topic IS NULL AND mqtt_retained IS NULL "
            "AND mqtt_payload IS NULL AND http_method IN ('GET', 'POST') "
            "AND http_path IS NOT NULL)",
            name="ck_control_protocol_fields",
        ),
        UniqueConstraint("name", name="uq_control_name"),
        Index("ix_control_type_status", "type", "status"),
        Index("ix_control_channel_id", "channel_id"),
        Index("ix_control_asset_type_asset_id", "asset_type", "asset_id"),
    )

    control_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(100), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(10), nullable=False)
    asset_id: Mapped[str] = mapped_column(
        String(100), ForeignKey(
            "assets.asset_id", name="fk_control_asset_id_assets", ondelete="CASCADE"
        ), nullable=False
    )
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    mqtt_topic: Mapped[str | None] = mapped_column(String(30), nullable=True)
    mqtt_retained: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    mqtt_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    http_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    http_path: Mapped[str | None] = mapped_column(String(100), nullable=True)
    http_header: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    http_params: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    http_body: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
