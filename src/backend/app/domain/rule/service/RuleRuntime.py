from __future__ import annotations

import copy
import math
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select

from app.common.validators import ValidationError
from app.core.middleware.LogRecorder import get_logger
from app.core.utils.UUIDGenerator import uuid_generator
from app.domain.collector.event import MeasurementBatchEvent
from app.domain.collector.event_bus import collection_event_bus
from app.domain.rule.repository.models import ActionTask, Rule, RuleEvent
from app.domain.channel.repository.models.Control import Control
from app.domain.rule.schema import RuleConfig
from app.infra.DB.SQLConnection import sql_manager
from app.infra.RDF import asset_rdf_runtime
from app.infra.Email import smtp_client
from .ActionWorker import action_worker
from .RuleEngine import RuleDecision, RuleEngine
from .RuleRDFService import rule_rdf_service

logger = get_logger(__name__)


@dataclass
class CompiledRule:
    config: RuleConfig
    fingerprint: str
    engines: dict[str, RuleEngine]


class RuleRuntime:
    def __init__(self) -> None:
        self._engines: dict[str, CompiledRule] = {}
        self._point_index: dict[str, set[str]] = {}
        self._lock = threading.RLock()
        self._subscription = None
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        action_worker.start()
        with sql_manager.get_db("main") as db:
            rows = db.scalars(
                select(Rule).where(Rule.status.in_(("running", "compile_failed")))
            ).all()
            candidates = [(row.rule_id, row.status) for row in rows]
        for rule_id, previous_status in candidates:
            try:
                self.load_rule(rule_id, restore=previous_status == "running")
                with sql_manager.get_db("main") as db:
                    row = db.get(Rule, rule_id)
                    if row:
                        row.status = "running"
                        row.error = None
            except Exception as exc:
                logger.exception("规则启动编译失败 rule_id=%s error=%s", rule_id, exc)
                with sql_manager.get_db("main") as db:
                    row = db.get(Rule, rule_id)
                    if row:
                        row.status = "compile_failed"
                        row.error = str(exc)
        self._subscription = collection_event_bus.subscribe(
            MeasurementBatchEvent, self.consume, critical=False, priority=100
        )
        asset_rdf_runtime.subscribe_rebuilt(self._on_assets_rebuilt)
        self._started = True

    def shutdown(self) -> None:
        if self._subscription:
            collection_event_bus.unsubscribe(self._subscription)
            self._subscription = None
        asset_rdf_runtime.unsubscribe_rebuilt(self._on_assets_rebuilt)
        with self._lock:
            self._engines.clear()
            self._point_index.clear()
        action_worker.shutdown()
        self._started = False

    @staticmethod
    def _resolve_bindings(config) -> dict[str, dict]:
        selector = config.selector
        if selector.type == "PointIdSelector":
            metadata = asset_rdf_runtime.describe_sensor_point(selector.point_id)
            if metadata is None:
                raise ValidationError("rule point not found or asset is disabled")
            return {selector.point_id: metadata}

        location = asset_rdf_runtime.describe_asset(selector.location_id)
        if location is None:
            raise ValidationError("semantic selector location not found")
        if location["asset_type"] != selector.location_type:
            raise ValidationError("semantic selector location type does not match asset")
        if not asset_rdf_runtime.point_definition_exists(selector.point_definition_id):
            raise ValidationError("semantic selector point definition not found")
        point_ids = asset_rdf_runtime.resolve_sensor_point_ids(
            selector.location_id,
            selector.point_definition_id,
            include_descendants=True,
            include_disabled=False,
        )
        bindings = {}
        for point_id in point_ids:
            metadata = asset_rdf_runtime.describe_sensor_point(point_id)
            if metadata is not None:
                bindings[point_id] = metadata
        if not bindings:
            raise ValidationError("semantic selector matched no enabled sensor points")
        return bindings

    @staticmethod
    def _restore_point_engines(rule_id: str, compiled: CompiledRule) -> None:
        pending = set(compiled.engines)
        if not pending:
            return
        with sql_manager.get_db("main") as db:
            events = db.scalars(
                select(RuleEvent).where(RuleEvent.rule_id == rule_id)
                .order_by(RuleEvent.event_time.desc(), RuleEvent.event_id.desc())
            ).all()
        for event in events:
            point_id = str((event.evidence or {}).get("point_id") or "")
            if point_id not in pending:
                continue
            compiled.engines[point_id].restore(
                event.evidence, event.event_type, event.event_time
            )
            pending.remove(point_id)
            if not pending:
                break

    def compile_rule(
        self, rule_id: str, file_name: str, *, restore: bool = True
    ) -> CompiledRule:
        config, fingerprint = rule_rdf_service.read(file_name, rule_id)
        self._validate_actions(config)
        bindings = self._resolve_bindings(config)
        compiled = CompiledRule(
            config=config,
            fingerprint=fingerprint,
            engines={
                point_id: RuleEngine(
                    config=config,
                    fingerprint=fingerprint,
                    metadata=metadata,
                )
                for point_id, metadata in bindings.items()
            },
        )
        if restore:
            self._restore_point_engines(rule_id, compiled)
        return compiled

    @staticmethod
    def _validate_actions(config: RuleConfig) -> None:
        if any(action.type == "EmailAction" for action in config.actions):
            smtp_client.validate_config()
        control_ids = {
            action.params.control_id
            for action in config.actions
            if action.type == "SensorControlAction"
        }
        if not control_ids:
            return
        with sql_manager.get_db("main") as db:
            existing = set(db.scalars(
                select(Control.control_id).where(Control.control_id.in_(control_ids))
            ).all())
        missing = sorted(control_ids - existing)
        if missing:
            raise ValidationError(f"control not found: {', '.join(missing)}")

    def load_rule(self, rule_id: str, *, restore: bool = True) -> CompiledRule:
        with sql_manager.get_db("main") as db:
            row = db.get(Rule, rule_id)
            if row is None:
                raise ValidationError("rule not found")
            file_name = row.rule_file_name
        compiled = self.compile_rule(rule_id, file_name, restore=restore)
        self.install_rule(rule_id, compiled)
        return compiled

    def _rebuild_point_index_locked(self) -> None:
        index: dict[str, set[str]] = {}
        for rule_id, compiled in self._engines.items():
            for point_id in compiled.engines:
                index.setdefault(point_id, set()).add(rule_id)
        self._point_index = index

    def install_rule(self, rule_id: str, engine: CompiledRule) -> None:
        """安装已经成功编译的对象，避免启用流程重复读取和编译 TTL。"""
        with self._lock:
            self._engines[rule_id] = engine
            self._rebuild_point_index_locked()

    def unload_rule(self, rule_id: str) -> None:
        with self._lock:
            self._engines.pop(rule_id, None)
            self._rebuild_point_index_locked()

    @staticmethod
    def _rebind_compiled(compiled: CompiledRule) -> CompiledRule:
        bindings = RuleRuntime._resolve_bindings(compiled.config)
        engines = {}
        for point_id, metadata in bindings.items():
            old = compiled.engines.get(point_id)
            if old is None:
                engines[point_id] = RuleEngine(
                    config=compiled.config,
                    fingerprint=compiled.fingerprint,
                    metadata=metadata,
                )
            else:
                preserved = copy.deepcopy(old)
                preserved.metadata = metadata
                engines[point_id] = preserved
        return CompiledRule(
            config=compiled.config,
            fingerprint=compiled.fingerprint,
            engines=engines,
        )

    def _on_assets_rebuilt(self, _revision: int) -> None:
        with sql_manager.get_db("main") as db:
            rows = db.scalars(
                select(Rule).where(Rule.status.in_(("running", "compile_failed")))
            ).all()
            candidates = [(row.rule_id, row.rule_file_name) for row in rows]
        for rule_id, file_name in candidates:
            try:
                with self._lock:
                    current = self._engines.get(rule_id)
                    if current is not None:
                        # 解析绑定、复制状态和替换反向索引必须与测量消费互斥，
                        # 否则重绑定可能覆盖刚刚完成的一次状态推进。
                        compiled = self._rebind_compiled(current)
                        self._engines[rule_id] = compiled
                        self._rebuild_point_index_locked()
                    else:
                        compiled = None
                if compiled is None:
                    compiled = self.compile_rule(
                        rule_id, file_name, restore=False
                    )
                    self.install_rule(rule_id, compiled)
                with sql_manager.get_db("main") as db:
                    row = db.get(Rule, rule_id)
                    if row:
                        row.status = "running"
                        row.error = None
            except Exception as exc:
                self.unload_rule(rule_id)
                try:
                    with sql_manager.get_db("main") as db:
                        row = db.get(Rule, rule_id)
                        if row:
                            row.status = "compile_failed"
                            row.error = str(exc)
                except Exception:
                    logger.exception("资产变更后的规则状态保存失败 rule_id=%s", rule_id)

    def consume(self, event: MeasurementBatchEvent) -> None:
        values = {item.point_id: item.value for item in event.measurements}
        with self._lock:
            candidates = [
                (rule_id, point_id, self._engines[rule_id].engines[point_id])
                for point_id in values
                for rule_id in sorted(self._point_index.get(point_id, ()))
                if rule_id in self._engines
                and point_id in self._engines[rule_id].engines
            ]
        for rule_id, point_id, original in candidates:
            working = copy.deepcopy(original)
            value = values[point_id]
            if isinstance(value, bool) or not math.isfinite(value):
                continue
            decision = working.process(event.occurred_at, value)
            try:
                if decision:
                    self._persist_decision(rule_id, working, decision, event.occurred_at, value)
                with self._lock:
                    compiled = self._engines.get(rule_id)
                    if compiled and compiled.engines.get(point_id) is original:
                        compiled.engines[point_id] = working
            except Exception:
                logger.exception("规则事件保存失败 rule_id=%s", rule_id)

    def _persist_decision(
        self, rule_id: str, engine: RuleEngine, decision: RuleDecision,
        measurement_time: datetime, value: float,
    ) -> None:
        evidence = {
            **engine.metadata,
            "value": value,
            "measurement_time": measurement_time.isoformat(),
            "condition": decision.evaluation,
            "reason": decision.reason,
            "rule_fingerprint": engine.fingerprint,
        }
        now = datetime.now(timezone.utc)
        event_id = uuid_generator.random()
        with sql_manager.get_db("main") as db:
            db.add(RuleEvent(
                event_id=event_id, rule_id=rule_id, event_type=decision.event_type,
                evidence=evidence, event_time=measurement_time,
            ))
            # ActionTask references the event created in this transaction.  The
            # models intentionally do not expose ORM relationships, so make the
            # database dependency order explicit before inserting tasks.
            db.flush()
            if decision.event_type == "triggered":
                for action in engine.config.actions:
                    db.add(ActionTask(
                        task_id=uuid_generator.random(), rule_id=rule_id, event_id=event_id,
                        action_id=action.action_id, action_type=action.type,
                        action_params={
                            **action.params.model_dump(),
                            "merge_window_seconds": engine.config.trigger_policy.merge_window_seconds,
                        },
                        is_executed=False, status="pending", created_at=now,
                    ))
        if decision.event_type == "triggered":
            action_worker.wake()


rule_runtime = RuleRuntime()
