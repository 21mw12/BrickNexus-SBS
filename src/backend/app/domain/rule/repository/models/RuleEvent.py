from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class RuleEvent(Base):
    __tablename__ = "rule_event"
    __table_args__ = (
        Index("ix_rule_event_rule_time", "rule_id", "event_time"),
        Index("ix_rule_event_type", "event_type"),
    )

    event_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    rule_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("rule.rule_id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
