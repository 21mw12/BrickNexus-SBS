from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.common.validators import ValidationError
from app.core.middleware.LogRecorder import get_logger
from app.infra.DB.SQLConnection import sql_manager
from app.infra.Scheduler.SchedulerManager import SchedulerManager, scheduler
from app.domain.sandbox.repository import SandboxMeasurementRepository, SandboxRepository
from app.domain.sandbox.repository.models import Sandbox
from app.domain.sandbox.schema import SandboxConfig
from .SandboxFaultRuntime import SandboxFaultRuntime, sandbox_fault_runtime
from .SandboxGenerator import SandboxGenerator, sandbox_generator
from .SandboxRealtimeService import SandboxRealtimeService, sandbox_realtime_service
from .SandboxRuleRuntime import SandboxRuleRuntime, sandbox_rule_runtime


logger = get_logger(__name__)


class SandboxRuntime:
    def __init__(
        self,
        scheduler_manager: SchedulerManager = scheduler,
        generator: SandboxGenerator = sandbox_generator,
        fault_runtime: SandboxFaultRuntime = sandbox_fault_runtime,
        rule_runtime: SandboxRuleRuntime = sandbox_rule_runtime,
        realtime: SandboxRealtimeService = sandbox_realtime_service,
    ) -> None:
        self.scheduler = scheduler_manager
        self.generator = generator
        self.fault_runtime = fault_runtime
        self.rule_runtime = rule_runtime
        self.realtime = realtime
        self.measurements = SandboxMeasurementRepository()
        self._jobs: set[str] = set()
        self._started = False

    @staticmethod
    def task_id(sandbox_id: str) -> str:
        return f"sandbox:{sandbox_id}"

    @staticmethod
    def interval_seconds(speed: int) -> float:
        return 30 / speed

    def _install_job(self, sandbox_id: str, speed: int) -> None:
        async def scheduled_advance():
            try:
                await self.advance(sandbox_id)
            except Exception as exc:
                logger.exception(
                    "沙盒 tick 执行失败 sandbox_id=%s error=%s",
                    sandbox_id,
                    exc,
                )
                await self.realtime.publish(
                    sandbox_id,
                    {
                        "type": "error",
                        "code": "tick_failed",
                        "message": "沙盒 tick 执行失败，请查看服务端日志",
                        **self.schedule_metadata(sandbox_id, True, speed),
                    },
                )

        task_id = self.task_id(sandbox_id)
        interval = self.interval_seconds(speed)
        self.scheduler.add_task(
            task_id,
            scheduled_advance,
            interval,
            initial_delay_seconds=interval,
        )
        self._jobs.add(task_id)

    @staticmethod
    def _utc_iso(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def schedule_metadata(
        self,
        sandbox_id: str,
        running: bool,
        speed: int,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        job = self.scheduler.get_job(self.task_id(sandbox_id)) if running else None
        next_run = getattr(job, "next_run_time", None) if job is not None else None
        return {
            "server_time": self._utc_iso(now),
            "next_tick_at": self._utc_iso(next_run) if next_run is not None else None,
            "tick_interval_seconds": self.interval_seconds(speed),
        }

    def ensure_job(self, sandbox_id: str, speed: int) -> dict[str, Any]:
        """Repair a missing scheduler job for a database row marked as running."""
        if self.scheduler.get_job(self.task_id(sandbox_id)) is None:
            logger.warning("运行中的沙盒缺少调度任务，正在恢复 sandbox_id=%s", sandbox_id)
            self._install_job(sandbox_id, speed)
        return self.schedule_metadata(sandbox_id, True, speed)

    def start(self) -> None:
        if self._started:
            return
        with sql_manager.get_db("main") as db:
            rows = list(db.scalars(select(Sandbox).where(Sandbox.state.is_(True))).all())
            for row in rows:
                try:
                    self.fault_runtime.restore(row, db)
                    self.rule_runtime.load(row, db)
                    self._install_job(row.sandbox_id, int(row.config.get("speed", 1)))
                except Exception:
                    logger.exception("沙盒运行状态恢复失败 sandbox_id=%s", row.sandbox_id)
        self._started = True

    async def shutdown(self) -> None:
        for task_id in tuple(self._jobs):
            self.scheduler.remove_task(task_id)
        self._jobs.clear()
        self._started = False

    async def toggle(self, sandbox_id: str) -> dict:
        with sql_manager.get_db("main") as db:
            row = SandboxRepository.get_for_update(sandbox_id, db)
            if row is None:
                raise ValidationError("sandbox not found")
            row.state = not row.state
            new_state = row.state
            config = dict(row.config)
            tick = row.tick
            speed = int(config.get("speed", 1))
        if new_state:
            with sql_manager.get_db("main") as db:
                row = db.get(Sandbox, sandbox_id)
                self.fault_runtime.restore(row, db)
                self.rule_runtime.load(row, db)
            self._install_job(sandbox_id, speed)
        else:
            task_id = self.task_id(sandbox_id)
            self.scheduler.remove_task(task_id)
            self._jobs.discard(task_id)
            self.rule_runtime.unload(sandbox_id)
        result = {
            "sandbox_id": sandbox_id,
            "state": new_state,
            "tick": tick,
            **self.schedule_metadata(sandbox_id, new_state, speed),
        }
        await self.realtime.publish(sandbox_id, {"type": "sandbox_state", **result})
        return result

    async def pause(self, sandbox_id: str) -> dict:
        """Idempotently stop a sandbox when its workspace is left."""
        with sql_manager.get_db("main") as db:
            row = SandboxRepository.get_for_update(sandbox_id, db)
            if row is None:
                raise ValidationError("sandbox not found")
            row.state = False
            tick = row.tick
            speed = int(row.config.get("speed", 1))
        task_id = self.task_id(sandbox_id)
        self.scheduler.remove_task(task_id)
        self._jobs.discard(task_id)
        self.rule_runtime.unload(sandbox_id)
        result = {
            "sandbox_id": sandbox_id,
            "state": False,
            "tick": tick,
            **self.schedule_metadata(sandbox_id, False, speed),
        }
        await self.realtime.publish(sandbox_id, {"type": "sandbox_state", **result})
        return result

    async def set_speed(self, sandbox_id: str, speed: int) -> dict:
        with sql_manager.get_db("main") as db:
            row = SandboxRepository.get_for_update(sandbox_id, db)
            if row is None:
                raise ValidationError("sandbox not found")
            config = dict(row.config)
            config["speed"] = speed
            row.config = SandboxConfig.model_validate(config).model_dump(mode="json")
            running = row.state
            tick = row.tick
        if running:
            self._install_job(sandbox_id, speed)
        result = {
            "sandbox_id": sandbox_id, "speed": speed, "tick": tick,
            **self.schedule_metadata(sandbox_id, running, speed),
        }
        await self.realtime.publish(sandbox_id, {"type": "sandbox_speed", **result})
        return result

    async def remove(self, sandbox_id: str) -> None:
        task_id = self.task_id(sandbox_id)
        self.scheduler.remove_task(task_id)
        self._jobs.discard(task_id)
        self.rule_runtime.unload(sandbox_id)
        self.fault_runtime.clear(sandbox_id)

    async def advance(self, sandbox_id: str) -> None:
        result = await asyncio.to_thread(self._advance_sync, sandbox_id)
        if result is not None:
            events = result.pop("events", [])
            result.update(
                self.schedule_metadata(
                    sandbox_id,
                    True,
                    int(result.pop("speed")),
                )
            )
            await self.realtime.publish(sandbox_id, result)
            for event in events:
                message_type = (
                    "fault_event"
                    if event["event_type"].startswith("fault_")
                    else "rule_event"
                )
                await self.realtime.publish(
                    sandbox_id, {"type": message_type, "event": event}
                )

    def _advance_sync(self, sandbox_id: str) -> dict | None:
        with sql_manager.get_db("main") as db:
            row = SandboxRepository.get_for_update(sandbox_id, db)
            if row is None or not row.state:
                return None
            row.tick += 1
            expired = self.fault_runtime.expire(sandbox_id, row.tick, db)
            measurements = self.generator.generate(
                sandbox_id, row.config, row.tick
            )
            self.measurements.upsert_many(measurements, db)
            rule_events = self.rule_runtime.process(row, row.tick, measurements, db)
            db.flush()
            events = [*expired, *rule_events]
            return {
                "type": "tick",
                "sandbox_id": sandbox_id,
                "tick": row.tick,
                "speed": int(row.config.get("speed", 1)),
                "measurements": measurements,
                "events": [
                    {
                        "event_id": event.event_id,
                        "tick": event.tick,
                        "event_type": event.event_type,
                        "payload": event.payload,
                    }
                    for event in events
                ],
            }


sandbox_runtime = SandboxRuntime()
