from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from rdflib import Graph
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.core.config.ConfigLoader import config
from app.core.utils.UUIDGenerator import uuid_generator
from app.domain.log.service import LogService
from app.domain.channel.repository.models.Control import Control
from app.domain.common.PermissionChecker import check_asset_instance_permission
from app.domain.rule.repository.models import ActionTask, Rule, RuleEvent
from app.domain.rule.schema import EventQuery, RuleConfig, RuleQuery, TaskQuery
from app.infra.RDF import asset_rdf_runtime
from .RuleRDFService import rule_rdf_service
from .RuleRuntime import rule_runtime


class RuleService:
    @staticmethod
    def _day_bounds(value: date) -> tuple[datetime, datetime]:
        """Return one business-calendar day as a half-open UTC interval."""
        business_timezone = ZoneInfo(config.time.default_timezone)
        start = datetime.combine(value, time.min, tzinfo=business_timezone)
        return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)

    @staticmethod
    def _validate_point(config: RuleConfig) -> None:
        if asset_rdf_runtime.get_status().dirty:
            asset_rdf_runtime.rebuild_now()
        selector = config.selector
        if selector.type == "PointIdSelector":
            if asset_rdf_runtime.describe_sensor_point(selector.point_id) is None:
                raise ValidationError("rule point not found or asset is disabled")
            return
        location = asset_rdf_runtime.describe_asset(selector.location_id)
        if location is None:
            raise ValidationError("semantic selector location not found")
        if location["asset_type"] != selector.location_type:
            raise ValidationError("semantic selector location type does not match asset")
        if not asset_rdf_runtime.point_definition_exists(selector.point_definition_id):
            raise ValidationError("semantic selector point definition not found")

    @staticmethod
    def _validate_control_actions(config: RuleConfig, authorization: str, db: Session) -> None:
        for action in config.actions:
            if action.type != "SensorControlAction":
                continue
            control = db.get(Control, action.params.control_id)
            if control is None:
                raise ValidationError(f"control not found: {action.params.control_id}")
            if not check_asset_instance_permission(authorization, control.asset_id, "O", db):
                raise PermissionError(
                    f"no O permission for control asset: {control.asset_id}"
                )

    @staticmethod
    def _operation_log(db: Session, operator: str, operation: str, rule: Rule) -> None:
        LogService.create(
            db, type="rule_operation", level="INFO", operator=operator,
            content=f"规则{operation}: rule_id={rule.rule_id}, rule_name={rule.rule_name}",
        )

    @staticmethod
    def create(config: RuleConfig, authorization: str, db: Session) -> dict:
        config = rule_rdf_service.ensure_action_ids(config)
        RuleService._validate_point(config)
        RuleService._validate_control_actions(config, authorization, db)
        rule_id = uuid_generator.random()
        file_name = f"{rule_id}.ttl"
        data = rule_rdf_service.serialize(rule_id, config)
        # 再从待落盘内容解析，防止生成器和运行时读取约束不一致。
        rule_rdf_service.parse_graph(Graph().parse(data=data, format="turtle"), rule_id)
        operator = LogService.operator_from_token(authorization, db)
        path = rule_rdf_service.path(file_name)
        try:
            rule_rdf_service.write_atomic(file_name, data)
            row = Rule(
                rule_id=rule_id, rule_name=config.rule_name, rule_file_name=file_name,
                status="paused", error=None, created_at=datetime.now(timezone.utc),
            )
            db.add(row)
            RuleService._operation_log(db, operator, "新增", row)
            db.commit()
            return RuleService._rule_dict(row, config)
        except Exception:
            db.rollback()
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            raise

    @staticmethod
    def edit(rule_id: str, config: RuleConfig, authorization: str, db: Session) -> dict:
        row = db.get(Rule, rule_id)
        if row is None:
            raise ValidationError("rule not found")
        if row.status == "running":
            raise ValidationError("running rule cannot be edited")
        config = rule_rdf_service.ensure_action_ids(config)
        RuleService._validate_point(config)
        RuleService._validate_control_actions(config, authorization, db)
        data = rule_rdf_service.serialize(rule_id, config)
        rule_rdf_service.parse_graph(Graph().parse(data=data, format="turtle"), rule_id)
        path = rule_rdf_service.path(row.rule_file_name)
        old_data = path.read_bytes() if path.exists() else None
        operator = LogService.operator_from_token(authorization, db)
        try:
            rule_rdf_service.write_atomic(row.rule_file_name, data)
            row.rule_name = config.rule_name
            row.status = "paused"
            row.error = None
            db.add(row)
            RuleService._operation_log(db, operator, "编辑", row)
            db.commit()
            return RuleService._rule_dict(row, config)
        except Exception:
            db.rollback()
            if old_data is not None:
                rule_rdf_service.write_atomic(row.rule_file_name, old_data)
            raise

    @staticmethod
    def toggle(rule_id: str, authorization: str, db: Session) -> dict:
        row = db.get(Rule, rule_id)
        if row is None:
            raise ValidationError("rule not found")
        operator = LogService.operator_from_token(authorization, db)
        if row.status == "running":
            config = None
            try:
                config, _ = rule_rdf_service.read(row.rule_file_name, row.rule_id)
            except Exception:
                # 暂停必须能够解除一个文件已经损坏的运行对象；详情中可以
                # 暂时不返回 config，后续编辑可重新生成合法 TTL。
                pass
            rule_runtime.unload_rule(rule_id)
            try:
                row.status = "paused"
                row.error = None
                RuleService._operation_log(db, operator, "暂停", row)
                db.commit()
                return RuleService._rule_dict(row, config)
            except Exception:
                db.rollback()
                rule_runtime.load_rule(rule_id)
                raise
        row.status = "validating"
        row.error = None
        db.flush()
        try:
            engine = rule_runtime.compile_rule(rule_id, row.rule_file_name)
        except Exception as exc:
            row.status = "compile_failed"
            row.error = str(exc)
            db.add(row)
            db.commit()
            raise ValidationError(str(exc)) from exc
        row.status = "running"
        RuleService._operation_log(db, operator, "启动", row)
        db.commit()
        rule_runtime.install_rule(rule_id, engine)
        return RuleService._rule_dict(row, engine.config)

    @staticmethod
    def delete(rule_id: str, authorization: str, db: Session) -> bool:
        row = db.get(Rule, rule_id)
        if row is None:
            raise ValidationError("rule not found")
        if row.status == "running":
            raise ValidationError("running rule cannot be deleted")
        operator = LogService.operator_from_token(authorization, db)
        path = rule_rdf_service.path(row.rule_file_name)
        backup = path.with_name(f".{path.name}.{uuid_generator.random()}.deleting")
        moved = False
        try:
            if path.exists():
                os.replace(path, backup)
                moved = True
            RuleService._operation_log(db, operator, "删除", row)
            db.delete(row)
            db.commit()
        except Exception:
            db.rollback()
            if moved and backup.exists():
                os.replace(backup, path)
            raise
        # SQL 已经提交，规则和历史事件/任务已删除。此时清理补偿文件
        # 失败不能再伪装成事务失败并把规则文件恢复成孤儿文件。
        if moved:
            try:
                backup.unlink(missing_ok=True)
            except OSError:
                pass
        return True

    @staticmethod
    def find(rule_id: str, db: Session) -> dict:
        row = db.get(Rule, rule_id)
        if row is None:
            raise ValidationError("rule not found")
        config = None
        try:
            config, _ = rule_rdf_service.read(row.rule_file_name, row.rule_id)
        except Exception:
            if row.status != "compile_failed":
                raise
        result = RuleService._rule_dict(row, config)
        result["sensor_id"] = None
        if config is not None and config.selector.type == "PointIdSelector":
            metadata = asset_rdf_runtime.describe_sensor_point(
                config.selector.point_id,
                include_disabled=True,
            )
            if metadata is not None:
                result["sensor_id"] = metadata.get("sensor_id") or None
        return result

    @staticmethod
    def list_rules(db: Session, page: int, limit: int, filters: RuleQuery | None) -> dict:
        conditions = []
        if filters:
            if filters.status:
                conditions.append(Rule.status == filters.status)
            if filters.rule_name:
                conditions.append(Rule.rule_name.ilike(f"%{filters.rule_name}%"))
            if filters.create_at:
                start, end = RuleService._day_bounds(filters.create_at)
                conditions.extend((Rule.created_at >= start, Rule.created_at < end))
        stmt = select(Rule).where(*conditions).order_by(Rule.created_at.desc(), Rule.rule_id.desc())
        total = db.scalar(select(func.count()).select_from(Rule).where(*conditions)) or 0
        rows = db.scalars(stmt.offset((page - 1) * limit).limit(limit)).all()
        return {"total": total, "items": [RuleService._rule_list_dict(row) for row in rows]}

    @staticmethod
    def get_ttl(rule_id: str, db: Session) -> str:
        row = db.get(Rule, rule_id)
        if row is None:
            raise ValidationError("rule not found")
        expected_name = f"{rule_id}.ttl"
        if row.rule_file_name != expected_name:
            raise ValidationError("invalid rule file name")
        return rule_rdf_service.read_ttl(row.rule_file_name, rule_id).decode("utf-8")

    @staticmethod
    def list_events(db: Session, page: int, limit: int, filters: EventQuery) -> dict:
        conditions = []
        for field in ("rule_id", "event_type"):
            value = getattr(filters, field)
            if value:
                conditions.append(getattr(RuleEvent, field) == value)
        if filters.event_time:
            start, end = RuleService._day_bounds(filters.event_time)
            conditions.extend((RuleEvent.event_time >= start, RuleEvent.event_time < end))
        stmt = select(RuleEvent).where(*conditions).order_by(
            RuleEvent.event_time.desc(), RuleEvent.event_id.desc()
        )
        total = db.scalar(select(func.count()).select_from(RuleEvent).where(*conditions)) or 0
        rows = db.scalars(stmt.offset((page - 1) * limit).limit(limit)).all()
        return {"total": total, "items": [{
            "event_id": event.event_id,
            "rule_id": event.rule_id,
            "event_type": event.event_type,
            "evidence": event.evidence,
            "event_time": event.event_time,
        } for event in rows]}

    @staticmethod
    def list_tasks(db: Session, page: int, limit: int, filters: TaskQuery) -> dict:
        conditions = []
        for field in ("rule_id", "event_id", "action_type", "status"):
            value = getattr(filters, field)
            if value:
                conditions.append(getattr(ActionTask, field) == value)
        if filters.create_time:
            start, end = RuleService._day_bounds(filters.create_time)
            conditions.extend((ActionTask.created_at >= start, ActionTask.created_at < end))
        if filters.completed_time:
            start, end = RuleService._day_bounds(filters.completed_time)
            conditions.extend((ActionTask.completed_at >= start, ActionTask.completed_at < end))
        stmt = select(ActionTask).where(*conditions).order_by(
            ActionTask.created_at.desc(), ActionTask.task_id.desc()
        )
        total = db.scalar(select(func.count()).select_from(ActionTask).where(*conditions)) or 0
        rows = db.scalars(stmt.offset((page - 1) * limit).limit(limit)).all()
        return {"total": total, "items": [{
            "task_id": task.task_id,
            "rule_id": task.rule_id,
            "action_type": task.action_type,
            "is_executed": task.is_executed,
            "status": task.status,
            "error": task.error,
            "created_at": task.created_at,
            "completed_at": task.completed_at,
        } for task in rows]}

    @staticmethod
    def _rule_list_dict(row: Rule) -> dict:
        return {
            "rule_id": row.rule_id,
            "rule_name": row.rule_name,
            "status": row.status,
            "error": row.error,
            "created_at": row.created_at,
        }

    @staticmethod
    def _rule_dict(row: Rule, config: RuleConfig | None = None) -> dict:
        result = {
            "rule_id": row.rule_id, "rule_name": row.rule_name,
            "rule_file_name": row.rule_file_name, "status": row.status,
            "error": row.error, "created_at": row.created_at,
        }
        if config is not None:
            result["config"] = config.model_dump(mode="json")
        return result
