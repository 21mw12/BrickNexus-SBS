import json
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.domain.log.repository.models import Log
from app.domain.log.schema import LogQuery
from app.domain.log.service import LogService
from app.domain.log.api.LogAPI import get_log_options
from app.domain.rule.repository.models import ActionTask, Rule, RuleEvent
from app.domain.rule.service.ActionWorker import ActionWorker
from app.infra.DB.SQLConnection import Base, sql_manager


def _database(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'rules.db'}")
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine, tables=[Rule.__table__, RuleEvent.__table__, ActionTask.__table__, Log.__table__])
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def test_log_action_writes_business_log_and_finishes_task(monkeypatch, tmp_path):
    engine, factory = _database(tmp_path)
    old = sql_manager.sessions["main"]
    monkeypatch.setitem(sql_manager.sessions, "main", factory)
    now = datetime.now(timezone.utc)
    with factory() as db:
        db.add(Rule(rule_id="r1", rule_name="rule", rule_file_name="r1.ttl", status="running", created_at=now))
        db.flush()
        db.add(RuleEvent(event_id="e1", rule_id="r1", event_type="triggered", evidence={"point_name": "温度", "value": 42, "measurement_time": now.isoformat()}, event_time=now))
        db.flush()
        db.add(ActionTask(task_id="t1", rule_id="r1", event_id="e1", action_id="a1", action_type="LogAction", action_params={"level": "WARNING", "content": "{{$.point_name}}={{$.value}}"}, is_executed=False, status="pending", created_at=now))
        db.commit()
    assert ActionWorker().process_one() is True
    with factory() as db:
        task = db.get(ActionTask, "t1")
        log = db.scalar(select(Log))
        assert task.status == "succeeded" and task.is_executed is True
        assert log.operator == "SYSTEM" and log.content == "温度=42"
        listed = LogService.list_logs(db, 1, 20, LogQuery(
            type="rule_action",
            level="WARNING",
            operator="SYSTEM",
            time=now.astimezone(ZoneInfo("Asia/Shanghai")).date(),
        ))
        assert listed["total"] == 1
        db.delete(db.get(Rule, "r1"))
        db.commit()
        db.expire_all()
        assert db.get(ActionTask, "t1") is None
        assert db.get(Log, log.id) is not None
    monkeypatch.setitem(sql_manager.sessions, "main", old)
    engine.dispose()


def test_failed_action_is_terminal_and_not_retried(monkeypatch, tmp_path):
    engine, factory = _database(tmp_path)
    old = sql_manager.sessions["main"]
    monkeypatch.setitem(sql_manager.sessions, "main", factory)
    now = datetime.now(timezone.utc)
    with factory() as db:
        db.add(Rule(rule_id="r1", rule_name="rule", rule_file_name="r1.ttl", status="running", created_at=now))
        db.flush()
        db.add(RuleEvent(event_id="e1", rule_id="r1", event_type="triggered", evidence={}, event_time=now))
        db.flush()
        db.add(ActionTask(
            task_id="t1", rule_id="r1", event_id="e1", action_id="a1",
            action_type="Unsupported", action_params={}, is_executed=False,
            status="pending", created_at=now,
        ))
        db.commit()

    worker = ActionWorker()
    assert worker.process_one() is True
    assert worker.process_one() is False
    with factory() as db:
        task = db.get(ActionTask, "t1")
        assert task.status == "failed" and task.is_executed is True
        assert "unsupported action type" in task.error
        assert db.scalar(select(Log)) is None

    monkeypatch.setitem(sql_manager.sessions, "main", old)
    engine.dispose()


def test_log_options_provide_english_values_and_chinese_labels():
    response = get_log_options(None)
    assert response.status_code == 200
    data = json.loads(response.body)["data"]
    assert {item["value"] for item in data["types"]} == LogService.TYPES
    assert {item["value"] for item in data["levels"]} == LogService.LEVELS
    assert all(item["label"] and item["label"] != item["value"] for item in data["types"] + data["levels"])


def test_log_action_formats_time_without_fraction_or_timezone():
    content = ActionWorker._render(
        "{{$.point_name}} 在 {{$.time}} 的值为 {{$.value}}",
        {
            "point_name": "会议室温度",
            "measurement_time": "2026-08-21T14:05:06.789123+08:00",
            "value": 42,
        },
    )

    assert content == "会议室温度 在 2026-08-21 14:05:06 的值为 42"


def test_log_calendar_day_uses_configured_business_timezone():
    start, end = LogService._day_bounds(date(2026, 8, 18))
    assert start == datetime(2026, 8, 17, 16, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 18, 16, tzinfo=timezone.utc)


