"""进程内采集事件的顺序、隔离和不可变性测试。"""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.domain.collector.event import MeasurementBatchEvent, MeasurementValue
from app.domain.collector.event_bus import CollectionEventBus


def _event() -> MeasurementBatchEvent:
    return MeasurementBatchEvent(
        request_id="api-1",
        request_type="http",
        occurred_at=datetime(2026, 8, 18, tzinfo=timezone.utc),
        terminal_ids=("terminal-1",),
        points=(),
        measurements=(
            MeasurementValue(
                point_id="point-1",
                sensor_id="sensor-1",
                terminal_id="terminal-1",
                value=42.0,
            ),
        ),
        sensor_statuses=(("sensor-1", True),),
    )


def test_data_priority_runs_before_future_rule_consumer() -> None:
    bus = CollectionEventBus()
    order = []
    bus.subscribe(MeasurementBatchEvent, lambda event: order.append("rule"), critical=False, priority=100)
    bus.subscribe(MeasurementBatchEvent, lambda event: order.append("data"), critical=True, priority=0)

    bus.publish(_event())

    assert order == ["data", "rule"]


def test_critical_failure_propagates_and_stops_later_consumers() -> None:
    bus = CollectionEventBus()
    order = []

    def fail(_event):
        order.append("data")
        raise RuntimeError("storage failed")

    bus.subscribe(MeasurementBatchEvent, fail, critical=True, priority=0)
    bus.subscribe(MeasurementBatchEvent, lambda event: order.append("rule"), critical=False, priority=100)

    with pytest.raises(RuntimeError, match="storage failed"):
        bus.publish(_event())
    assert order == ["data"]


def test_noncritical_failure_isolated_from_publisher_and_other_consumers() -> None:
    bus = CollectionEventBus()
    order = []

    def fail(_event):
        order.append("rule-1")
        raise RuntimeError("rule failed")

    bus.subscribe(MeasurementBatchEvent, fail, critical=False, priority=100)
    bus.subscribe(MeasurementBatchEvent, lambda event: order.append("rule-2"), critical=False, priority=101)

    bus.publish(_event())

    assert order == ["rule-1", "rule-2"]


def test_event_and_nested_values_are_immutable() -> None:
    event = _event()
    with pytest.raises(FrozenInstanceError):
        event.request_id = "changed"
    with pytest.raises(FrozenInstanceError):
        event.measurements[0].value = 0
    with pytest.raises(TypeError):
        event.sensor_statuses[0] = ("sensor-1", False)
