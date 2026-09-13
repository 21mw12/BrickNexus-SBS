from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, JSON, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base


JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class Sandbox(Base):
    __tablename__ = "sandbox"

    sandbox_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    sandbox_name: Mapped[str] = mapped_column(String(30), nullable=False)
    config: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    state: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tick: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