def test_waiting_email_does_not_block_log_and_merges_matching_events(monkeypatch, tmp_path):
    engine, factory = _database(tmp_path)
    monkeypatch.setitem(sql_manager.sessions, "main", factory)
    now = datetime.now(timezone.utc)
    sent = []
    monkeypatch.setattr(
        "app.domain.rule.service.ActionWorker.smtp_client.send",
        lambda recipients, subject, content: sent.append((recipients, subject, content)),
    )
    with factory() as db:
        db.add(Rule(rule_id="r1", rule_name="rule", rule_file_name="r1.ttl", status="running", created_at=now))
        for index, value in enumerate((41, 42), start=1):
            occurred = now + timedelta(seconds=index)
            db.add(RuleEvent(
                event_id=f"e{index}", rule_id="r1", event_type="triggered",
                evidence={"point_name": f"温度{index}", "value": value,
                          "measurement_time": occurred.isoformat(), "rule_fingerprint": "v1"},
                event_time=occurred,
            ))
            db.flush()
            db.add(ActionTask(
                task_id=f"mail{index}", rule_id="r1", event_id=f"e{index}", action_id="email",
                action_type="EmailAction",
                action_params={"recipients": ["ops@example.com"], "subject": "告警",
                               "content": "{{$.point_name}}={{$.value}}", "merge_window_seconds": 10},
                is_executed=False, status="pending", created_at=now + timedelta(seconds=index),
            ))
        db.add(ActionTask(
            task_id="log", rule_id="r1", event_id="e1", action_id="log",
            action_type="LogAction", action_params={"level": "INFO", "content": "即时日志"},
            is_executed=False, status="pending", created_at=now + timedelta(seconds=3),
        ))
        db.commit()

    worker = ActionWorker()
    assert worker.process_one(now + timedelta(seconds=5)) is True
    assert sent == []
    assert worker.process_one(now + timedelta(seconds=12)) is True
    assert sent == [(["ops@example.com"], "告警", "温度1=41\n温度2=42")]
    with factory() as db:
        assert all(db.get(ActionTask, task_id).status == "succeeded" for task_id in ("mail1", "mail2", "log"))
    engine.dispose()


def test_sensor_control_action_reuses_control_service(monkeypatch, tmp_path):
    engine, factory = _database(tmp_path)
    monkeypatch.setitem(sql_manager.sessions, "main", factory)
    now = datetime.now(timezone.utc)
    calls = []
    monkeypatch.setattr(
        "app.domain.rule.service.ActionWorker.ControlService.execute",
        lambda db, control_id: calls.append(control_id),
    )
    with factory() as db:
        db.add(Rule(rule_id="r1", rule_name="rule", rule_file_name="r1.ttl", status="running", created_at=now))
        db.add(RuleEvent(event_id="e1", rule_id="r1", event_type="triggered", evidence={}, event_time=now))
        db.flush()
        db.add(ActionTask(
            task_id="t1", rule_id="r1", event_id="e1", action_id="a1",
            action_type="SensorControlAction", action_params={"control_id": "control-1"},
            is_executed=False, status="pending", created_at=now,
        ))
        db.commit()
    assert ActionWorker().process_one() is True
    assert calls == ["control-1"]
    with factory() as db:
        assert db.get(ActionTask, "t1").status == "succeeded"
    engine.dispose()


def test_recover_interrupted_marks_unknown_without_replay(monkeypatch, tmp_path):
    engine, factory = _database(tmp_path)
    monkeypatch.setitem(sql_manager.sessions, "main", factory)
    now = datetime.now(timezone.utc)
    with factory() as db:
        db.add(Rule(rule_id="r1", rule_name="rule", rule_file_name="r1.ttl", status="running", created_at=now))
        db.add(RuleEvent(event_id="e1", rule_id="r1", event_type="triggered", evidence={}, event_time=now))
        db.flush()
        db.add(ActionTask(
            task_id="t1", rule_id="r1", event_id="e1", action_id="a1",
            action_type="EmailAction", action_params={}, is_executed=False,
            status="executing", created_at=now,
        ))
        db.commit()
    assert ActionWorker().recover_interrupted() == 1
    with factory() as db:
        task = db.get(ActionTask, "t1")
        assert task.status == "failed" and task.is_executed is True
        assert "执行结果未知" in task.error
    engine.dispose()


def test_merged_email_failure_finishes_every_task_without_retry(monkeypatch, tmp_path):
    engine, factory = _database(tmp_path)
    monkeypatch.setitem(sql_manager.sessions, "main", factory)
    now = datetime.now(timezone.utc)

    def fail_send(*_args):
        raise TimeoutError("SMTP timeout")

    monkeypatch.setattr("app.domain.rule.service.ActionWorker.smtp_client.send", fail_send)
    with factory() as db:
        db.add(Rule(rule_id="r1", rule_name="rule", rule_file_name="r1.ttl", status="running", created_at=now))
        for index in (1, 2):
            db.add(RuleEvent(
                event_id=f"e{index}", rule_id="r1", event_type="triggered",
                evidence={"rule_fingerprint": "v1"}, event_time=now + timedelta(seconds=index),
            ))
            db.flush()
            db.add(ActionTask(
                task_id=f"t{index}", rule_id="r1", event_id=f"e{index}", action_id="email",
                action_type="EmailAction", action_params={
                    "recipients": ["ops@example.com"], "subject": "x", "content": "x",
                    "merge_window_seconds": 5,
                }, is_executed=False, status="pending", created_at=now + timedelta(seconds=index),
            ))
        db.commit()
    worker = ActionWorker()
    assert worker.process_one(now + timedelta(seconds=10)) is True
    assert worker.process_one(now + timedelta(seconds=10)) is False
    with factory() as db:
        for task_id in ("t1", "t2"):
            task = db.get(ActionTask, task_id)
            assert task.status == "failed" and task.is_executed is True
            assert "SMTP timeout" in task.error
    engine.dispose()
