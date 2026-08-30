from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Float, Index

from app.infra.DB.SQLConnection import Base


class Measurement(Base):
    __tablename__ = "measurement"

    __table_args__ = (Index("ix_measurement_time", "time"),)

    point_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="传感器测点ID")
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, comment="测量时间")
    value: Mapped[float] = mapped_column(Float, nullable=False, comment="测量值")

    def print_info(self):
        """ 打印基本信息 """
        print("=" * 60)
        print(f"point_id:           {self.point_id}")
        print(f"value:              {self.value}")
        print(f"time:               {self.time}")
        print("=" * 60)
