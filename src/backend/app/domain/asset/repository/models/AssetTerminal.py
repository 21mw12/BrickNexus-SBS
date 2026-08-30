from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Boolean

from app.infra.DB.SQLConnection import Base


class AssetTerminal(Base):
    __tablename__ = "assets_terminal"

    ATTRIBUTES = [
        {"field": "asset_id", "label": "资产ID"},
        {"field": "request_id", "label": "数据请求ID"},
        {"field": "number", "label": "终端编号"},
        {"field": "model", "label": "终端类型"},
        {"field": "location", "label": "安装位置"},
        {"field": "iot_number", "label": "物联网卡号"},
        {"field": "iot_activate_human", "label": "物联网卡激活人"},
        {"field": "is_online", "label": "是否在线"},
        {"field": "last_receive_time", "label": "最后接收数据时间"},
    ]

    asset_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="资产ID")
    request_id: Mapped[str] = mapped_column(String(100), nullable=True, comment="数据请求ID")
    number: Mapped[str] = mapped_column(String(50), nullable=True, comment="终端编号")
    model: Mapped[str] = mapped_column(String(50), nullable=True, comment="终端类型")
    location: Mapped[str] = mapped_column(String(100), nullable=True, comment="安装位置")
    iot_number: Mapped[str] = mapped_column(String(50), nullable=True, comment="物联网卡号")
    iot_activate_human: Mapped[str] = mapped_column(String(50), nullable=True, comment="物联网卡激活人")
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否在线")
    last_receive_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最后接收数据时间")

    def print_info(self):
        """ 打印基本信息 """
        print("=" * 60)
        print(f"asset_id:           {self.asset_id}")
        print(f"request_id:         {self.request_id}")
        print(f"number:             {self.number}")
        print(f"model:              {self.model}")
        print(f"location:           {self.location}")
        print(f"iot_number:         {self.iot_number}")
        print(f"iot_activate_human: {self.iot_activate_human}")
        print(f"is_online:          {self.is_online}")
        print(f"last_receive_time:  {self.last_receive_time}")
        print("=" * 60)
