from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, Integer

from app.infra.DB.SQLConnection import Base


class Asset(Base):
    __tablename__ = "assets"

    asset_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="资产ID")
    asset_id_parent: Mapped[str] = mapped_column(String(100), nullable=True, comment="父资产ID")
    asset_path: Mapped[str] = mapped_column(String(500), nullable=True, comment="资产路径")
    asset_type: Mapped[str] = mapped_column(String(20), comment="资产类型")
    name: Mapped[str] = mapped_column(String(100), comment="资产名称")

    floor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="楼层数量")
    room_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="房间数量")
    terminal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="终端数量")
    sensor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="传感器数量")

    is_use: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否使用")

    def print_info(self):
        """ 打印基本信息 """
        print("=" * 60)
        print(f"asset_id:           {self.asset_id}")
        print(f"asset_id_parent:    {self.asset_id_parent}")
        print(f"asset_path:         {self.asset_path}")
        print(f"asset_type:         {self.asset_type}")
        print(f"name:               {self.name}")
        print(f"floor_count:        {self.floor_count}")
        print(f"room_count:         {self.room_count}")
        print(f"terminal_count:     {self.terminal_count}")
        print(f"sensor_count:       {self.sensor_count}")
        print(f"is_use:             {self.is_use}")
        print("=" * 60)
