import asyncio
import importlib
import random
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.sandbox.api.SandboxAPI import _parse_sandbox_subscription
from app.domain.rule.schema import RuleConfig
from app.domain.rule.service.RuleEngine import RuleEngine
from app.domain.asset.repository.models import ModelPoint, Point, SensorModel
from app.domain.sandbox.repository import SandboxMeasurementRepository
from app.domain.sandbox.repository.models import Sandbox, SandboxEvent, SandboxMeasurement
from app.domain.sandbox.schema import (
    SandboxConfig, SandboxCreateSchema, SandboxFaultSchema,
)
from app.domain.sandbox.service.SandboxFaultRuntime import SandboxFaultRuntime
from app.domain.sandbox.service.SandboxGenerator import SandboxGenerator
from app.domain.sandbox.service.SandboxRuleRuntime import RuntimeRule, SandboxRuleRuntime
from app.domain.sandbox.service.SandboxRuleService import SandboxRuleService
from app.domain.sandbox.service.SandboxRealtimeService import SandboxRealtimeService
from app.domain.sandbox.service.SandboxRuntime import SandboxRuntime
from app.domain.sandbox.service.SandboxService import SandboxService
from app.infra.DB.SQLConnection import Base


def config(interval: int = 2) -> dict:
    return {
        "speed": 1,
        "terminals": [{
            "name": "terminal", "interval_ticks": interval,
            "sensors": [{
                "name": "sensor",
                "points": [{
                    "id": "point-1", "name": "temperature", "unit": "C",
                    "base_value": 20.0,
                    "generator": {"noise": 0.0, "min": 0.0, "max": 50.0},
                }],
            }],
        }],
        "sandbox_rule": [],
    }


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Sandbox.__table__, SandboxMeasurement.__table__, SandboxEvent.__table__,
    ])
    with Session(engine) as session:
        yield session


def sandbox(db: Session, *, state: bool = True) -> Sandbox:
    row = Sandbox(
        sandbox_id="sandbox-1", sandbox_name="room", config=config(), state=state,
        tick=0, description=None, created_at=__import__("datetime").datetime.now(),
    )
    db.add(row); db.commit()
    return row


def test_config_rejects_terminal_and_sensor_state() -> None:
    payload = config()
    payload["terminals"][0]["state"] = True
    payload["terminals"][0]["sensors"][0]["state"] = True

    with pytest.raises(PydanticValidationError):
        SandboxConfig.model_validate(payload)


def test_config_discards_legacy_terminal_interval() -> None:
    parsed = SandboxConfig.model_validate(config(9))

    assert "interval_ticks" not in parsed.model_dump()["terminals"][0]


def test_generator_ignores_legacy_terminal_interval_and_runs_each_tick() -> None:
    generator = SandboxGenerator(SandboxFaultRuntime(), random.Random(1))

    rows = generator.generate("sandbox-1", config(2), 1)
    assert rows == [{
        "sandbox_id": "sandbox-1", "point_id": "point-1", "tick": 1,
        "value": 20.0,
    }]


def test_full_sandbox_query_is_ordered(db: Session) -> None:
    sandbox(db)
    repository = SandboxMeasurementRepository()
    repository.upsert_many([
        {"sandbox_id": "sandbox-1", "point_id": "point-1", "tick": 2, "value": 2.0},
        {"sandbox_id": "sandbox-1", "point_id": "point-1", "tick": 1, "value": 1.0},
    ], db)
    db.commit()

    count, stream = repository.stream_full("sandbox-1", "point-1", 0, 3, db)

    assert count == 2
    assert list(stream) == [(1, 1.0), (2, 2.0)]


def test_recent_query_limits_each_point_and_preserves_null(db: Session) -> None:
    sandbox(db)
    repository = SandboxMeasurementRepository()
    repository.upsert_many([
        {"sandbox_id": "sandbox-1", "point_id": point_id, "tick": tick,
         "value": None if point_id == "point-2" and tick == 3 else float(tick)}
        for point_id in ("point-1", "point-2")
        for tick in range(1, 5)
    ], db)
    db.commit()

    rows = repository.recent_for_points(
        "sandbox-1", ["point-1", "point-2"], 2, db
    )

    assert rows == [
        {"point_id": "point-1", "tick": 3, "value": 3.0},
        {"point_id": "point-1", "tick": 4, "value": 4.0},
        {"point_id": "point-2", "tick": 3, "value": None},
        {"point_id": "point-2", "tick": 4, "value": 4.0},
    ]


