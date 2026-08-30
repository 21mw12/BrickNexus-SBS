from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.domain.rule.repository.models import ActionTask, Rule, RuleEvent
from app.domain.rule.schema import RuleConfig
from app.domain.rule.service.RuleEngine import RuleDecision, RuleEngine
from app.domain.collector.event import MeasurementBatchEvent, MeasurementValue
from app.domain.rule.service.RuleRuntime import CompiledRule, RuleRuntime, action_worker, smtp_client
from app.domain.rule.service.RuleRDFService import rule_rdf_service
from app.common.validators import ValidationError
from app.infra.RDF import asset_rdf_runtime
from app.infra.DB.SQLConnection import Base, sql_manager


def test_trigger_event_and_same_type_actions_are_persisted_atomically(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'runtime.db'}")
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine, tables=[Rule.__table__, RuleEvent.__table__, ActionTask.__table__])
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setitem(sql_manager.sessions, "main", factory)
    wake_calls = []
    monkeypatch.setattr(action_worker, "wake", lambda: wake_calls.append(True))

    config = RuleConfig.model_validate({
        "rule_name": "two logs", "description": "",
        "selector": {"selector_id": "monitor", "type": "PointIdSelector", "point_id": "p1"},
        "condition": {
            "type": "Comparison", "operator": "GreaterThan",
            "left": {"type": "PointValue", "selector_id": "monitor"},
            "right": {"type": "ConstantValue", "value": 40},
        },
        "trigger_policy": {"merge_window_seconds": 8},
        "actions": [
            {"action_id": "log-a", "type": "LogAction", "params": {"level": "WARNING", "content": "A"}},
            {"action_id": "log-b", "type": "LogAction", "params": {"level": "ERROR", "content": "B"}},
        ],
    })
    runtime = RuleRuntime()
    rule_engine = RuleEngine(config, "fingerprint", {"point_id": "p1", "point_name": "温度", "unit": "℃"})
    now = datetime.now(timezone.utc)
    with factory() as db:
        db.add(Rule(rule_id="r1", rule_name="two logs", rule_file_name="r1.ttl", status="running", created_at=now))
        db.commit()

    runtime._persist_decision(
        "r1", rule_engine,
        RuleDecision("triggered", "initial", {"result": True}),
        now, 42.0,
    )

    with factory() as db:
        source_event = db.scalar(select(RuleEvent))
        tasks = db.scalars(select(ActionTask).order_by(ActionTask.action_id)).all()
        assert source_event.evidence["rule_fingerprint"] == "fingerprint"
        assert source_event.evidence["value"] == 42.0
        assert [task.action_id for task in tasks] == ["log-a", "log-b"]
        assert {task.event_id for task in tasks} == {source_event.event_id}
        assert {task.action_params["merge_window_seconds"] for task in tasks} == {8.0}
        assert all(task.status == "pending" and not task.is_executed for task in tasks)
    assert wake_calls == [True]
    engine.dispose()


def test_email_rule_compile_validates_smtp_without_connecting(monkeypatch):
    data = _semantic_config().model_dump(mode="json")
    data["selector"] = {
        "selector_id": "monitor", "type": "PointIdSelector", "point_id": "p1",
    }
    data["actions"] = [{
        "action_id": "email-1", "type": "EmailAction",
        "params": {"recipients": ["ops@example.com"], "subject": "告警", "content": "正文"},
    }]
    config = RuleConfig.model_validate(data)
    monkeypatch.setattr(rule_rdf_service, "read", lambda *_args: (config, "fingerprint"))
    monkeypatch.setattr(
        smtp_client, "validate_config",
        lambda: (_ for _ in ()).throw(ValidationError("SMTP is disabled")),
    )
    with pytest.raises(ValidationError, match="SMTP is disabled"):
        RuleRuntime().compile_rule("r1", "r1.ttl")


def _semantic_config():
    return RuleConfig.model_validate({
        "rule_name": "三楼温度突变", "description": "",
        "selector": {
            "selector_id": "monitor", "type": "SemanticPointSelector",
            "point_definition_id": "global-temp-c",
            "location_id": "floor-3", "location_type": "floor",
        },
        "condition": {
            "type": "Comparison", "operator": "GreaterThan",
            "left": {"type": "PreviousDifference", "selector_id": "monitor"},
            "right": {"type": "ConstantValue", "value": 5},
        },
        "actions": [{
            "action_id": "log-1", "type": "LogAction",
            "params": {"level": "WARNING", "content": "{{$.point_name}}={{$.value}}"},
        }],
    })


def _batch(when, **values):
    return MeasurementBatchEvent(
        request_id="request-1", request_type="http", occurred_at=when,
        terminal_ids=("terminal-1",), points=(),
        measurements=tuple(
            MeasurementValue(
                point_id=point_id,
                sensor_id=f"sensor-{point_id}",
                terminal_id="terminal-1",
                value=value,
            )
            for point_id, value in values.items()
        ),
        sensor_statuses=(),
    )


