"""HTTP 通道数据库模型。"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, JSON, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base


JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")


class ChannelHttp(Base):
    __tablename__ = "channel_http"
    __table_args__ = (
        CheckConstraint("default_timeout > 0", name="ck_channel_http_timeout"),
        Index("ix_channel_http_base_url", "base_url"),
    )

    channel_http_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    base_url: Mapped[str] = mapped_column(String(200), nullable=False)
    default_headers: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    default_timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
