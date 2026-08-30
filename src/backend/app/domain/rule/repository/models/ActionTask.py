from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class ActionTask(Base):
    __tablename__ = "action_task"
    __table_args__ = (
        Index("ix_action_task_status_created", "status", "created_at"),
        Index("ix_action_task_rule_action", "rule_id", "action_id"),
    )

    task_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    rule_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("rule.rule_id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("rule_event.event_id", ondelete="CASCADE"), nullable=False
    )
    action_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)
    action_params: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    is_executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
