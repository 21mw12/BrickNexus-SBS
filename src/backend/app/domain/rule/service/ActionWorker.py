from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.middleware.LogRecorder import get_logger
from app.domain.channel.service.ControlService import ControlService
from app.domain.log.service import LogService
from app.domain.rule.repository.models import ActionTask, RuleEvent
from app.infra.DB.SQLConnection import sql_manager
from app.infra.Email import smtp_client

logger = get_logger(__name__)


@dataclass(frozen=True)
class ClaimedAction:
    task_ids: tuple[str, ...]
    action_type: str
    params: dict
    evidences: tuple[dict, ...]
    claim_error: str | None = None


class ActionWorker:
    """单线程、最多一次的规则动作执行器。"""

    UNKNOWN_OUTCOME_ERROR = "进程在动作执行期间中断，执行结果未知，任务不会自动重放"

    def __init__(self) -> None:
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.recover_interrupted()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="rule-action-worker", daemon=True)
        self._thread.start()

    def recover_interrupted(self) -> int:
        """外部动作可能已经完成，故遗留 executing 只能终结为失败，不能重发。"""
        now = datetime.now(timezone.utc)
        with sql_manager.get_db("main") as db:
            tasks = db.scalars(select(ActionTask).where(ActionTask.status == "executing")).all()
            for task in tasks:
                task.status = "failed"
                task.is_executed = True
                task.error = self.UNKNOWN_OUTCOME_ERROR
                task.completed_at = now
                db.add(task)
            return len(tasks)

    def wake(self) -> None:
        self._wake.set()

    def shutdown(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join()
        self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            handled = self.process_one()
            if not handled:
                self._wake.wait(timeout=1)
                self._wake.clear()

    @staticmethod
    def _format_time(value) -> str:
        """将证据时间格式化为动作内容需要的秒级展示文本。"""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if not isinstance(value, str) or not value:
            return ""
        try:
            parsed = datetime.fromisoformat(
                f"{value[:-1]}+00:00" if value.endswith("Z") else value
            )
        except ValueError:
            return value
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _render(template: str, evidence: dict) -> str:
        replacements = {
            "{{$.point_name}}": str(evidence.get("point_name", "")),
            "{{$.time}}": ActionWorker._format_time(evidence.get("measurement_time", "")),
            "{{$.value}}": str(evidence.get("value", "")),
        }
        for source, value in replacements.items():
            template = template.replace(source, value)
        return template

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    @staticmethod
    def _window(params: dict) -> float:
        try:
            return max(0.0, float(params.get("merge_window_seconds", 0)))
        except (TypeError, ValueError):
            return 0.0

    def _claim(self, now: datetime) -> ClaimedAction | None:
        """领取一个已到执行时间的动作；等待合并的邮件不会挡住其他任务。"""
        with sql_manager.get_db("main") as db:
            tasks = db.scalars(
                select(ActionTask)
                .where(ActionTask.status == "pending", ActionTask.is_executed.is_(False))
                .order_by(ActionTask.created_at, ActionTask.task_id)
            ).all()
            candidate = None
            for task in tasks:
                if task.action_type != "EmailAction":
                    candidate = task
                    break
                due_at = self._aware(task.created_at) + timedelta(seconds=self._window(task.action_params))
                if now >= due_at:
                    candidate = task
                    break
            if candidate is None:
                return None

            event = db.get(RuleEvent, candidate.event_id)
            claimed = [candidate]
            if candidate.action_type == "EmailAction" and event is not None:
                window = self._window(candidate.action_params)
                if window > 0:
                    deadline = self._aware(candidate.created_at) + timedelta(seconds=window)
                    fingerprint = (event.evidence or {}).get("rule_fingerprint")
                    email_snapshot = {
                        key: candidate.action_params.get(key)
                        for key in ("recipients", "subject", "content")
                    }
                    claimed = []
                    for task in tasks:
                        if (
                            task.action_type != "EmailAction"
                            or task.rule_id != candidate.rule_id
                            or task.action_id != candidate.action_id
                            or self._aware(task.created_at) > deadline
                        ):
                            continue
                        task_event = db.get(RuleEvent, task.event_id)
                        if task_event is None:
                            continue
                        if (task_event.evidence or {}).get("rule_fingerprint") != fingerprint:
                            continue
                        if any(task.action_params.get(key) != value for key, value in email_snapshot.items()):
                            continue
                        claimed.append(task)
                    claimed.sort(
                        key=lambda item: (
                            self._aware(db.get(RuleEvent, item.event_id).event_time), item.event_id
                        )
                    )

            evidences = []
            claim_error = None
            for task in claimed:
                task.status = "executing"
                task.error = None
                db.add(task)
                source = db.get(RuleEvent, task.event_id)
                if source is None:
                    claim_error = "source rule event not found"
                    evidences.append({})
                else:
                    evidences.append(dict(source.evidence or {}))
            return ClaimedAction(
                task_ids=tuple(task.task_id for task in claimed),
                action_type=candidate.action_type,
                params=dict(candidate.action_params or {}),
                evidences=tuple(evidences),
                claim_error=claim_error,
            )

    @staticmethod
    def _finish(task_ids: tuple[str, ...], status: str, error: str | None = None) -> None:
        with sql_manager.get_db("main") as db:
            now = datetime.now(timezone.utc)
            for task_id in task_ids:
                task = db.get(ActionTask, task_id)
                if task is None or task.status != "executing":
                    continue
                task.status = status
                task.is_executed = True
                task.error = error
                task.completed_at = now
                db.add(task)

    def _execute_log(self, claimed: ClaimedAction) -> tuple[str, str]:
        content = self._render(claimed.params["content"], claimed.evidences[0])
        level = claimed.params["level"]
        with sql_manager.get_db("main") as db:
            task = db.get(ActionTask, claimed.task_ids[0])
            if task is None or task.status != "executing":
                raise RuntimeError("claimed action task no longer exists")
            LogService.create(
                db, type="rule_action", level=level, operator="SYSTEM", content=content
            )
            task.status = "succeeded"
            task.is_executed = True
            task.completed_at = datetime.now(timezone.utc)
            task.error = None
            db.add(task)
        return level, content

    def _execute_external(self, claimed: ClaimedAction) -> None:
        if claimed.action_type == "EmailAction":
            content = "\n".join(
                self._render(claimed.params["content"], evidence)
                for evidence in claimed.evidences
            )
            smtp_client.send(
                list(claimed.params["recipients"]), claimed.params["subject"], content
            )
            return
        if claimed.action_type == "SensorControlAction":
            with sql_manager.get_db("main") as db:
                ControlService.execute(db, claimed.params["control_id"])
            return
        raise RuntimeError(f"unsupported action type: {claimed.action_type}")

    def process_one(self, now: datetime | None = None) -> bool:
        execution_time = now or datetime.now(timezone.utc)
        claimed = self._claim(self._aware(execution_time))
        if claimed is None:
            return False
        try:
            if claimed.claim_error:
                raise RuntimeError(claimed.claim_error)
            if claimed.action_type == "LogAction":
                level, content = self._execute_log(claimed)
                try:
                    getattr(logger, level.lower())(content)
                except Exception:
                    logger.exception("规则动作应用日志镜像失败 task_id=%s", claimed.task_ids[0])
            else:
                self._execute_external(claimed)
                self._finish(claimed.task_ids, "succeeded")
        except Exception as exc:
            logger.exception("规则动作执行失败 task_ids=%s error=%s", claimed.task_ids, exc)
            try:
                self._finish(claimed.task_ids, "failed", str(exc))
            except Exception:
                logger.exception("规则动作失败状态保存失败 task_ids=%s", claimed.task_ids)
        return True


action_worker = ActionWorker()