def test_drift_fault_starts_on_next_sampling_tick(db: Session) -> None:
    sandbox(db)
    faults = SandboxFaultRuntime()
    event = faults.inject("sandbox-1", SandboxFaultSchema(
        fault_type="drift", point_id="point-1", duration_ticks=3,
        parameters={"offset_per_tick": 2.0},
    ), db)

    assert event.payload["start_tick"] == 1
    assert faults.active("sandbox-1", 0) == []
    assert faults.active("sandbox-1")[0]["event_id"] == event.event_id
    assert faults.apply("sandbox-1", "point-1", 1, 20.0) == 20.0
    assert faults.apply("sandbox-1", "point-1", 2, 20.0) == 22.0


def test_sandbox_rule_creates_only_virtual_events(db: Session) -> None:
    room = sandbox(db)
    config_model = RuleConfig.model_validate({
        "rule_name": "high temperature", "description": "",
        "selector": {"selector_id": "monitor", "type": "PointIdSelector", "point_id": "point-1"},
        "condition": {"type": "Comparison", "operator": "GreaterThan", "left": {"type": "PointValue", "selector_id": "monitor"}, "right": {"type": "ConstantValue", "value": 30}},
        "trigger_policy": {"trigger_count": 1, "trigger_duration_seconds": 0, "recovery_count": 1, "recovery_duration_seconds": 0, "repeat_policy": "OncePerIncident", "cooldown_seconds": 0, "merge_window_seconds": 0},
        "actions": [{"action_id": "action-1", "type": "LogAction", "params": {"level": "WARNING", "content": "virtual"}}],
    })
    runtime = SandboxRuleRuntime()
    engine = RuleEngine(config_model, "fingerprint", {"point_id": "point-1"})
    runtime._rules[room.sandbox_id] = {
        "rule-1": RuntimeRule("rule-1", "point-1", engine)
    }

    created = runtime.process(room, 1, [{"point_id": "point-1", "value": 40.0}], db)

    assert [item.event_type for item in created] == ["rule_triggered", "virtual_action"]
    assert all(item.__class__ is SandboxEvent for item in db.new)


def test_running_sandbox_rejects_rule_creation(db: Session) -> None:
    room = sandbox(db, state=True)
    config_model = RuleConfig.model_validate({
        "rule_name": "high temperature", "description": "",
        "selector": {"selector_id": "monitor", "type": "PointIdSelector", "point_id": "point-1"},
        "condition": {"type": "Comparison", "operator": "GreaterThan", "left": {"type": "PointValue", "selector_id": "monitor"}, "right": {"type": "ConstantValue", "value": 30}},
        "trigger_policy": {"trigger_count": 1, "trigger_duration_seconds": 0, "recovery_count": 1, "recovery_duration_seconds": 0, "repeat_policy": "OncePerIncident", "cooldown_seconds": 0, "merge_window_seconds": 0},
        "actions": [{"type": "LogAction", "params": {"level": "WARNING", "content": "virtual"}}],
    })

    with pytest.raises(ValidationError, match="运行中的沙盒不能创建或修改规则"):
        SandboxRuleService.create(room.sandbox_id, config_model, db)


def test_create_canonicalizes_model_points_and_generates_virtual_id() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Point.__table__, SensorModel.__table__, ModelPoint.__table__,
        Sandbox.__table__, SandboxMeasurement.__table__, SandboxEvent.__table__,
    ])
    with Session(engine) as session:
        session.add(Point(
            point_id="definition-1", point_name="Temperature",
            point_unit="C", point_description="room temperature",
        ))
        session.add(SensorModel(
            model_id="model-1", model_name="TH-1", sensor_type="temperature",
            remark=None,
        ))
        session.flush()
        session.add(ModelPoint(model_id="model-1", point_id="definition-1"))
        session.commit()

        created = SandboxService().create(SandboxCreateSchema.model_validate({
            "sandbox_name": "room",
            "config": {
                "speed": 1,
                "terminals": [{
                    "name": "terminal",
                    "sensors": [{
                        "name": "sensor", "model_id": "model-1",
                        "points": [{
                            "id": "client-temporary-id",
                            "source_point_id": "definition-1",
                            "name": "tampered", "unit": "tampered",
                            "base_value": 20,
                            "generator": {"noise": 0.1, "min": 0, "max": 50},
                        }],
                    }],
                }],
            },
        }), session)

        point = created["config"]["terminals"][0]["sensors"][0]["points"][0]
        assert point["id"] != "client-temporary-id"
        assert point["name"] == "Temperature"
        assert point["unit"] == "C"


