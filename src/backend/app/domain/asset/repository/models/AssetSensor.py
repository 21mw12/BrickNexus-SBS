from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Boolean

from app.infra.DB.SQLConnection import Base


class AssetSensor(Base):
    __tablename__ = "assets_sensor"

    ATTRIBUTES = [
        {"field": "asset_id", "label": "资产ID"},
        {"field": "model_id", "label": "传感器型号ID"},
        {"field": "is_online", "label": "是否在线"},
        {"field": "last_receive_time", "label": "最后接收数据时间"},
    ]

    asset_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="资产ID")
    model_id: Mapped[str] = mapped_column(String(100), nullable=True, comment="传感器型号ID")
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否在线")
    last_receive_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最后接收数据时间")

    def print_info(self):
        """ 打印基本信息 """
        print("=" * 60)
        print(f"asset_id:           {self.asset_id}")
        print(f"model_id:           {self.model_id}")
        print(f"is_online:          {self.is_online}")
        print(f"last_receive_time:  {self.last_receive_time}")
        print("=" * 60)
