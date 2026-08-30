"""楼层平面图领域的数据库模型。"""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base


class FloorPlan(Base):
    """一条记录对应一个楼层的一张平面图。"""

    __tablename__ = "floor_plan"
    __table_args__ = (
        CheckConstraint("image_width > 0", name="ck_floor_plan_image_width_positive"),
        CheckConstraint("image_height > 0", name="ck_floor_plan_image_height_positive"),
    )

    # floor_id 使用共享主键，同时保证平面图一定属于一个真实楼层。
    floor_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("assets_floor.asset_id", ondelete="CASCADE"),
        primary_key=True,
        comment="楼层ID",
    )
    image_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="图片名称")
    image_width: Mapped[int] = mapped_column(Integer, nullable=False, comment="原图宽度")
    image_height: Mapped[int] = mapped_column(Integer, nullable=False, comment="原图高度")
    image_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="图片MIME类型")
