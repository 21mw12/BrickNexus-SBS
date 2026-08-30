from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from app.infra.DB.SQLConnection import Base


class SensorModel(Base):
    __tablename__ = "model"

    ATTRIBUTES = [
        {"field": "model_id", "label": "型号ID"},
        {"field": "sensor_type", "label": "传感器类型"},
        {"field": "model_name", "label": "传感器型号"},
        {"field": "remark", "label": "备注"},
    ]

    model_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="型号ID")
    sensor_type: Mapped[str] = mapped_column(String(50), nullable=True, comment="传感器类型")
    model_name: Mapped[str] = mapped_column(String(50), nullable=True, comment="传感器型号")
    remark: Mapped[str] = mapped_column(String(100), nullable=True, comment="备注")

    def print_info(self):
        """ 打印基本信息 """
        print("=" * 60)
        print(f"model_id:           {self.model_id}")
        print(f"sensor_type:        {self.sensor_type}")
        print(f"model_name:         {self.model_name}")
        print(f"remark:             {self.remark}")
        print("=" * 60)
