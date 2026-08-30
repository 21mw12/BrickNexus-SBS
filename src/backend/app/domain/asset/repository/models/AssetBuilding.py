from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from app.infra.DB.SQLConnection import Base


class AssetBuilding(Base):
    __tablename__ = "assets_building"

    ATTRIBUTES = [
        {"field": "name", "label": "资产名称"},
        {"field": "number", "label": "建筑编号"},
    ]

    asset_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="资产ID")
    number: Mapped[str] = mapped_column(String(50), nullable=True, comment="建筑编号")
    address: Mapped[str] = mapped_column(String(200), nullable=True, comment="地址")

    def print_info(self):
        """ 打印基本信息 """
        print("=" * 60)
        print(f"asset_id:           {self.asset_id}")
        print(f"number:             {self.number}")
        print(f"address:            {self.address}")
        print("=" * 60)