def test_semantic_rule_runs_independent_point_engines(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'semantic-runtime.db'}")
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine, tables=[Rule.__table__, RuleEvent.__table__, ActionTask.__table__])
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setitem(sql_manager.sessions, "main", factory)
    monkeypatch.setattr(action_worker, "wake", lambda: None)

    config = _semantic_config()
    compiled = CompiledRule(
        config=config,
        fingerprint="semantic-fingerprint",
        engines={
            point_id: RuleEngine(config, "semantic-fingerprint", {
                "point_id": point_id,
                "point_name": point_name,
                "sensor_id": sensor_id,
                "unit": "℃",
                "asset_path": [],
            })
            for point_id, point_name, sensor_id in (
                ("p1", "301温度", "s1"),
                ("p2", "302温度", "s2"),
            )
        },
    )
    runtime = RuleRuntime()
    runtime.install_rule("r-semantic", compiled)
    start = datetime(2026, 8, 21, 1, tzinfo=timezone.utc)
    with factory() as db:
        db.add(Rule(
            rule_id="r-semantic", rule_name=config.rule_name,
            rule_file_name="r-semantic.ttl", status="running", created_at=start,
        ))
        db.commit()

    runtime.consume(_batch(start, p1=10.0, p2=100.0))
    runtime.consume(_batch(start.replace(minute=1), p1=20.0, p2=101.0))
    with factory() as db:
        events = db.scalars(select(RuleEvent)).all()
        tasks = db.scalars(select(ActionTask)).all()
        assert [item.evidence["point_id"] for item in events] == ["p1"]
        assert events[0].evidence["point_name"] == "301温度"
        assert len(tasks) == 1

    runtime.consume(_batch(start.replace(minute=2), p2=110.0))
    with factory() as db:
        events = db.scalars(select(RuleEvent).order_by(RuleEvent.event_time)).all()
        assert [item.evidence["point_id"] for item in events] == ["p1", "p2"]
        assert len(db.scalars(select(ActionTask)).all()) == 2
    assert runtime._engines["r-semantic"].engines["p1"].phase == "Triggered"
    assert runtime._engines["r-semantic"].engines["p2"].phase == "Triggered"
    runtime.consume(_batch(start.replace(minute=3), p1=20.0))
    with factory() as db:
        events = db.scalars(select(RuleEvent).order_by(RuleEvent.event_time)).all()
        assert [(item.evidence["point_id"], item.event_type) for item in events] == [
            ("p1", "triggered"),
            ("p2", "triggered"),
            ("p1", "recovered"),
        ]
        assert len(db.scalars(select(ActionTask)).all()) == 2
    assert runtime._engines["r-semantic"].engines["p1"].phase == "Normal"
    assert runtime._engines["r-semantic"].engines["p2"].phase == "Triggered"
    engine.dispose()


def test_semantic_rule_creates_separate_events_for_same_batch(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'same-batch.db'}")
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(
        engine, tables=[Rule.__table__, RuleEvent.__table__, ActionTask.__table__]
    )
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setitem(sql_manager.sessions, "main", factory)
    monkeypatch.setattr(action_worker, "wake", lambda: None)

    data = _semantic_config().model_dump(mode="json")
    data["condition"]["left"] = {
        "type": "PointValue", "selector_id": "monitor",
    }
    data["condition"]["right"] = {"type": "ConstantValue", "value": 40}
    config = RuleConfig.model_validate(data)
    compiled = CompiledRule(
        config=config,
        fingerprint="same-batch-fingerprint",
        engines={
            point_id: RuleEngine(config, "same-batch-fingerprint", {
                "point_id": point_id,
                "point_name": point_name,
                "sensor_id": sensor_id,
                "unit": "℃",
                "asset_path": [],
            })
            for point_id, point_name, sensor_id in (
                ("p1", "301温度", "s1"),
                ("p2", "302温度", "s2"),
            )
        },
    )
    runtime = RuleRuntime()
    runtime.install_rule("r-semantic", compiled)
    now = datetime(2026, 8, 21, 1, tzinfo=timezone.utc)
    with factory() as db:
        db.add(Rule(
            rule_id="r-semantic", rule_name=config.rule_name,
            rule_file_name="r-semantic.ttl", status="running", created_at=now,
        ))
        db.commit()

    runtime.consume(_batch(now, p1=41.0, p2=42.0))

    with factory() as db:
        events = db.scalars(select(RuleEvent).order_by(RuleEvent.event_id)).all()
        tasks = db.scalars(select(ActionTask).order_by(ActionTask.task_id)).all()
        assert len(events) == 2
        assert {item.evidence["point_id"] for item in events} == {"p1", "p2"}
        assert {item.evidence["point_name"] for item in events} == {"301温度", "302温度"}
        assert len(tasks) == 2
        assert {item.event_id for item in tasks} == {item.event_id for item in events}
    engine.dispose()


