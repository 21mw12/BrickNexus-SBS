from datetime import date, datetime, timezone
from importlib import import_module

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from types import SimpleNamespace

from app.domain.log.repository.models import Log
from app.domain.log.service import LogService
from app.common.validators import ValidationError
from app.domain.rule.repository.models import ActionTask, Rule, RuleEvent
from app.domain.rule.schema import EventQuery, RuleConfig, RuleQuery, TaskQuery
from app.domain.rule.service.RuleRDFService import rule_rdf_service
from app.domain.rule.service.RuleRuntime import rule_runtime
from app.domain.rule.service.RuleService import RuleService
from app.infra.DB.SQLConnection import Base
from app.infra.RDF import asset_rdf_runtime

rule_service_module = import_module("app.domain.rule.service.RuleService")


def _config(name="高温告警"):
    return RuleConfig.model_validate({
        "rule_name": name,
        "description": "单测点规则",
        "selector": {"selector_id": "monitor", "type": "PointIdSelector", "point_id": "p1"},
        "condition": {
            "type": "Comparison", "operator": "GreaterThan",
            "left": {"type": "PointValue", "selector_id": "monitor"},
            "right": {"type": "ConstantValue", "value": 40},
        },
        "actions": [{"type": "LogAction", "params": {"level": "WARNING", "content": "{{$.value}}"}}],
    })


def _semantic_config(name="楼层高温告警"):
    data = _config(name).model_dump(mode="json")
    data["selector"] = {
        "selector_id": "monitor",
        "type": "SemanticPointSelector",
        "point_definition_id": "global-temp-c",
        "location_id": "floor-3",
        "location_type": "floor",
    }
    return RuleConfig.model_validate(data)


def _control_config():
    data = _config().model_dump(mode="json")
    data["actions"] = [{
        "type": "SensorControlAction", "params": {"control_id": "control-1"},
    }]
    return RuleConfig.model_validate(data)


def _database(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'service.db'}")
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(
        engine,
        tables=[Rule.__table__, RuleEvent.__table__, ActionTask.__table__, Log.__table__],
    )
    return engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def test_rule_crud_toggle_and_operation_log_snapshot(monkeypatch, tmp_path):
    engine, factory = _database(tmp_path)
    monkeypatch.setattr(rule_rdf_service, "rule_dir", tmp_path / "rdf" / "rule")
    monkeypatch.setattr(RuleService, "_validate_point", staticmethod(lambda _config: None))
    monkeypatch.setattr(
        asset_rdf_runtime,
        "describe_sensor_point",
        lambda point_id, **_kwargs: {"point_id": point_id, "sensor_id": "sensor-001"},
    )
    monkeypatch.setattr(LogService, "operator_from_token", staticmethod(lambda _authorization, _db: "张三"))
    compiled = SimpleNamespace(config=_config("高温告警-已编辑"))
    installed = []
    unloaded = []
    monkeypatch.setattr(rule_runtime, "compile_rule", lambda _rule_id, _file_name: compiled)
    monkeypatch.setattr(rule_runtime, "install_rule", lambda rule_id, engine: installed.append((rule_id, engine)))
    monkeypatch.setattr(rule_runtime, "unload_rule", lambda rule_id: unloaded.append(rule_id))

    with factory() as db:
        created = RuleService.create(_config(), "Bearer token", db)
        rule_id = created["rule_id"]
        action_id = created["config"]["actions"][0]["action_id"]
        assert created["status"] == "paused"
        assert rule_rdf_service.path(f"{rule_id}.ttl").exists()
        details = RuleService.find(rule_id, db)
        assert details["sensor_id"] == "sensor-001"
        assert "sensor_id" not in details["config"]["selector"]
        ttl = RuleService.get_ttl(rule_id, db)
        assert "configJson" in ttl

        edited_data = _config("高温告警-已编辑").model_dump(mode="json")
        edited_data["actions"][0]["action_id"] = action_id
        edited = RuleService.edit(rule_id, RuleConfig.model_validate(edited_data), "Bearer token", db)
        assert edited["rule_name"] == "高温告警-已编辑"
        assert edited["config"]["actions"][0]["action_id"] == action_id

        running = RuleService.toggle(rule_id, "Bearer token", db)
        assert running["status"] == "running"
        assert installed == [(rule_id, compiled)]
        paused = RuleService.toggle(rule_id, "Bearer token", db)
        assert paused["status"] == "paused"
        assert unloaded == [rule_id]

        assert RuleService.delete(rule_id, "Bearer token", db) is True
        assert not rule_rdf_service.path(f"{rule_id}.ttl").exists()
        assert db.get(Rule, rule_id) is None
        assert db.scalar(select(func.count()).select_from(Log)) == 5
        logs = db.scalars(select(Log).order_by(Log.time)).all()
        assert {item.operator for item in logs} == {"张三"}
        assert all(item.type == "rule_operation" and item.level == "INFO" for item in logs)

    engine.dispose()


def test_rule_list_filters_name_and_creation_day_and_hides_detail_fields(tmp_path):
    engine, factory = _database(tmp_path)
    now = datetime(2026, 8, 18, 4, tzinfo=timezone.utc)
    with factory() as db:
        db.add_all([
            Rule(rule_id="contains-needle", rule_name="普通规则", rule_file_name="a.ttl", status="paused", created_at=now),
            Rule(rule_id="r2", rule_name="高温 needle 告警", rule_file_name="b.ttl", status="paused", created_at=now),
        ])
        db.commit()
        result = RuleService.list_rules(db, 1, 20, RuleQuery(rule_name="needle"))
        assert result["total"] == 1
        assert result["items"][0]["rule_id"] == "r2"
        assert set(result["items"][0]) == {
            "rule_id", "rule_name", "status", "error", "created_at",
        }
        by_day = RuleService.list_rules(db, 1, 20, RuleQuery(create_at=date(2026, 8, 18)))
        assert by_day["total"] == 2
    engine.dispose()


