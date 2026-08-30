"""MQTT 通道数据库模型。"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.DB.SQLConnection import Base


class ChannelMqtt(Base):
    __tablename__ = "channel_mqtt"
    __table_args__ = (
        CheckConstraint("broker_port BETWEEN 1 AND 65535", name="ck_channel_mqtt_port"),
        CheckConstraint("qos IN (0, 1, 2)", name="ck_channel_mqtt_qos"),
        CheckConstraint("connect_timeout > 0", name="ck_channel_mqtt_connect_timeout"),
        CheckConstraint("data_timeout > 0", name="ck_channel_mqtt_data_timeout"),
        UniqueConstraint("client_id", name="uq_channel_mqtt_client_id"),
        Index("ix_channel_mqtt_broker", "broker_host", "broker_port"),
    )

    channel_mqtt_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    broker_host: Mapped[str] = mapped_column(String(30), nullable=False)
    broker_port: Mapped[int] = mapped_column(Integer, nullable=False, default=1883)
    client_id: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[str | None] = mapped_column(String(20), nullable=True)
    password: Mapped[str | None] = mapped_column(Text, nullable=True)
    qos: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    connect_timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    data_timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

