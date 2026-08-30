from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from app.infra.DB.SQLConnection import Base


class AssetFloor(Base):
    __tablename__ = "assets_floor"

    ATTRIBUTES = [
        {"field": "level", "label": "楼层号"},
    ]

    asset_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="资产ID")    
    level: Mapped[str] = mapped_column(String(20), nullable=True, comment="楼层等级")

    def print_info(self):
        """ 打印基本信息 """
        print("=" * 60)
        print(f"asset_id:           {self.asset_id}")
        print(f"level:              {self.level}")
        print("=" * 60)