def test_semantic_rebind_preserves_existing_state_and_starts_new_points_fresh(monkeypatch):
    config = _semantic_config()
    existing = RuleEngine(config, "fp", {"point_id": "p1"})
    existing.phase = "Triggered"
    removed = RuleEngine(config, "fp", {"point_id": "removed"})
    compiled = CompiledRule(config, "fp", {"p1": existing, "removed": removed})
    monkeypatch.setattr(
        RuleRuntime,
        "_resolve_bindings",
        staticmethod(lambda _config: {
            "p1": {"point_id": "p1", "point_name": "更新名称"},
            "p2": {"point_id": "p2", "point_name": "新增测点"},
        }),
    )

    rebound = RuleRuntime._rebind_compiled(compiled)

    assert set(rebound.engines) == {"p1", "p2"}
    assert rebound.engines["p1"].phase == "Triggered"
    assert rebound.engines["p1"].metadata["point_name"] == "更新名称"
    assert rebound.engines["p2"].phase == "Normal"


def test_semantic_binding_requires_at_least_one_enabled_instance(monkeypatch):
    config = _semantic_config()
    monkeypatch.setattr(
        asset_rdf_runtime,
        "describe_asset",
        lambda _asset_id: {
            "asset_id": "floor-3", "asset_type": "floor", "name": "三层", "is_enabled": True,
        },
    )
    monkeypatch.setattr(asset_rdf_runtime, "point_definition_exists", lambda _point_id: True)
    monkeypatch.setattr(asset_rdf_runtime, "resolve_sensor_point_ids", lambda *_args, **_kwargs: [])

    with pytest.raises(ValidationError, match="matched no enabled sensor points"):
        RuleRuntime._resolve_bindings(config)


def test_asset_rebuild_moves_empty_semantic_rule_to_failed_and_retries(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'semantic-rebind.db'}")
    Base.metadata.create_all(engine, tables=[Rule.__table__, RuleEvent.__table__, ActionTask.__table__])
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setitem(sql_manager.sessions, "main", factory)
    config = _semantic_config()
    runtime = RuleRuntime()
    runtime.install_rule("r-semantic", CompiledRule(
        config, "fp", {"p1": RuleEngine(config, "fp", {"point_id": "p1"})}
    ))
    now = datetime.now(timezone.utc)
    with factory() as db:
        db.add(Rule(
            rule_id="r-semantic", rule_name=config.rule_name,
            rule_file_name="r-semantic.ttl", status="running", created_at=now,
        ))
        db.commit()

    monkeypatch.setattr(
        RuleRuntime,
        "_resolve_bindings",
        staticmethod(lambda _config: (_ for _ in ()).throw(
            ValidationError("semantic selector matched no enabled sensor points")
        )),
    )
    runtime._on_assets_rebuilt(1)
    with factory() as db:
        row = db.get(Rule, "r-semantic")
        assert row.status == "compile_failed"
        assert "matched no enabled" in row.error
    assert "r-semantic" not in runtime._engines

    monkeypatch.setattr(rule_rdf_service, "read", lambda *_args: (config, "fp"))
    monkeypatch.setattr(
        RuleRuntime,
        "_resolve_bindings",
        staticmethod(lambda _config: {"p2": {"point_id": "p2", "point_name": "新增温度"}}),
    )
    runtime._on_assets_rebuilt(2)
    with factory() as db:
        row = db.get(Rule, "r-semantic")
        assert row.status == "running"
        assert row.error is None
    assert set(runtime._engines["r-semantic"].engines) == {"p2"}
    assert runtime._engines["r-semantic"].engines["p2"].phase == "Normal"
    engine.dispose()


def test_restart_restores_latest_event_for_each_semantic_point(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'semantic-restore.db'}")
    Base.metadata.create_all(engine, tables=[Rule.__table__, RuleEvent.__table__, ActionTask.__table__])
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setitem(sql_manager.sessions, "main", factory)
    config = _semantic_config()
    now = datetime.now(timezone.utc)
    with factory() as db:
        db.add(Rule(
            rule_id="r-semantic", rule_name=config.rule_name,
            rule_file_name="r-semantic.ttl", status="running", created_at=now,
        ))
        db.flush()
        db.add_all([
            RuleEvent(
                event_id="e-p1", rule_id="r-semantic", event_type="triggered",
                evidence={"point_id": "p1", "rule_fingerprint": "fp"}, event_time=now,
            ),
            RuleEvent(
                event_id="e-p2", rule_id="r-semantic", event_type="recovered",
                evidence={"point_id": "p2", "rule_fingerprint": "fp"}, event_time=now,
            ),
        ])
        db.commit()
    compiled = CompiledRule(config, "fp", {
        "p1": RuleEngine(config, "fp", {"point_id": "p1"}),
        "p2": RuleEngine(config, "fp", {"point_id": "p2"}),
    })

    RuleRuntime._restore_point_engines("r-semantic", compiled)

    assert compiled.engines["p1"].phase == "Triggered"
    assert compiled.engines["p2"].phase == "Normal"
    engine.dispose()
