from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base


class Log(Base):
    __tablename__ = "log"
    __table_args__ = (
        Index("ix_log_type", "type"),
        Index("ix_log_level", "level"),
        Index("ix_log_operator", "operator"),
        Index("ix_log_time", "time"),
    )

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    operator: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
