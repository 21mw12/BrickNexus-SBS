"""MQTT/HTTP channel management."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.channel.repository import ChannelHttpRepository, ChannelMqttRepository
from app.domain.channel.repository.models import ChannelHttp, ChannelMqtt, Control, Request
from app.domain.channel.schema.ChannelSchema import (
    HttpChannelAddSchema, HttpChannelEditSchema, HttpChannelQuerySchema,
    MqttChannelAddSchema, MqttChannelEditSchema, MqttChannelQuerySchema,
)
from .ChannelCipher import ChannelCipher


class ChannelService:
    @staticmethod
    def serialize_mqtt(channel: ChannelMqtt) -> dict[str, Any]:
        return {
            "channel_mqtt_id": channel.channel_mqtt_id,
            "broker_host": channel.broker_host,
            "broker_port": channel.broker_port,
            "client_id": channel.client_id,
            "username": channel.username,
            "password_configured": channel.password is not None,
            "qos": channel.qos,
            "connect_timeout": channel.connect_timeout,
            "data_timeout": channel.data_timeout,
            "created_at": channel.created_at,
        }

    @staticmethod
    def serialize_mqtt_summary(channel: ChannelMqtt) -> dict[str, Any]:
        return {
            "channel_mqtt_id": channel.channel_mqtt_id,
            "broker_host": channel.broker_host,
            "broker_port": channel.broker_port,
            "created_at": channel.created_at,
        }

    @staticmethod
    def serialize_http(channel: ChannelHttp) -> dict[str, Any]:
        return {
            "channel_http_id": channel.channel_http_id,
            "base_url": channel.base_url,
            "default_headers": channel.default_headers or {},
            "default_timeout": channel.default_timeout,
            "created_at": channel.created_at,
        }

    @staticmethod
    def serialize_http_summary(channel: ChannelHttp) -> dict[str, Any]:
        return {
            "channel_http_id": channel.channel_http_id,
            "base_url": channel.base_url,
            "created_at": channel.created_at,
        }

    @staticmethod
    def _paginate(db: Session, stmt, count_stmt, page: int, limit: int, serializer) -> dict:
        total = db.execute(count_stmt).scalar_one()
        items = db.execute(stmt.offset((page - 1) * limit).limit(limit)).scalars().all()
        return {"total": total, "items": [serializer(item) for item in items]}

    @classmethod
    def list_mqtt(cls, db: Session, page: int, limit: int, filters: MqttChannelQuerySchema | None):
        stmt = select(ChannelMqtt)
        count = select(func.count()).select_from(ChannelMqtt)
        if filters and filters.broker_host:
            condition = ChannelMqtt.broker_host.ilike(f"%{filters.broker_host}%")
            stmt, count = stmt.where(condition), count.where(condition)
        if filters and filters.username:
            condition = ChannelMqtt.username.ilike(f"%{filters.username}%")
            stmt, count = stmt.where(condition), count.where(condition)
        return cls._paginate(db, stmt.order_by(ChannelMqtt.created_at.desc()), count, page, limit, cls.serialize_mqtt_summary)

    @classmethod
    def list_http(cls, db: Session, page: int, limit: int, filters: HttpChannelQuerySchema | None):
        stmt = select(ChannelHttp)
        count = select(func.count()).select_from(ChannelHttp)
        if filters and filters.base_url:
            condition = ChannelHttp.base_url.ilike(f"%{filters.base_url}%")
            stmt, count = stmt.where(condition), count.where(condition)
        return cls._paginate(db, stmt.order_by(ChannelHttp.created_at.desc()), count, page, limit, cls.serialize_http_summary)

    @classmethod
    def add_mqtt(cls, db: Session, data: MqttChannelAddSchema):
        values = data.model_dump()
        values["password"] = ChannelCipher.encrypt(values["password"])
        values["client_id"] = f"smartbuilding-{uuid.uuid4()}"
        return cls.serialize_mqtt(ChannelMqttRepository().create(ChannelMqtt(**values), db=db))

    @classmethod
    def add_http(cls, db: Session, data: HttpChannelAddSchema):
        values = data.model_dump()
        values["default_headers"] = values["default_headers"] or {}
        return cls.serialize_http(ChannelHttpRepository().create(ChannelHttp(**values), db=db))

    @staticmethod
    def _require_not_active(db: Session, channel_type: str, channel_id: str):
        if db.execute(select(Request.request_id).where(Request.type == channel_type, Request.channel_id == channel_id, Request.status.is_(True))).first():
            raise ValidationError("channel is used by a running request")
        if db.execute(select(Control.control_id).where(Control.type == channel_type, Control.channel_id == channel_id, Control.status.is_(True))).first():
            raise ValidationError("channel is used by an enabled control")

    @staticmethod
    def _require_unreferenced(db: Session, channel_type: str, channel_id: str):
        if db.execute(select(Request.request_id).where(Request.type == channel_type, Request.channel_id == channel_id)).first():
            raise ValidationError("channel is referenced by a request")
        if db.execute(select(Control.control_id).where(Control.type == channel_type, Control.channel_id == channel_id)).first():
            raise ValidationError("channel is referenced by a control")

    @classmethod
    def find_mqtt(cls, db: Session, channel_id: str):
        channel = db.get(ChannelMqtt, channel_id)
        if channel is None:
            raise ValidationError("mqtt channel not found")
        return cls.serialize_mqtt(channel)

    @classmethod
    def find_http(cls, db: Session, channel_id: str):
        channel = db.get(ChannelHttp, channel_id)
        if channel is None:
            raise ValidationError("http channel not found")
        return cls.serialize_http(channel)

    @classmethod
    def edit_mqtt(cls, db: Session, channel_id: str, data: MqttChannelEditSchema):
        channel = db.get(ChannelMqtt, channel_id)
        if channel is None:
            raise ValidationError("mqtt channel not found")
        cls._require_not_active(db, "mqtt", channel_id)
        values = data.model_dump(exclude_unset=True)
        if "password" in values:
            values["password"] = ChannelCipher.encrypt(values["password"])
        updated = ChannelMqttRepository().update(channel_id, values, db=db)
        return cls.serialize_mqtt(updated)

    @classmethod
    def edit_http(cls, db: Session, channel_id: str, data: HttpChannelEditSchema):
        if db.get(ChannelHttp, channel_id) is None:
            raise ValidationError("http channel not found")
        cls._require_not_active(db, "http", channel_id)
        values = data.model_dump(exclude_unset=True)
        if values.get("default_headers") is None and "default_headers" in values:
            values["default_headers"] = {}
        return cls.serialize_http(ChannelHttpRepository().update(channel_id, values, db=db))

    @classmethod
    def drop_mqtt(cls, db: Session, channel_id: str):
        if db.get(ChannelMqtt, channel_id) is None:
            raise ValidationError("mqtt channel not found")
        cls._require_unreferenced(db, "mqtt", channel_id)
        return ChannelMqttRepository().delete(channel_id, db=db)

    @classmethod
    def drop_http(cls, db: Session, channel_id: str):
        if db.get(ChannelHttp, channel_id) is None:
            raise ValidationError("http channel not found")
        cls._require_unreferenced(db, "http", channel_id)
        return ChannelHttpRepository().delete(channel_id, db=db)

    @staticmethod
    def options():
        return {
            "types": [{"label": "MQTT", "value": "mqtt"}, {"label": "HTTP", "value": "http"}],
            "qos": [{"label": f"QoS {value}", "value": value} for value in (0, 1, 2)],
            "http_methods": [{"label": value, "value": value} for value in ("GET", "POST")],
        }
