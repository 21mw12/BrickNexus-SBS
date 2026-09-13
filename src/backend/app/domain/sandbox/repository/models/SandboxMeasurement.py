from sqlalchemy import BigInteger, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base


class SandboxMeasurement(Base):
    __tablename__ = "sandbox_measurement"
    __table_args__ = (
        Index("ix_sandbox_measurement_sandbox_tick", "sandbox_id", "tick"),
    )

    sandbox_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("sandbox.sandbox_id", ondelete="CASCADE"),
        primary_key=True,
    )
    point_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tick: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