def test_control_action_configuration_requires_existing_control_and_sensor_o_permission(monkeypatch):
    db = SimpleNamespace(get=lambda _model, control_id: (
        SimpleNamespace(control_id=control_id, asset_type="terminal", asset_id="terminal-1")
        if control_id == "control-1" else None
    ))
    monkeypatch.setattr(rule_service_module, "check_asset_instance_permission", lambda *_args: False)
    with pytest.raises(PermissionError, match="no O permission"):
        RuleService._validate_control_actions(_control_config(), "Bearer token", db)
    monkeypatch.setattr(rule_service_module, "check_asset_instance_permission", lambda *_args: True)
    RuleService._validate_control_actions(_control_config(), "Bearer token", db)

    missing = SimpleNamespace(get=lambda *_args: None)
    with pytest.raises(ValidationError, match="control not found"):
        RuleService._validate_control_actions(_control_config(), "Bearer token", missing)


def test_event_and_task_lists_keep_columns_and_use_documented_day_filters(tmp_path):
    engine, factory = _database(tmp_path)
    now = datetime(2026, 8, 18, 4, tzinfo=timezone.utc)
    with factory() as db:
        db.add(Rule(
            rule_id="r-source", rule_name="三楼高温规则", rule_file_name="source.ttl",
            status="running", created_at=now,
        ))
        db.add_all([
            RuleEvent(
                event_id="e-match", rule_id="r-source", event_type="triggered",
                evidence={"point_name": "会议室温度"}, event_time=now,
            ),
            RuleEvent(
                event_id="e-other", rule_id="r-source", event_type="recovered",
                evidence={"point_name": "走廊温度"}, event_time=now,
            ),
        ])
        db.flush()
        db.add_all([
            ActionTask(
                task_id="t-match", rule_id="r-source", event_id="e-match", action_id="a1",
                action_type="LogAction", action_params={}, is_executed=True,
                status="succeeded", error=None, created_at=now, completed_at=now,
            ),
            ActionTask(
                task_id="t-other", rule_id="r-source", event_id="e-other", action_id="a2",
                action_type="LogAction", action_params={}, is_executed=False,
                status="pending", error=None, created_at=now, completed_at=None,
            ),
        ])
        db.commit()

        events = RuleService.list_events(
            db, 1, 20,
            EventQuery(rule_id="r-source", event_type="triggered", event_time=date(2026, 8, 18)),
        )
        assert events["total"] == 1
        assert set(events["items"][0]) == {
            "event_id", "rule_id", "event_type", "evidence", "event_time",
        }

        tasks = RuleService.list_tasks(db, 1, 20, TaskQuery(event_id="e-match"))
        assert tasks["total"] == 1
        assert tasks["items"][0]["task_id"] == "t-match"
        assert set(tasks["items"][0]) == {
            "task_id", "rule_id", "action_type", "is_executed",
            "status", "error", "created_at", "completed_at",
        }

        created_tasks = RuleService.list_tasks(
            db, 1, 20, TaskQuery(rule_id="r-source", create_time=date(2026, 8, 18)),
        )
        assert created_tasks["total"] == 2
        completed_tasks = RuleService.list_tasks(
            db, 1, 20, TaskQuery(completed_time=date(2026, 8, 18)),
        )
        assert [item["task_id"] for item in completed_tasks["items"]] == ["t-match"]
    engine.dispose()


def test_rule_calendar_day_uses_configured_business_timezone():
    start, end = RuleService._day_bounds(date(2026, 8, 18))
    assert start == datetime(2026, 8, 17, 16, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 18, 16, tzinfo=timezone.utc)


def test_semantic_selector_validation_allows_zero_instances_and_find_has_no_sensor(monkeypatch, tmp_path):
    engine, factory = _database(tmp_path)
    monkeypatch.setattr(rule_rdf_service, "rule_dir", tmp_path / "rdf" / "rule")
    monkeypatch.setattr(asset_rdf_runtime, "get_status", lambda: SimpleNamespace(dirty=False))
    monkeypatch.setattr(
        asset_rdf_runtime,
        "describe_asset",
        lambda asset_id: {
            "asset_id": asset_id, "asset_type": "floor", "name": "三层", "is_enabled": True,
        },
    )
    monkeypatch.setattr(asset_rdf_runtime, "point_definition_exists", lambda point_id: point_id == "global-temp-c")
    monkeypatch.setattr(LogService, "operator_from_token", staticmethod(lambda _authorization, _db: "张三"))

    with factory() as db:
        created = RuleService.create(_semantic_config(), "Bearer token", db)
        details = RuleService.find(created["rule_id"], db)
        assert details["sensor_id"] is None
        assert details["config"]["selector"]["type"] == "SemanticPointSelector"
        monkeypatch.setattr(
            rule_runtime,
            "compile_rule",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                ValidationError("semantic selector matched no enabled sensor points")
            ),
        )
        with pytest.raises(ValidationError, match="matched no enabled sensor points"):
            RuleService.toggle(created["rule_id"], "Bearer token", db)
        failed = db.get(Rule, created["rule_id"])
        assert failed.status == "compile_failed"
        assert "matched no enabled" in failed.error
    engine.dispose()
