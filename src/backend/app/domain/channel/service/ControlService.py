"""Terminal/sensor control configuration and synchronous execution."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.core.utils.HTTPRequestor import HttpUtil
from app.domain.asset.repository.models.Asset import Asset
from app.domain.channel.repository.ControlRepository import ControlRepository
from app.domain.channel.repository.models.Control import Control
from app.domain.channel.schema.ControlSchema import ControlEditSchema, ControlQuerySchema
from app.infra.MQTT import (
    MQTTConnectionOptions,
    MQTTPublisher,
    MQTTTransportError,
)
from .ChannelCipher import ChannelCipher
from .ChannelResolver import ChannelResolver, join_http_url
from .ChannelService import ChannelService


mqtt_publisher = MQTTPublisher()


class ControlService:
    @staticmethod
    def get_bound_asset_id(db: Session, control_id: str) -> str | None:
        """返回 Control 绑定的资产 ID，不向 API 暴露 ORM 模型。"""
        control = db.get(Control, control_id)
        if control is None:
            return None
        return control.asset_id

    @staticmethod
    def _asset(
        db: Session, asset_type: str, asset_id: str, require_enabled: bool = False
    ) -> Asset:
        if asset_type not in {"terminal", "sensor"}:
            raise ValidationError("asset_type must be 'terminal' or 'sensor'")
        asset = db.scalar(select(Asset).where(
            Asset.asset_id == asset_id, Asset.asset_type == asset_type
        ))
        if asset is None:
            raise ValidationError(f"{asset_type} asset not found")
        if require_enabled and not asset.is_use:
            raise ValidationError(f"{asset_type} asset is disabled")
        return asset

    @classmethod
    def _serialize(cls, db: Session, control: Control):
        asset = cls._asset(db, control.asset_type, control.asset_id)
        channel = ChannelResolver.get_channel(db, control.type, control.channel_id)
        return {
            "control_id": control.control_id, "name": control.name, "type": control.type,
            "channel_id": control.channel_id, "asset_type": control.asset_type,
            "asset_id": control.asset_id,
            "status": control.status, "created_at": control.created_at,
            "mqtt_topic": control.mqtt_topic, "mqtt_retained": control.mqtt_retained,
            "mqtt_payload": control.mqtt_payload, "http_method": control.http_method,
            "http_path": control.http_path, "http_header": control.http_header,
            "http_params": control.http_params, "http_body": control.http_body,
            "asset": {
                "asset_id": asset.asset_id, "asset_type": asset.asset_type,
                "name": asset.name, "is_use": asset.is_use,
            },
            "channel": ChannelService.serialize_mqtt(channel) if control.type == "mqtt" else ChannelService.serialize_http(channel),
        }

    @staticmethod
    def _validate_protocol(values: dict):
        result = dict(values)
        if result.get("type") == "mqtt":
            if not result.get("mqtt_topic") or not result.get("mqtt_payload"):
                raise ValidationError("mqtt_topic and mqtt_payload are required")
            if result.get("mqtt_retained") is None:
                result["mqtt_retained"] = False
            for field in ("http_method", "http_path", "http_header", "http_params", "http_body"):
                result[field] = None
        elif result.get("type") == "http":
            method = result.get("http_method")
            if method not in {"GET", "POST"} or not result.get("http_path"):
                raise ValidationError("http_method and http_path are required")
            if method == "GET" and result.get("http_body") is not None:
                raise ValidationError("GET control cannot configure http_body")
            if method == "POST" and result.get("http_params") is not None:
                raise ValidationError("POST control cannot configure http_params")
            result["mqtt_topic"] = result["mqtt_retained"] = result["mqtt_payload"] = None
        else:
            raise ValidationError("type must be 'mqtt' or 'http'")
        return result

    @classmethod
    def list_controls(
        cls, db: Session,
        page: int, limit: int,
        filters: ControlQuerySchema | None,
        viewable_asset_ids: set[str] | None,
    ):
        conditions = []
        if viewable_asset_ids is None:
            # root：不添加 asset_id 权限范围条件。
            pass
        elif not viewable_asset_ids:
            # 非 root 且没有任何可见资产。
            return {"total": 0, "items": []}
        else:
            conditions.append(Control.asset_id.in_(viewable_asset_ids))
        
        if filters:
            if filters.name: conditions.append(Control.name.ilike(f"%{filters.name}%"))
            if filters.type: conditions.append(Control.type == filters.type)
            if filters.status is not None: conditions.append(Control.status == filters.status)
            if filters.asset_type: conditions.append(Control.asset_type == filters.asset_type)
            if filters.asset_id: conditions.append(Control.asset_id == filters.asset_id)
        
        stmt = select(Control).where(*conditions)
        count = select(func.count()).select_from(Control).where(*conditions)
        total = db.execute(count).scalar_one()
        rows = db.execute(stmt.order_by(Control.created_at.desc()).offset((page - 1) * limit).limit(limit)).scalars().all()
        return {
            "total": total,
            "items": [
                {
                    "control_id": row.control_id,
                    "name": row.name,
                    "type": row.type,
                    "asset_type": row.asset_type,
                    "asset_name": cls._asset(db, row.asset_type, row.asset_id).name,
                    "status": row.status,
                    "created_at": row.created_at,
                }
                for row in rows
            ],
        }

    @classmethod
    def find(cls, db: Session, control_id: str):
        control = db.get(Control, control_id)
        if control is None: raise ValidationError("control not found")
        return cls._serialize(db, control)

    @classmethod
    def add(cls, db: Session, data):
        values = cls._validate_protocol(data.model_dump())
        cls._asset(db, values["asset_type"], values["asset_id"])
        ChannelResolver.get_channel(db, values["type"], values["channel_id"])
        control = ControlRepository().create(Control(**values), db=db)
        return cls._serialize(db, control)

    @classmethod
    def edit(cls, db: Session, control_id: str, data: ControlEditSchema):
        control = db.get(Control, control_id)
        if control is None: raise ValidationError("control not found")
        if control.status: raise ValidationError("enabled control cannot be edited")
        fields = ("name", "type", "channel_id", "asset_type", "asset_id", "mqtt_topic", "mqtt_retained", "mqtt_payload", "http_method", "http_path", "http_header", "http_params", "http_body")
        values = {field: getattr(control, field) for field in fields}
        values.update(data.model_dump(exclude_unset=True))
        values = cls._validate_protocol(values)
        cls._asset(db, values["asset_type"], values["asset_id"])
        ChannelResolver.get_channel(db, values["type"], values["channel_id"])
        return cls._serialize(db, ControlRepository().update(control_id, values, db=db))

    @classmethod
    def toggle(cls, db: Session, control_id: str):
        control = db.get(Control, control_id)
        if control is None: raise ValidationError("control not found")
        target = not control.status
        if target:
            cls._asset(db, control.asset_type, control.asset_id, True)
            ChannelResolver.get_channel(db, control.type, control.channel_id)
        ControlRepository().update(control_id, {"status": target}, db=db)
        return True

    @classmethod
    def drop(cls, db: Session, control_id: str):
        control = db.get(Control, control_id)
        if control is None: raise ValidationError("control not found")
        if control.status: raise ValidationError("enabled control cannot be deleted")
        return ControlRepository().delete(control_id, db=db)

    @classmethod
    def execute(cls, db: Session, control_id: str):
        control = db.get(Control, control_id)
        if control is None: raise ValidationError("control not found")
        if not control.status: raise ValidationError("disabled control cannot be executed")
        cls._asset(db, control.asset_type, control.asset_id, True)
        channel = ChannelResolver.get_channel(db, control.type, control.channel_id)
        executed_at = datetime.now(timezone.utc)
        if control.type == "http":
            headers = dict(channel.default_headers or {}); headers.update(control.http_header or {})
            ok, value = HttpUtil._request(
                method=control.http_method, url=join_http_url(channel.base_url, control.http_path),
                headers=headers, params=control.http_params if control.http_method == "GET" else None,
                json=control.http_body if control.http_method == "POST" else None,
                timeout=channel.default_timeout, return_json=True,
            )
            if not ok: raise ValidationError(f"control HTTP request failed: {value}")
            result = {"protocol": "http", "response": value}
        else:
            try:
                published = mqtt_publisher.publish_once(
                    MQTTConnectionOptions(
                        host=channel.broker_host,
                        port=channel.broker_port,
                        client_id=channel.client_id,
                        username=channel.username,
                        password=ChannelCipher.decrypt(channel.password),
                        keepalive=channel.connect_timeout,
                    ),
                    topic=control.mqtt_topic,
                    payload=control.mqtt_payload,
                    qos=channel.qos,
                    retain=control.mqtt_retained,
                    timeout=channel.connect_timeout,
                )
            except MQTTTransportError as exc:
                raise ValidationError(str(exc)) from exc
            result = {
                "protocol": "mqtt",
                "message_id": published.message_id,
                "published": published.published,
            }
        return {"success": True, "executed_at": executed_at, "result": result}
