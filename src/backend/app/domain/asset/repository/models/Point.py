from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base


class Point(Base):
    """可被多个传感器型号复用的全局测点定义。"""

    __tablename__ = "point"
    __table_args__ = (
        UniqueConstraint("point_name", "point_unit", name="uq_point_name_unit"),
    )

    ATTRIBUTES = [
        {"field": "point_id", "label": "测点ID"},
        {"field": "point_name", "label": "测点名称"},
        {"field": "point_unit", "label": "测点单位"},
        {"field": "point_description", "label": "测点描述"},
    ]

    point_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="测点ID")
    point_name: Mapped[str] = mapped_column(String(20), nullable=False, comment="测点名称")
    point_unit: Mapped[str] = mapped_column(String(10), nullable=False, comment="测点单位")
    point_description: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="测点含义说明"
    )
