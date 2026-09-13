from __future__ import annotations

import copy
import random
import threading

from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.core.utils.UUIDGenerator import uuid_generator
from app.domain.sandbox.repository import SandboxEventRepository
from app.domain.sandbox.repository.models import Sandbox, SandboxEvent, SandboxMeasurement
from app.domain.sandbox.schema import SandboxFaultSchema
from .SandboxDataService import sandbox_point_ids


class SandboxFaultRuntime:
    def __init__(self) -> None:
        self._active: dict[str, dict[str, dict]] = {}
        self._lock = threading.RLock()

    def restore(self, sandbox: Sandbox, db: Session) -> None:
        active: dict[str, dict] = {}
        for event in SandboxEventRepository.all_fault_events(sandbox.sandbox_id, db):
            if event.event_type == "fault_started":
                active[event.event_id] = copy.deepcopy(event.payload)
            else:
                active.pop(str(event.payload.get("fault_event_id") or ""), None)
        active = {
            event_id: payload
            for event_id, payload in active.items()
            if payload.get("end_tick") is None or payload["end_tick"] >= sandbox.tick
        }
        with self._lock:
            self._active[sandbox.sandbox_id] = active

    def inject(
        self, sandbox_id: str, data: SandboxFaultSchema, db: Session
    ) -> SandboxEvent:
        sandbox = db.get(Sandbox, sandbox_id)
        if sandbox is None:
            raise ValidationError("sandbox not found")
        if not sandbox.state:
            raise ValidationError("sandbox must be running to inject fault")
        if data.point_id not in sandbox_point_ids(sandbox.config):
            raise ValidationError("point does not belong to sandbox")
        start_tick = sandbox.tick + 1
        end_tick = (
            None
            if data.duration_ticks is None
            else start_tick + data.duration_ticks - 1
        )
        parameters = dict(data.parameters)
        if data.fault_type == "stuck":
            latest = db.query(SandboxMeasurement).filter(
                SandboxMeasurement.sandbox_id == sandbox_id,
                SandboxMeasurement.point_id == data.point_id,
                SandboxMeasurement.value.is_not(None),
            ).order_by(SandboxMeasurement.tick.desc()).first()
            if latest is None:
                for terminal in sandbox.config.get("terminals", []):
                    for sensor in terminal.get("sensors", []):
                        for point in sensor.get("points", []):
                            if point.get("id") == data.point_id:
                                parameters["value"] = float(point["base_value"])
            else:
                parameters["value"] = float(latest.value)
        payload = {
            "fault_type": data.fault_type,
            "point_id": data.point_id,
            "start_tick": start_tick,
            "end_tick": end_tick,
            "parameters": parameters,
        }
        event = SandboxEvent(
            event_id=uuid_generator.random(),
            sandbox_id=sandbox_id,
            tick=sandbox.tick,
            event_type="fault_started",
            payload=payload,
        )
        db.add(event)
        db.flush()
        with self._lock:
            self._active.setdefault(sandbox_id, {})[event.event_id] = copy.deepcopy(payload)
        return event

    def stop(
        self, sandbox_id: str, fault_event_id: str, tick: int, db: Session,
        reason: str = "manual",
    ) -> SandboxEvent:
        with self._lock:
            active = self._active.setdefault(sandbox_id, {})
            if fault_event_id not in active:
                raise ValidationError("active fault not found")
            active.pop(fault_event_id)
        event = SandboxEvent(
            event_id=uuid_generator.random(), sandbox_id=sandbox_id, tick=tick,
            event_type="fault_stopped",
            payload={"fault_event_id": fault_event_id, "reason": reason},
        )
        db.add(event)
        db.flush()
        return event

    def expire(self, sandbox_id: str, tick: int, db: Session) -> list[SandboxEvent]:
        with self._lock:
            expired = [
                event_id
                for event_id, payload in self._active.get(sandbox_id, {}).items()
                if payload.get("end_tick") is not None and payload["end_tick"] < tick
            ]
        return [self.stop(sandbox_id, event_id, tick, db, "duration") for event_id in expired]

    def active(self, sandbox_id: str, tick: int | None = None) -> list[dict]:
        with self._lock:
            rows = copy.deepcopy(self._active.get(sandbox_id, {}))
        return [
            {"event_id": event_id, **payload}
            for event_id, payload in rows.items()
            if tick is None or payload["start_tick"] <= tick
        ]

    def noise(self, sandbox_id: str, point_id: str, tick: int, default: float) -> float:
        result = default
        for fault in self.active(sandbox_id, tick):
            if fault["point_id"] == point_id and fault["fault_type"] == "noise":
                result = float(fault["parameters"]["noise"])
        return result

    def apply(self, sandbox_id: str, point_id: str, tick: int, value: float) -> float:
        faults = sorted(self.active(sandbox_id, tick), key=lambda item: (item["start_tick"], item["event_id"]))
        for fault in faults:
            if fault["point_id"] != point_id:
                continue
            kind = fault["fault_type"]
            params = fault["parameters"]
            if kind == "offset":
                value += float(params["offset"])
            elif kind == "drift":
                value += float(params["offset_per_tick"]) * (tick - fault["start_tick"])
            elif kind == "spike":
                if params.get("mode", "set") == "add":
                    value += float(params["value"])
                else:
                    value = float(params["value"])
            elif kind == "stuck":
                value = float(params["value"])
        return value

    def clear(self, sandbox_id: str) -> None:
        with self._lock:
            self._active.pop(sandbox_id, None)


sandbox_fault_runtime = SandboxFaultRuntime()
