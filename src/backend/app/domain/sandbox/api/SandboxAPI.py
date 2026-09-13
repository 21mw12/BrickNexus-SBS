from __future__ import annotations

import csv
import io
import json

from fastapi import (
    APIRouter, Body, Depends, File, Form, Header, Path, Query, UploadFile,
    WebSocket, WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.common.Response import Response
from app.common.validators import ValidationError
from app.core.middleware.LogRecorder import get_logger
from app.domain.common.AuthDecorator import require_page
from app.domain.common.PermissionChecker import (
    check_asset_instance_permission, check_page_permission,
)
from app.domain.rule.schema import RuleConfig
from app.domain.sandbox.repository.models import Sandbox, SandboxEvent
from app.domain.sandbox.repository import (
    SandboxEventRepository, SandboxMeasurementRepository,
)
from app.domain.sandbox.schema import (
    SandboxCreateSchema, SandboxDataQuerySchema, SandboxEditSchema,
    SandboxEventQuerySchema, SandboxFaultSchema, SandboxRawQuerySchema,
    SandboxSpeedSchema,
)
from app.domain.sandbox.service.SandboxDataService import (
    sandbox_data_service, sandbox_point_ids,
)
from app.domain.sandbox.service.SandboxFaultRuntime import sandbox_fault_runtime
from app.domain.sandbox.service.SandboxRealtimeService import sandbox_realtime_service
from app.domain.sandbox.service.SandboxRuleService import sandbox_rule_service
from app.domain.sandbox.service.SandboxRuntime import sandbox_runtime
from app.domain.sandbox.service.SandboxService import sandbox_service
from app.infra.DB.SQLConnection import sql_manager


router = APIRouter(prefix="/sandbox", tags=["sandbox"])
ws_router = APIRouter(tags=["sandbox-realtime"])
logger = get_logger(__name__)


def _parse_sandbox_subscription(payload) -> tuple[str, list[str], int]:
    if not isinstance(payload, dict):
        raise ValidationError("message must be a JSON object")
    if payload.get("type") != "subscribe":
        raise ValidationError("message type must be subscribe")
    token = payload.get("token")
    if not isinstance(token, str) or not token.strip():
        raise ValidationError("token must be a non-empty string")
    point_ids = payload.get("point_ids")
    if not isinstance(point_ids, list):
        raise ValidationError("point_ids must be a list")
    normalized: list[str] = []
    seen: set[str] = set()
    for point_id in point_ids:
        if not isinstance(point_id, str) or not point_id.strip():
            raise ValidationError("each point_id must be a non-empty string")
        point_id = point_id.strip()
        if point_id not in seen:
            normalized.append(point_id)
            seen.add(point_id)
    if len(normalized) > 10:
        raise ValidationError("at most 10 point_ids may be subscribed")
    history_limit = payload.get("history_limit", 500)
    if isinstance(history_limit, bool) or not isinstance(history_limit, int):
        raise ValidationError("history_limit must be an integer")
    if not 1 <= history_limit <= 500:
        raise ValidationError("history_limit must be between 1 and 500")
    return token.strip(), normalized, history_limit


def _event(event: SandboxEvent) -> dict:
    return {
        "event_id": event.event_id,
        "sandbox_id": event.sandbox_id,
        "tick": event.tick,
        "event_type": event.event_type,
        "payload": event.payload,
    }


@router.get("/list")
def list_sandboxes(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    return Response.success(sandbox_service.list(db, page, limit))


@router.get("/find/{sandbox_id}")
def find_sandbox(
    sandbox_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    try:
        return Response.success(sandbox_service.find(sandbox_id, db))
    except ValidationError as exc:
        return Response.error_params(str(exc))


@router.post("/add")
def add_sandbox(
    data: SandboxCreateSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    try:
        result = sandbox_service.create(data, db)
        db.commit()
        return Response.success(result)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))


@router.post("/edit/{sandbox_id}")
def edit_sandbox(
    sandbox_id: str, data: SandboxEditSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    try:
        result = sandbox_service.edit(sandbox_id, data, db)
        db.commit()
        return Response.success(result)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))


@router.post("/toggle/{sandbox_id}")
async def toggle_sandbox(
    sandbox_id: str, _auth: None = require_page("sandbox"),
):
    try:
        return Response.success(await sandbox_runtime.toggle(sandbox_id))
    except ValidationError as exc:
        return Response.error_params(str(exc))


@router.post("/speed/{sandbox_id}")
async def change_speed(
    sandbox_id: str, data: SandboxSpeedSchema = Body(...),
    _auth: None = require_page("sandbox"),
):
    try:
        return Response.success(await sandbox_runtime.set_speed(sandbox_id, data.speed))
    except ValidationError as exc:
        return Response.error_params(str(exc))


@router.post("/pause/{sandbox_id}")
async def pause_sandbox(
    sandbox_id: str, _auth: None = require_page("sandbox"),
):
    try:
        return Response.success(await sandbox_runtime.pause(sandbox_id))
    except ValidationError as exc:
        return Response.error_params(str(exc))


@router.get("/drop/{sandbox_id}")
async def drop_sandbox(
    sandbox_id: str,
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    try:
        row = db.get(Sandbox, sandbox_id)
        if row is None:
            raise ValidationError("sandbox not found")
        if row.state:
            raise ValidationError("running sandbox cannot be deleted")
        await sandbox_runtime.remove(sandbox_id)
        sandbox_service.delete(sandbox_id, db)
        db.commit()
        sandbox_rule_service.remove_directory(sandbox_id)
        return Response.success({"ok": True})
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))


