from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, JSON, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base


JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class LLMConfig(Base):
    __tablename__ = "config_llm"
    __table_args__ = (
        CheckConstraint(
            "service_type IN ('vllm', 'ollama', 'deepseek')",
            name="ck_config_llm_service_type",
        ),
        Index("ix_config_llm_created_at", "created_at"),
        Index(
            "uq_config_llm_single_active",
            "is_use",
            unique=True,
            postgresql_where=text("is_use = true"),
            sqlite_where=text("is_use = 1"),
        ),
    )

    llm_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    service_name: Mapped[str] = mapped_column(String(50), nullable=False)
    service_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    is_use: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

