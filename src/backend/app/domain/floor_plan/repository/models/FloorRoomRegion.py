"""楼层平面图领域中的房间矩形标记模型。"""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base


class FloorRoomRegion(Base):
    """一个房间最多拥有一个矩形标记。"""

    __tablename__ = "floor_room_region"
    __table_args__ = (
        CheckConstraint("x >= 0", name="ck_floor_room_region_x_non_negative"),
        CheckConstraint("y >= 0", name="ck_floor_room_region_y_non_negative"),
        CheckConstraint("width > 0", name="ck_floor_room_region_width_positive"),
        CheckConstraint("height > 0", name="ck_floor_room_region_height_positive"),
    )

    # room_id 使用共享主键，同时保证标记一定属于一个真实房间。
    room_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("assets_room.asset_id", ondelete="CASCADE"),
        primary_key=True,
        comment="房间ID",
    )
    x: Mapped[int] = mapped_column(Integer, nullable=False, comment="左上角X像素坐标")
    y: Mapped[int] = mapped_column(Integer, nullable=False, comment="左上角Y像素坐标")
    width: Mapped[int] = mapped_column(Integer, nullable=False, comment="矩形宽度")
    height: Mapped[int] = mapped_column(Integer, nullable=False, comment="矩形高度")
