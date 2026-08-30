from datetime import datetime, timedelta, timezone

import pytest

from app.domain.rule.schema import RuleConfig
from app.domain.rule.service.RuleEngine import RuleEngine


def _config(left, operator="GreaterThan", threshold=5, policy=None):
    return RuleConfig.model_validate({
        "rule_name": "test", "description": "",
        "selector": {"selector_id": "monitor", "type": "PointIdSelector", "point_id": "p1"},
        "condition": {
            "type": "Comparison", "operator": operator,
            "left": {"selector_id": "monitor", **left},
            "right": {"type": "ConstantValue", "value": threshold},
        },
        "trigger_policy": policy or {
            "trigger_count": 1, "trigger_duration_seconds": 0,
            "recovery_count": 1, "recovery_duration_seconds": 0,
            "repeat_policy": "OncePerIncident", "repeat_interval_seconds": None,
            "cooldown_seconds": 0, "merge_window_seconds": 0,
        },
        "actions": [{"action_id": "a1", "type": "LogAction", "params": {"level": "WARNING", "content": "x"}}],
    })


@pytest.mark.parametrize(
    "operand,first,second,threshold",
    [
        ({"type": "PreviousDifference"}, 10, 16, 5),
        ({"type": "AbsolutePreviousDifference"}, 10, 3, 5),
        ({"type": "SampleLagDifference", "samples": 1}, 10, 16, 5),
        ({"type": "TimeLagDifference", "duration_seconds": 10, "tolerance_seconds": 1}, 10, 16, 5),
        ({"type": "WindowAverageDifference", "window_seconds": 20}, 10, 16, 5),
        ({"type": "WindowRange", "window_seconds": 20}, 10, 16, 5),
        ({"type": "RateOfChange", "samples": 1, "time_unit_seconds": 10}, 10, 16, 5),
    ],
)
def test_history_operands_are_unknown_until_warm(operand, first, second, threshold):
    engine = RuleEngine(_config(operand, threshold=threshold), "fp", {})
    start = datetime(2026, 8, 18, tzinfo=timezone.utc)
    assert engine.process(start, first) is None
    decision = engine.process(start + timedelta(seconds=10), second)
    assert decision is not None
    assert decision.event_type == "triggered"


def test_counts_duration_periodic_recovery_and_cooldown():
    policy = {
        "trigger_count": 2, "trigger_duration_seconds": 10,
        "recovery_count": 2, "recovery_duration_seconds": 10,
        "repeat_policy": "Periodic", "repeat_interval_seconds": 20,
        "cooldown_seconds": 30, "merge_window_seconds": 5,
    }
    engine = RuleEngine(_config({"type": "PointValue"}, threshold=40, policy=policy), "fp", {})
    t = datetime(2026, 8, 18, tzinfo=timezone.utc)
    assert engine.process(t, 41) is None
    assert engine.process(t + timedelta(seconds=10), 42).reason == "initial"
    assert engine.process(t + timedelta(seconds=20), 43) is None
    assert engine.process(t + timedelta(seconds=30), 44).reason == "periodic"
    assert engine.process(t + timedelta(seconds=40), 39) is None
    recovered = engine.process(t + timedelta(seconds=50), 38)
    assert recovered.event_type == "recovered"
    assert engine.process(t + timedelta(seconds=60), 50) is None
    assert engine.process(t + timedelta(seconds=80), 50) is None
    assert engine.process(t + timedelta(seconds=90), 50).reason == "initial"


def test_out_of_order_and_fingerprint_restore():
    config = _config({"type": "PointValue"}, threshold=40)
    engine = RuleEngine(config, "fp", {})
    t = datetime(2026, 8, 18, tzinfo=timezone.utc)
    assert engine.process(t, 41).event_type == "triggered"
    assert engine.process(t, 10) is None
    restored = RuleEngine(config, "fp", {})
    restored.restore({"rule_fingerprint": "fp"}, "triggered", t)
    assert restored.phase == "Triggered"
    other = RuleEngine(config, "new", {})
    other.restore({"rule_fingerprint": "fp"}, "triggered", t)
    assert other.phase == "Normal"


@pytest.mark.parametrize(
    "operator,value,threshold,expected",
    [
        ("GreaterThan", 2, 1, True),
        ("GreaterThanOrEqual", 1, 1, True),
        ("LessThan", 0, 1, True),
        ("LessThanOrEqual", 1, 1, True),
        ("Equal", 1, 1, True),
        ("NotEqual", 2, 1, True),
    ],
)
def test_all_comparison_operators(operator, value, threshold, expected):
    engine = RuleEngine(_config({"type": "PointValue"}, operator, threshold), "fp", {})
    decision = engine.process(datetime(2026, 8, 18, tzinfo=timezone.utc), value)
    assert (decision is not None) is expected


@pytest.mark.parametrize(
    "operator,children,should_trigger",
    [
        ("AND", [("GreaterThan", 0), ("LessThan", 10)], True),
        ("OR", [("LessThan", 0), ("GreaterThan", 3)], True),
        ("NOT", [("LessThan", 0)], True),
    ],
)
def test_logical_operators(operator, children, should_trigger):
    nodes = [
        {
            "type": "Comparison", "operator": comparison,
            "left": {"type": "PointValue", "selector_id": "monitor"},
            "right": {"type": "ConstantValue", "value": threshold},
        }
        for comparison, threshold in children
    ]
    config = RuleConfig.model_validate({
        "rule_name": "logic", "description": "",
        "selector": {"selector_id": "monitor", "type": "PointIdSelector", "point_id": "p1"},
        "condition": {"type": "Logical", "operator": operator, "children": nodes},
        "actions": [{"action_id": "a1", "type": "LogAction", "params": {"level": "INFO", "content": "x"}}],
    })
    engine = RuleEngine(config, "fp", {})
    decision = engine.process(datetime(2026, 8, 18, tzinfo=timezone.utc), 5)
    assert (decision is not None) is should_trigger


def test_operand_rejects_irrelevant_parameters():
    payload = _config({"type": "PointValue"}).model_dump(mode="json")
    payload["condition"]["left"]["window_seconds"] = 60
    with pytest.raises(ValueError, match="unexpected parameters"):
        RuleConfig.model_validate(payload)