@router.get("/export/{sandbox_id}")
def export_sandbox(
    sandbox_id: str,
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    try:
        content = sandbox_service.export_config(sandbox_id, db)
        return StreamingResponse(
            iter((content,)), media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="sandbox-{sandbox_id}.json"'},
        )
    except ValidationError as exc:
        return Response.error_params(str(exc))


@router.post("/import")
async def import_sandbox(
    sandbox_name: str = Form(..., min_length=1, max_length=30),
    description: str | None = Form(default=None, max_length=500),
    file: UploadFile = File(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    try:
        content = await file.read()
        if len(content) > 2 * 1024 * 1024:
            raise ValidationError("sandbox import file is too large")
        result = sandbox_service.import_config(
            sandbox_name, description, content, db
        )
        db.commit()
        return Response.success(result)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))


@router.get("/baseline/{sensor_id}")
def sensor_baseline(
    sensor_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    try:
        if not check_asset_instance_permission(authorization or "", sensor_id, "R", db):
            return Response.error_forbidden("permission denied")
        return Response.success(sandbox_service.baseline(sensor_id, db))
    except ValidationError as exc:
        return Response.error_params(str(exc))


@router.get("/catalog/models")
def catalog_models(
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    return Response.success(sandbox_service.catalog_models(db))


@router.get("/catalog/models/{model_id}/sensors")
def catalog_model_sensors(
    model_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    try:
        return Response.success(
            sandbox_service.catalog_sensors(model_id, authorization or "", db)
        )
    except ValidationError as exc:
        return Response.error_params(str(exc))


@router.post("/{sandbox_id}/measurements/raw")
def raw_measurements(
    sandbox_id: str, data: SandboxRawQuerySchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    try:
        return Response.success(sandbox_data_service.query_raw(sandbox_id, data, db))
    except ValidationError as exc:
        return Response.error_params(str(exc))


@router.post("/{sandbox_id}/measurements/query")
def sampled_measurements(
    sandbox_id: str, data: SandboxDataQuerySchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    try:
        return Response.success(sandbox_data_service.query_sampled(sandbox_id, data, db))
    except ValidationError as exc:
        return Response.error_params(str(exc))


@router.get("/{sandbox_id}/measurements/export")
def export_measurements(
    sandbox_id: str, _auth: None = require_page("sandbox"),
):
    def rows():
        yield "\ufeffsandbox_id,point_id,tick,value\r\n"
        with sql_manager.get_db("main") as db:
            if db.get(Sandbox, sandbox_id) is None:
                return
            for item in sandbox_data_service.repository.stream_sandbox(sandbox_id, db):
                target = io.StringIO()
                csv.writer(target).writerow([
                    item.sandbox_id, item.point_id, item.tick, item.value,
                ])
                yield target.getvalue()
    return StreamingResponse(
        rows(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="sandbox-{sandbox_id}-measurements.csv"'},
    )


@router.post("/{sandbox_id}/faults/inject")
async def inject_fault(
    sandbox_id: str, data: SandboxFaultSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    try:
        event = sandbox_fault_runtime.inject(sandbox_id, data, db)
        db.commit()
        payload = _event(event)
        await sandbox_realtime_service.publish(
            sandbox_id, {"type": "fault_event", "event": payload}
        )
        return Response.success(payload)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))


@router.post("/{sandbox_id}/faults/{event_id}/stop")
async def stop_fault(
    sandbox_id: str, event_id: str,
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    try:
        sandbox = db.get(Sandbox, sandbox_id)
        if sandbox is None:
            raise ValidationError("sandbox not found")
        event = sandbox_fault_runtime.stop(sandbox_id, event_id, sandbox.tick, db)
        db.commit()
        payload = _event(event)
        await sandbox_realtime_service.publish(
            sandbox_id, {"type": "fault_event", "event": payload}
        )
        return Response.success(payload)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))


@router.get("/{sandbox_id}/faults/active")
def active_faults(
    sandbox_id: str,
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    sandbox = db.get(Sandbox, sandbox_id)
    if sandbox is None:
        return Response.error_params("sandbox not found")
    # Include faults scheduled for the next tick so an injection is visible
    # immediately instead of only after a page refresh.
    return Response.success(sandbox_fault_runtime.active(sandbox_id))


@router.post("/{sandbox_id}/events")
def list_events(
    sandbox_id: str, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    filters: SandboxEventQuerySchema | None = Body(default=None),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("sandbox"),
):
    total, rows = SandboxEventRepository.list_page(
        sandbox_id, db, page, limit, filters.event_type if filters else None
    )
    return Response.success({"total": total, "items": [_event(item) for item in rows]})


@router.get("/{sandbox_id}/rules/list")
def list_rules(sandbox_id: str, db: Session = Depends(sql_manager.get_db_dep("main")), _auth: None = require_page("sandbox")):
    try:
        return Response.success(sandbox_rule_service.list_rules(sandbox_id, db))
    except ValidationError as exc:
        return Response.error_params(str(exc))


@router.get("/{sandbox_id}/rules/find/{rule_id}")
def find_rule(sandbox_id: str, rule_id: str, db: Session = Depends(sql_manager.get_db_dep("main")), _auth: None = require_page("sandbox")):
    try:
        return Response.success(sandbox_rule_service.find(sandbox_id, rule_id, db))
    except ValidationError as exc:
        return Response.error_params(str(exc))


@router.post("/{sandbox_id}/rules/add")
def add_rule(sandbox_id: str, data: RuleConfig = Body(...), db: Session = Depends(sql_manager.get_db_dep("main")), _auth: None = require_page("sandbox")):
    try:
        result = sandbox_rule_service.create(sandbox_id, data, db)
        db.commit()
        return Response.success(result)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))


@router.post("/{sandbox_id}/rules/edit/{rule_id}")
def edit_rule(sandbox_id: str, rule_id: str, data: RuleConfig = Body(...), db: Session = Depends(sql_manager.get_db_dep("main")), _auth: None = require_page("sandbox")):
    try:
        result = sandbox_rule_service.edit(sandbox_id, rule_id, data, db)
        db.commit()
        return Response.success(result)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))


@router.post("/{sandbox_id}/rules/toggle/{rule_id}")
def toggle_rule(sandbox_id: str, rule_id: str, db: Session = Depends(sql_manager.get_db_dep("main")), _auth: None = require_page("sandbox")):
    try:
        result = sandbox_rule_service.toggle(sandbox_id, rule_id, db)
        db.commit()
        return Response.success(result)
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))