class _FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)


def test_realtime_filters_tick_per_connection() -> None:
    async def scenario():
        service = SandboxRealtimeService()
        first_socket, second_socket = _FakeWebSocket(), _FakeWebSocket()
        first = await service.register(first_socket, "sandbox-1")
        second = await service.register(second_socket, "sandbox-1")
        first_generation = await service.replace_subscriptions(first, ["point-1"])
        second_generation = await service.replace_subscriptions(second, ["point-2"])
        await service.activate_subscription(first, first_generation, 0)
        await service.activate_subscription(second, second_generation, 0)

        await service.publish("sandbox-1", {
            "type": "tick", "sandbox_id": "sandbox-1", "tick": 1,
            "measurements": [
                {"point_id": "point-1", "tick": 1, "value": 10.0},
                {"point_id": "point-2", "tick": 1, "value": 20.0},
            ],
        })
        await asyncio.sleep(0.01)

        assert first_socket.messages[0]["subscription_version"] == first_generation
        assert [item["point_id"] for item in first_socket.messages[0]["measurements"]] == ["point-1"]
        assert [item["point_id"] for item in second_socket.messages[0]["measurements"]] == ["point-2"]
        await service.unregister(first)
        await service.unregister(second)

    asyncio.run(scenario())


def test_realtime_snapshot_precedes_pending_tick() -> None:
    async def scenario():
        service = SandboxRealtimeService()
        websocket = _FakeWebSocket()
        connection = await service.register(websocket, "sandbox-1")
        generation = await service.replace_subscriptions(connection, ["point-1"])
        await service.publish("sandbox-1", {
            "type": "tick", "tick": 2,
            "measurements": [{"point_id": "point-1", "tick": 2, "value": 2.0}],
        })
        await service.enqueue(
            connection, {"type": "snapshot", "subscription_version": generation},
            generation,
        )
        await service.activate_subscription(connection, generation, 1)
        await asyncio.sleep(0.01)

        assert [message["type"] for message in websocket.messages] == ["snapshot", "tick"]
        await service.unregister(connection)

    asyncio.run(scenario())


def test_realtime_serializes_datetime_payloads() -> None:
    async def scenario():
        service = SandboxRealtimeService()
        websocket = _FakeWebSocket()
        connection = await service.register(websocket, "sandbox-1")
        generation = await service.replace_subscriptions(connection, [])
        await service.activate_subscription(connection, generation, 0)
        created_at = datetime(2026, 9, 4, 10, 59, 50, tzinfo=timezone.utc)

        await service.enqueue(
            connection,
            {"type": "snapshot", "sandbox": {"created_at": created_at}},
            generation,
        )
        await asyncio.sleep(0.01)

        assert websocket.messages == [{
            "type": "snapshot",
            "sandbox": {"created_at": "2026-09-04T10:59:50+00:00"},
        }]
        await service.unregister(connection)

    asyncio.run(scenario())


class _FakeJob:
    def __init__(self, delay: float) -> None:
        self.next_run_time = datetime.now(timezone.utc) + timedelta(seconds=delay)


class _FakeScheduler:
    def __init__(self) -> None:
        self.jobs = {}
        self.last_interval = None
        self.last_delay = None
        self.last_func = None

    def get_job(self, task_id):
        return self.jobs.get(task_id)

    def add_task(self, task_id, func, interval_seconds, initial_delay_seconds=None):
        self.last_interval = interval_seconds
        self.last_delay = initial_delay_seconds
        self.last_func = func
        self.jobs[task_id] = _FakeJob(initial_delay_seconds or interval_seconds)
        return self.jobs[task_id]

    def remove_task(self, task_id):
        self.jobs.pop(task_id, None)


def test_runtime_installs_explicit_first_tick_and_reports_schedule() -> None:
    scheduler = _FakeScheduler()
    runtime = SandboxRuntime(scheduler_manager=scheduler)

    metadata = runtime.ensure_job("sandbox-1", 10)

    assert scheduler.last_interval == 3
    assert scheduler.last_delay == 3
    assert metadata["tick_interval_seconds"] == 3
    assert metadata["next_tick_at"] is not None
    assert metadata["server_time"].endswith("Z")


