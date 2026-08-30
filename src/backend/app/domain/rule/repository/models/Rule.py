from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base


class Rule(Base):
    __tablename__ = "rule"
    __table_args__ = (Index("ix_rule_status", "status"),)

    rule_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_file_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="paused")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