@router.get("/{sandbox_id}/rules/drop/{rule_id}")
def drop_rule(sandbox_id: str, rule_id: str, db: Session = Depends(sql_manager.get_db_dep("main")), _auth: None = require_page("sandbox")):
    try:
        result = sandbox_rule_service.delete(sandbox_id, rule_id, db)
        db.commit()
        return Response.success({"ok": result})
    except ValidationError as exc:
        db.rollback()
        return Response.error_params(str(exc))


@router.get("/{sandbox_id}/rules/ttl/{rule_id}")
def rule_ttl(sandbox_id: str, rule_id: str, db: Session = Depends(sql_manager.get_db_dep("main")), _auth: None = require_page("sandbox")):
    try:
        return Response.success({"rule_id": rule_id, "ttl": sandbox_rule_service.ttl(sandbox_id, rule_id, db)})
    except ValidationError as exc:
        return Response.error_params(str(exc))


@ws_router.websocket("/ws/sandboxes/{sandbox_id}")
async def sandbox_websocket(websocket: WebSocket, sandbox_id: str):
    await websocket.accept()
    connection = await sandbox_realtime_service.register(websocket, sandbox_id)
    try:
        while True:
            try:
                payload = await websocket.receive_json()
                token, requested_point_ids, history_limit = (
                    _parse_sandbox_subscription(payload)
                )
            except WebSocketDisconnect:
                raise
            except (ValidationError, json.JSONDecodeError) as exc:
                await sandbox_realtime_service.enqueue(
                    connection,
                    {
                        "type": "error",
                        "code": "invalid_message",
                        "message": str(exc),
                    },
                )
                continue

            if not check_page_permission(token, ["sandbox"]):
                await sandbox_realtime_service.enqueue(
                    connection,
                    {
                        "type": "error",
                        "code": "unauthorized",
                        "message": "permission denied",
                    },
                )
                await websocket.close(code=1008)
                return

            try:
                with sql_manager.get_db("main") as db:
                    snapshot = sandbox_service.find(sandbox_id, db)
                    sandbox = db.get(Sandbox, sandbox_id)
                    known_point_ids = sandbox_point_ids(snapshot["config"])
                    accepted = [
                        point_id
                        for point_id in requested_point_ids
                        if point_id in known_point_ids
                    ]
                    accepted_set = set(accepted)
                    rejected = [
                        point_id
                        for point_id in requested_point_ids
                        if point_id not in accepted_set
                    ]
                    generation = await sandbox_realtime_service.replace_subscriptions(
                        connection, accepted
                    )
                    rows = SandboxMeasurementRepository.recent_for_points(
                        sandbox_id, accepted, history_limit, db
                    )
                    sandbox_fault_runtime.restore(sandbox, db)
                    active_faults = sandbox_fault_runtime.active(sandbox_id)
            except ValidationError as exc:
                await sandbox_realtime_service.enqueue(
                    connection,
                    {
                        "type": "error",
                        "code": "sandbox_not_found",
                        "message": str(exc),
                    },
                )
                continue
            except Exception as exc:
                logger.exception(
                    "沙盒 WebSocket 快照读取失败 sandbox_id=%s error=%s",
                    sandbox_id,
                    exc,
                )
                await sandbox_realtime_service.enqueue(
                    connection,
                    {
                        "type": "error",
                        "code": "internal_error",
                        "message": "sandbox snapshot query failed",
                    },
                )
                continue

            speed = int(snapshot["config"].get("speed", 1))
            schedule = (
                sandbox_runtime.ensure_job(sandbox_id, speed)
                if snapshot["state"]
                else sandbox_runtime.schedule_metadata(sandbox_id, False, speed)
            )
            grouped = {point_id: [] for point_id in accepted}
            for row in rows:
                grouped[row["point_id"]].append({
                    "tick": row["tick"], "value": row["value"]
                })
            queued = await sandbox_realtime_service.enqueue(
                connection,
                {
                    "type": "snapshot",
                    "subscription_version": generation,
                    "sandbox": snapshot,
                    "point_ids": accepted,
                    "rejected_point_ids": rejected,
                    "series": [
                        {"point_id": point_id, "measurements": grouped[point_id]}
                        for point_id in accepted
                    ],
                    "active_faults": active_faults,
                    **schedule,
                },
                generation,
            )
            if queued:
                await sandbox_realtime_service.activate_subscription(
                    connection, generation, int(snapshot["tick"])
                )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception(
            "沙盒 WebSocket 接收异常 sandbox_id=%s error=%s", sandbox_id, exc
        )
    finally:
        await sandbox_realtime_service.unregister(connection)