def test_subscription_payload_deduplicates_and_limits_points() -> None:
    token, point_ids, history_limit = _parse_sandbox_subscription({
        "type": "subscribe",
        "token": " token ",
        "point_ids": ["point-1", "point-1", "point-2"],
        "history_limit": 200,
    })
    assert token == "token"
    assert point_ids == ["point-1", "point-2"]
    assert history_limit == 200

    with pytest.raises(ValidationError):
        _parse_sandbox_subscription({
            "type": "subscribe", "token": "token",
            "point_ids": [f"point-{index}" for index in range(11)],
        })


def test_scheduled_tick_failure_is_published() -> None:
    class _Realtime:
        def __init__(self):
            self.messages = []

        async def publish(self, sandbox_id, payload):
            self.messages.append((sandbox_id, payload))

    async def scenario():
        scheduler = _FakeScheduler()
        realtime = _Realtime()
        runtime = SandboxRuntime(scheduler_manager=scheduler, realtime=realtime)

        async def fail(_sandbox_id):
            raise RuntimeError("generation failed")

        runtime.advance = fail
        runtime._install_job("sandbox-1", 10)
        await scheduler.last_func()

        assert realtime.messages[0][0] == "sandbox-1"
        assert realtime.messages[0][1]["type"] == "error"
        assert realtime.messages[0][1]["code"] == "tick_failed"
        assert realtime.messages[0][1]["next_tick_at"] is not None

    asyncio.run(scenario())


def test_runtime_tick_generates_all_points_and_processes_rules_once(
    db: Session, monkeypatch
) -> None:
    room = sandbox(db)
    room.config = {
        **config(),
        "terminals": [{
            "name": "terminal",
            "sensors": [{
                "name": "sensor",
                "points": [
                    config()["terminals"][0]["sensors"][0]["points"][0],
                    {
                        "id": "point-2", "name": "humidity", "unit": "%",
                        "base_value": 50.0,
                        "generator": {"noise": 0.0, "min": 0.0, "max": 100.0},
                    },
                ],
            }],
        }],
    }
    db.commit()

    class _Faults:
        def expire(self, sandbox_id, tick, session):
            return []

    class _Generator:
        def generate(self, sandbox_id, payload, tick):
            return [
                {"sandbox_id": sandbox_id, "point_id": point["id"],
                 "tick": tick, "value": point["base_value"]}
                for terminal in payload["terminals"]
                for sensor in terminal["sensors"]
                for point in sensor["points"]
            ]

    class _Rules:
        def __init__(self):
            self.calls = 0

        def process(self, sandbox_row, tick, measurements, session):
            self.calls += 1
            assert len(measurements) == 2
            return []

    rules = _Rules()
    runtime = SandboxRuntime(
        generator=_Generator(), fault_runtime=_Faults(), rule_runtime=rules
    )
    runtime_module = importlib.import_module(
        "app.domain.sandbox.service.SandboxRuntime"
    )
    monkeypatch.setattr(
        runtime_module.sql_manager, "get_db", lambda _key: nullcontext(db)
    )

    result = runtime._advance_sync("sandbox-1")

    assert result["tick"] == 1
    assert {item["point_id"] for item in result["measurements"]} == {
        "point-1", "point-2"
    }
    assert rules.calls == 1
    assert db.query(SandboxMeasurement).count() == 2


def test_runtime_pause_is_idempotent_and_removes_job(db: Session, monkeypatch) -> None:
    room = sandbox(db, state=True)
    scheduler = _FakeScheduler()
    scheduler.jobs["sandbox:sandbox-1"] = _FakeJob(30)

    class _Realtime:
        def __init__(self):
            self.messages = []

        async def publish(self, sandbox_id, payload):
            self.messages.append(payload)

    realtime = _Realtime()
    runtime = SandboxRuntime(scheduler_manager=scheduler, realtime=realtime)
    runtime._jobs.add("sandbox:sandbox-1")
    runtime_module = importlib.import_module(
        "app.domain.sandbox.service.SandboxRuntime"
    )
    monkeypatch.setattr(
        runtime_module.sql_manager, "get_db", lambda _key: nullcontext(db)
    )

    first = asyncio.run(runtime.pause("sandbox-1"))
    second = asyncio.run(runtime.pause("sandbox-1"))

    assert first["state"] is False
    assert second["state"] is False
    assert room.state is False
    assert scheduler.get_job("sandbox:sandbox-1") is None
    assert "sandbox:sandbox-1" not in runtime._jobs
    assert [message["type"] for message in realtime.messages] == [
        "sandbox_state", "sandbox_state"
    ]
