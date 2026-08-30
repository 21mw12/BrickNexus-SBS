from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from app.infra.DB.SQLConnection import Base


class AssetRoom(Base):
    __tablename__ = "assets_room"

    ATTRIBUTES = [
        {"field": "number", "label": "房间编号"},
        {"field": "room_purpose", "label": "房间用途"},
        {"field": "max_current", "label": "最大电流"},
        {"field": "manager_name", "label": "管理员姓名"},
    ]

    asset_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="资产ID")    
    number: Mapped[str] = mapped_column(String(20), nullable=True, comment="房间编号")
    room_purpose: Mapped[str] = mapped_column(String(100), nullable=True, comment="房间用途")
    max_current: Mapped[str] = mapped_column(String(20), nullable=True, comment="最大电流")
    manager_name: Mapped[str] = mapped_column(String(50), nullable=True, comment="管理员姓名")

    def print_info(self):
        """ 打印基本信息 """
        print("=" * 60)
        print(f"asset_id:           {self.asset_id}")
        print(f"number:             {self.number}")
        print(f"room_purpose:       {self.room_purpose}")
        print(f"max_current:        {self.max_current}")
        print(f"manager_name:       {self.manager_name}")
        print("=" * 60)

