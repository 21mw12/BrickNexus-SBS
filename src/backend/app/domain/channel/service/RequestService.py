"""Request CRUD and collector lifecycle for normalized channel configurations."""

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.core.middleware.LogRecorder import get_logger
from app.core.utils.HTTPRequestor import HttpUtil
from app.domain.asset.repository.AssetTerminalRepository import AssetTerminalRepository
from app.domain.channel.repository.RequestRepository import RequestRepository
from app.domain.channel.repository.models.Request import Request
from app.domain.channel.schema.RequestSchema import RequestEditSchema, RequestQuerySchema
from app.domain.collector.loader.request_loader import request_loader
from app.infra.MQTT import MQTTConnectionOptions, MQTTProbe, MQTTTransportError
from .ChannelResolver import ChannelResolver, ResolvedRequest
from .ChannelService import ChannelService

logger = get_logger(__name__)
mqtt_probe = MQTTProbe()


class RequestService:
    @staticmethod
    def _serialize(req: Request, db: Session) -> dict[str, Any]:
        channel = ChannelResolver.get_channel(db, req.type, req.channel_id)
        channel_data = (
            ChannelService.serialize_mqtt(channel)
            if req.type == "mqtt"
            else ChannelService.serialize_http(channel)
        )
        return {
            "request_id": req.request_id,
            "name": req.name,
            "type": req.type,
            "channel_id": req.channel_id,
            "interval_seconds": req.interval_seconds,
            "time_json_path": req.time_json_path,
            "time_format": req.time_format,
            "status": req.status,
            "created_at": req.created_at,
            "mqtt_topic": req.mqtt_topic,
            "http_method": req.http_method,
            "http_path": req.http_path,
            "http_header": req.http_header,
            "http_params": req.http_params,
            "http_body": req.http_body,
            "channel": channel_data,
        }

    @staticmethod
    def _validate_protocol(values: dict) -> dict:
        result = dict(values)
        request_type = result.get("type")
        if request_type == "mqtt":
            if not result.get("mqtt_topic"):
                raise ValidationError("mqtt_topic is required for MQTT request")
            for key in ("http_method", "http_path", "http_header", "http_params", "http_body"):
                result[key] = None
        elif request_type == "http":
            method = result.get("http_method")
            if method not in {"GET", "POST"} or not result.get("http_path"):
                raise ValidationError("http_method and http_path are required for HTTP request")
            if method == "GET" and result.get("http_body") is not None:
                raise ValidationError("GET request cannot configure http_body")
            if method == "POST" and result.get("http_params") is not None:
                raise ValidationError("POST request cannot configure http_params")
            result["mqtt_topic"] = None
        else:
            raise ValidationError("type must be 'mqtt' or 'http'")
        return result

    @staticmethod
    def _validate_unique(db: Session, values: dict, exclude_id: str | None = None):
        stmt = select(Request.request_id).where(
            Request.type == values["type"], Request.channel_id == values["channel_id"]
        )
        if values["type"] == "mqtt":
            stmt = stmt.where(Request.mqtt_topic == values["mqtt_topic"])
        else:
            stmt = stmt.where(Request.http_path == values["http_path"])
        if exclude_id:
            stmt = stmt.where(Request.request_id != exclude_id)
        if db.execute(stmt).first():
            raise ValidationError("a request with the same channel and protocol target already exists")

    @classmethod
    def list_requests(cls, db: Session, page=1, limit=20, filters: RequestQuerySchema | None = None):
        stmt = select(Request)
        count_stmt = select(func.count()).select_from(Request)
        conditions = []
        if filters:
            if filters.name:
                conditions.append(Request.name.ilike(f"%{filters.name}%"))
            if filters.type:
                conditions.append(Request.type == filters.type)
            if filters.status is not None:
                conditions.append(Request.status == filters.status)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        total = db.execute(count_stmt).scalar_one()
        rows = db.execute(
            stmt.order_by(Request.created_at.desc()).offset((page - 1) * limit).limit(limit)
        ).scalars().all()
        return {
            "total": total,
            "items": [
                {
                    "request_id": row.request_id,
                    "name": row.name,
                    "type": row.type,
                    "status": row.status,
                    "created_at": row.created_at,
                }
                for row in rows
            ],
        }

    @classmethod
    def create_request(cls, data, db: Session):
        values = cls._validate_protocol(data.model_dump())
        ChannelResolver.get_channel(db, values["type"], values["channel_id"])
        cls._validate_unique(db, values)
        request = RequestRepository().create(Request(**values), db=db)
        return cls._serialize(request, db)

    @classmethod
    def find_request(cls, request_id: str, db: Session):
        request = db.get(Request, request_id)
        if request is None:
            raise ValidationError("request not found")
        return cls._serialize(request, db)

    @classmethod
    def edit_request(cls, request_id: str, data: RequestEditSchema, db: Session):
        request = db.get(Request, request_id)
        if request is None:
            raise ValidationError("request not found")
        if request.status:
            raise ValidationError("running request cannot be edited")
        current = {
            key: getattr(request, key)
            for key in (
                "name", "type", "channel_id", "interval_seconds", "time_json_path", "time_format",
                "mqtt_topic", "http_method", "http_path", "http_header", "http_params", "http_body",
            )
        }
        current.update(data.model_dump(exclude_unset=True))
        current = cls._validate_protocol(current)
        ChannelResolver.get_channel(db, current["type"], current["channel_id"])
        cls._validate_unique(db, current, request_id)
        updated = RequestRepository().update(request_id, current, db=db)
        return cls._serialize(updated, db)

    @classmethod
    def toggle_active(cls, request_id: str, db: Session):
        request = db.get(Request, request_id)
        if request is None:
            raise ValidationError("request not found")
        target = not request.status
        resolved = ChannelResolver.resolve_request(db, request) if target else None
        RequestRepository().update(request_id, {"status": target}, db=db)
        try:
            if target:
                request_loader.start(resolved)
            else:
                request_loader.stop(request.type, request_id)
        except Exception as exc:
            if target:
                try:
                    request_loader.stop(request.type, request_id)
                except Exception:
                    logger.exception("failed to clean a partially started request %s", request_id)
            raise ValidationError(str(exc)) from exc
        db.flush()
        return cls._serialize(db.get(Request, request_id), db)

    @staticmethod
    def _test_http(info: dict, timeout: float):
        success, value = HttpUtil._request(
            method=info["method"], url=info["url"], headers=info.get("headers"),
            params=info.get("params"), json=info.get("body") if info["method"] == "POST" else None,
            timeout=timeout, return_json=True,
        )
        return {"ok": success, "data": value if success else None, "message": None if success else str(value)}

    @staticmethod
    def _test_mqtt(info: dict, timeout: float):
        host, port_text = info["address"].rsplit(":", 1)
        result = {"ok": False, "data": None, "message": None}
        try:
            probe_result = mqtt_probe.receive_once(
                MQTTConnectionOptions(
                    host=host,
                    port=int(port_text),
                    client_id=info.get("client_id"),
                    username=info.get("username"),
                    password=info.get("password"),
                    keepalive=max(10, int(timeout)),
                ),
                topic=info["topic"],
                qos=info["qos"],
                timeout=timeout,
            )
            if probe_result.payload is not None:
                raw = probe_result.payload.decode("utf-8", errors="replace")
                try:
                    result["data"] = json.loads(raw)
                except ValueError:
                    result["data"] = raw
                result["message"] = "ok"
            else:
                result["message"] = "connected; no message received before timeout"
            result["ok"] = True
        except MQTTTransportError as exc:
            result["message"] = str(exc)
        except Exception as exc:
            # Keep the public test endpoint's existing error response contract.
            result["message"] = str(exc)
        return result

    @classmethod
    def test_request(cls, request_id: str, timeout: float, db: Session):
        request = db.get(Request, request_id)
        if request is None:
            raise ValidationError("request not found")
        resolved = ChannelResolver.resolve_request(db, request)
        return cls._test_http(resolved.request_info, timeout) if request.type == "http" else cls._test_mqtt(resolved.request_info, timeout)

    @staticmethod
    def delete_request(request_id: str, db: Session):
        request = db.get(Request, request_id)
        if request is None:
            raise ValidationError("request not found")
        if request.status:
            raise ValidationError("running request cannot be deleted")
        terminal_repo = AssetTerminalRepository()
        for terminal in terminal_repo.select(db, filters={"request_id": request_id}):
            terminal_repo.update(terminal.asset_id, {"request_id": None}, db=db)
        return RequestRepository().delete(request_id, db=db)
