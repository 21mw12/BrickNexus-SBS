from sqlalchemy import BigInteger, ForeignKey, Index, JSON, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base


JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class SandboxEvent(Base):
    __tablename__ = "sandbox_event"
    __table_args__ = (
        Index("ix_sandbox_event_sandbox_tick", "sandbox_id", "tick"),
    )

    event_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    sandbox_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("sandbox.sandbox_id", ondelete="CASCADE"),
        nullable=False,
    )
    tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
