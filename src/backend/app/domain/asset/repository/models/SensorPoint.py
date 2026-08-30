from sqlalchemy import ForeignKeyConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.DB.SQLConnection import Base


class SensorPoint(Base):
    __tablename__ = "sensor_point"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_model_id", "source_point_id"],
            ["model_point.model_id", "model_point.point_id"],
            name="fk_sensor_point_source_model_point",
            ondelete="RESTRICT",
        ),
        Index("ix_sensor_point_source_point_id", "source_point_id"),
        Index(
            "ix_sensor_point_source_model_point",
            "source_model_id",
            "source_point_id",
        ),
    )

    ATTRIBUTES = [
        {"field": "point_id", "label": "测点ID"},
        {"field": "sensor_id", "label": "传感器ID"},
        {"field": "source_model_id", "label": "来源型号ID"},
        {"field": "source_point_id", "label": "来源测点ID"},
        {"field": "point_name", "label": "测点名称"},
        {"field": "point_unit", "label": "测点单位"},
        {"field": "json_path", "label": "JSON路径"},
    ]

    point_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="测点ID")
    sensor_id: Mapped[str] = mapped_column(String(100), nullable=False, comment="传感器资产ID")
    source_model_id: Mapped[str] = mapped_column(String(100), nullable=False, comment="来源型号ID")
    source_point_id: Mapped[str] = mapped_column(String(100), nullable=False, comment="来源测点ID")
    point_name: Mapped[str] = mapped_column(String(20), nullable=False, comment="测点名称快照")
    point_unit: Mapped[str] = mapped_column(String(10), nullable=False, comment="测点单位快照")
    json_path: Mapped[str] = mapped_column(String(200), nullable=True, comment="JSON数据提取路径")

    source_model_point = relationship("ModelPoint", lazy="joined")

    @property
    def point_description(self) -> str | None:
        return self.source_model_point.point.point_description

    def print_info(self):
        """ 打印基本信息 """
        print("=" * 60)
        print(f"point_id:           {self.point_id}")
        print(f"sensor_id:          {self.sensor_id}")
        print(f"source_model_id:    {self.source_model_id}")
        print(f"source_point_id:    {self.source_point_id}")
        print(f"point_name:         {self.point_name}")
        print(f"point_unit:         {self.point_unit}")
        print(f"json_path:          {self.json_path}")
        print("=" * 60)
