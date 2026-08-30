from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.DB.SQLConnection import Base


class ModelPoint(Base):
    __tablename__ = "model_point"

    ATTRIBUTES = [
        {"field": "model_id", "label": "型号ID"},
        {"field": "point_id", "label": "测点ID"},
    ]

    model_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("model.model_id", ondelete="CASCADE"),
        primary_key=True,
        comment="型号ID",
    )
    point_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("point.point_id", ondelete="RESTRICT"),
        primary_key=True,
        comment="测点ID",
    )

    point = relationship("Point", lazy="joined")

    @property
    def point_name(self) -> str:
        return self.point.point_name

    @property
    def point_unit(self) -> str:
        return self.point.point_unit

    @property
    def point_description(self) -> str | None:
        return self.point.point_description

    def print_info(self):
        """ 打印基本信息 """
        print("=" * 60)
        print(f"model_id:           {self.model_id}")
        print(f"point_id:           {self.point_id}")
        print(f"point_name:         {self.point_name}")
        print(f"point_unit:         {self.point_unit}")
        print(f"point_description:  {self.point_description}")
        print("=" * 60)
