from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.utils.UUIDGenerator import uuid_generator
from app.domain.rule.service.RuleEngine import RuleEngine
from app.domain.sandbox.repository.models import Sandbox, SandboxEvent, SandboxMeasurement
from .SandboxRuleService import SandboxRuleService


EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)


@dataclass
class RuntimeRule:
    rule_id: str
    point_id: str
    engine: RuleEngine


class SandboxRuleRuntime:
    def __init__(self) -> None:
        self._rules: dict[str, dict[str, RuntimeRule]] = {}
        self._lock = threading.RLock()

    @staticmethod
    def virtual_time(tick: int) -> datetime:
        return EPOCH + timedelta(seconds=tick * 30)

    def load(self, sandbox: Sandbox, db: Session) -> None:
        compiled: dict[str, RuntimeRule] = {}
        service = SandboxRuleService.rdf_service(sandbox.sandbox_id)
        for ref in sandbox.config.get("sandbox_rule", []):
            if not ref.get("state"):
                continue
            config, fingerprint = service.read(f"{ref['rule_id']}.ttl", ref["rule_id"])
            point_id = config.selector.point_id
            engine = RuleEngine(
                config=config,
                fingerprint=fingerprint,
                metadata={"sandbox_id": sandbox.sandbox_id, "point_id": point_id},
            )
            rows = db.execute(
                select(SandboxMeasurement.tick, SandboxMeasurement.value)
                .where(
                    SandboxMeasurement.sandbox_id == sandbox.sandbox_id,
                    SandboxMeasurement.point_id == point_id,
                    SandboxMeasurement.tick >= int(ref.get("effective_tick", 0)),
                    SandboxMeasurement.tick <= sandbox.tick,
                    SandboxMeasurement.value.is_not(None),
                )
                .order_by(SandboxMeasurement.tick.asc())
            )
            for tick, value in rows:
                engine.process(self.virtual_time(int(tick)), float(value))
            compiled[ref["rule_id"]] = RuntimeRule(
                ref["rule_id"], point_id, engine
            )
        with self._lock:
            self._rules[sandbox.sandbox_id] = compiled

    def unload(self, sandbox_id: str) -> None:
        with self._lock:
            self._rules.pop(sandbox_id, None)

    def process(
        self, sandbox: Sandbox, tick: int, measurements: list[dict], db: Session
    ) -> list[SandboxEvent]:
        values = {item["point_id"]: item["value"] for item in measurements}
        with self._lock:
            candidates = list(self._rules.get(sandbox.sandbox_id, {}).values())
        events: list[SandboxEvent] = []
        for runtime_rule in candidates:
            if runtime_rule.point_id not in values or values[runtime_rule.point_id] is None:
                continue
            original = runtime_rule.engine
            working = copy.deepcopy(original)
            value = float(values[runtime_rule.point_id])
            decision = working.process(self.virtual_time(tick), value)
            if decision:
                payload = {
                    "rule_id": runtime_rule.rule_id,
                    "rule_name": working.config.rule_name,
                    "point_id": runtime_rule.point_id,
                    "value": value,
                    "reason": decision.reason,
                    "condition": decision.evaluation,
                    "rule_fingerprint": working.fingerprint,
                }
                event = SandboxEvent(
                    event_id=uuid_generator.random(), sandbox_id=sandbox.sandbox_id,
                    tick=tick, event_type=f"rule_{decision.event_type}", payload=payload,
                )
                db.add(event)
                events.append(event)
                if decision.event_type == "triggered":
                    for action in working.config.actions:
                        action_event = SandboxEvent(
                            event_id=uuid_generator.random(), sandbox_id=sandbox.sandbox_id,
                            tick=tick, event_type="virtual_action",
                            payload={
                                **payload,
                                "action_id": action.action_id,
                                "action_type": action.type,
                                "action_params": action.params.model_dump(mode="json"),
                                "message": "沙盒模拟动作，未执行真实任务",
                            },
                        )
                        db.add(action_event)
                        events.append(action_event)
            with self._lock:
                current = self._rules.get(sandbox.sandbox_id, {}).get(runtime_rule.rule_id)
                if current is runtime_rule and current.engine is original:
                    current.engine = working
        return events


sandbox_rule_runtime = SandboxRuleRuntime()
