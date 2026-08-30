from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.domain.rule.schema.RuleSchema import Condition, Operand, RuleConfig


Truth = bool | None


@dataclass
class Evaluation:
    truth: Truth
    detail: dict


@dataclass
class RuleDecision:
    event_type: str
    reason: str
    evaluation: dict


@dataclass
class RuleEngine:
    config: RuleConfig
    fingerprint: str
    metadata: dict
    history: list[tuple[datetime, float]] = field(default_factory=list)
    phase: str = "Normal"
    trigger_count: int = 0
    trigger_since: datetime | None = None
    recovery_count: int = 0
    recovery_since: datetime | None = None
    last_processed_at: datetime | None = None
    last_trigger_at: datetime | None = None
    cooldown_until: datetime | None = None

    def _time_reference(self, when: datetime, seconds: float, tolerance: float) -> tuple[datetime, float] | None:
        target = when - timedelta(seconds=seconds)
        candidates = [item for item in self.history if abs((item[0] - target).total_seconds()) <= tolerance]
        return min(candidates, key=lambda item: (abs((item[0] - target).total_seconds()), -item[0].timestamp())) if candidates else None

    def _operand(self, operand: Operand, when: datetime, current: float) -> tuple[float, dict] | None:
        kind = operand.type
        if kind == "ConstantValue":
            return float(operand.value), {"type": kind, "value": operand.value}
        if kind == "PointValue":
            return current, {"type": kind, "value": current}
        reference = None
        if kind in {"PreviousDifference", "AbsolutePreviousDifference"}:
            reference = self.history[-1] if self.history else None
        elif kind == "SampleLagDifference":
            reference = self.history[-operand.samples] if len(self.history) >= operand.samples else None
        elif kind == "TimeLagDifference":
            reference = self._time_reference(when, operand.duration_seconds, operand.tolerance_seconds)
        elif kind == "WindowAverageDifference":
            start = when - timedelta(seconds=operand.window_seconds)
            values = [value for time, value in self.history if start <= time < when]
            if not values:
                return None
            reference_value = sum(values) / len(values)
            value = current - reference_value
            return value, {"type": kind, "value": value, "reference_value": reference_value, "samples": len(values)}
        elif kind == "WindowRange":
            start = when - timedelta(seconds=operand.window_seconds)
            values = [value for time, value in self.history if start <= time < when] + [current]
            if len(values) < 2:
                return None
            value = max(values) - min(values)
            return value, {"type": kind, "value": value, "minimum": min(values), "maximum": max(values), "samples": len(values)}
        elif kind == "RateOfChange":
            if operand.samples is not None:
                reference = self.history[-operand.samples] if len(self.history) >= operand.samples else None
            else:
                reference = self._time_reference(when, operand.duration_seconds, operand.tolerance_seconds)
        if reference is None:
            return None
        ref_time, ref_value = reference
        difference = current - ref_value
        if kind == "AbsolutePreviousDifference":
            difference = abs(difference)
        if kind == "RateOfChange":
            elapsed = (when - ref_time).total_seconds()
            if elapsed <= 0:
                return None
            difference = difference / elapsed * operand.time_unit_seconds
        return difference, {
            "type": kind,
            "value": difference,
            "reference_value": ref_value,
            "reference_time": ref_time.isoformat(),
        }

    def _condition(self, node: Condition, when: datetime, current: float) -> Evaluation:
        if node.type == "Comparison":
            left = self._operand(node.left, when, current)
            right = self._operand(node.right, when, current)
            if left is None or right is None:
                return Evaluation(None, {"type": "Comparison", "operator": node.operator, "result": "Unknown"})
            a, b = left[0], right[0]
            operations = {
                "GreaterThan": lambda: a > b,
                "GreaterThanOrEqual": lambda: a >= b,
                "LessThan": lambda: a < b,
                "LessThanOrEqual": lambda: a <= b,
                "Equal": lambda: a == b,
                "NotEqual": lambda: a != b,
            }
            truth = operations[node.operator]()
            return Evaluation(truth, {
                "type": "Comparison", "operator": node.operator, "result": truth,
                "left": left[1], "right": right[1],
            })
        children = [self._condition(child, when, current) for child in node.children or []]
        values = [child.truth for child in children]
        if node.operator == "AND":
            truth = False if False in values else True if all(v is True for v in values) else None
        elif node.operator == "OR":
            truth = True if True in values else False if all(v is False for v in values) else None
        else:
            truth = None if values[0] is None else not values[0]
        return Evaluation(truth, {
            "type": "Logical", "operator": node.operator,
            "result": "Unknown" if truth is None else truth,
            "children": [child.detail for child in children],
        })

    def _meets(self, count: int, since: datetime | None, required_count: int, duration: float, now: datetime) -> bool:
        return count >= required_count and since is not None and (now - since).total_seconds() >= duration

    def _prune(self, now: datetime) -> None:
        max_samples = 2
        max_seconds = 0.0

        def scan(node: Condition):
            nonlocal max_samples, max_seconds
            if node.type == "Comparison":
                for op in (node.left, node.right):
                    if op is None:
                        continue
                    max_samples = max(max_samples, (op.samples or 0) + 1)
                    max_seconds = max(
                        max_seconds,
                        (op.duration_seconds or 0) + (op.tolerance_seconds or 0),
                        op.window_seconds or 0,
                    )
            else:
                for child in node.children or []:
                    scan(child)
        scan(self.config.condition)
        if max_seconds:
            cutoff = now - timedelta(seconds=max_seconds)
            self.history = [item for item in self.history if item[0] >= cutoff]
        if len(self.history) > max_samples and not max_seconds:
            self.history = self.history[-max_samples:]

    def process(self, when: datetime, value: float) -> RuleDecision | None:
        if self.last_processed_at is not None and when <= self.last_processed_at:
            return None
        evaluation = self._condition(self.config.condition, when, value)
        self.history.append((when, value))
        self._prune(when)
        self.last_processed_at = when
        if evaluation.truth is None:
            return None
        policy = self.config.trigger_policy
        if self.phase == "Cooldown":
            if self.cooldown_until and when < self.cooldown_until:
                return None
            self.phase = "Normal"
            self.trigger_count = 0
            self.trigger_since = None
        if self.phase == "Normal":
            if evaluation.truth:
                self.trigger_count += 1
                self.trigger_since = self.trigger_since or when
                if self._meets(self.trigger_count, self.trigger_since, policy.trigger_count, policy.trigger_duration_seconds, when):
                    self.phase = "Triggered"
                    self.last_trigger_at = when
                    self.trigger_count = 0
                    self.trigger_since = None
                    return RuleDecision("triggered", "initial", evaluation.detail)
            else:
                self.trigger_count = 0
                self.trigger_since = None
            return None
        if evaluation.truth:
            self.recovery_count = 0
            self.recovery_since = None
            if policy.repeat_policy == "Periodic" and self.last_trigger_at:
                if (when - self.last_trigger_at).total_seconds() >= policy.repeat_interval_seconds:
                    self.last_trigger_at = when
                    return RuleDecision("triggered", "periodic", evaluation.detail)
            return None
        self.recovery_count += 1
        self.recovery_since = self.recovery_since or when
        if self._meets(self.recovery_count, self.recovery_since, policy.recovery_count, policy.recovery_duration_seconds, when):
            self.recovery_count = 0
            self.recovery_since = None
            if policy.cooldown_seconds > 0:
                self.phase = "Cooldown"
                self.cooldown_until = when + timedelta(seconds=policy.cooldown_seconds)
            else:
                self.phase = "Normal"
            return RuleDecision("recovered", "recovery", evaluation.detail)
        return None

    def restore(self, evidence: dict, event_type: str, event_time: datetime) -> None:
        if evidence.get("rule_fingerprint") != self.fingerprint:
            return
        if event_type == "triggered":
            self.phase = "Triggered"
            self.last_trigger_at = event_time
        elif event_type == "recovered" and self.config.trigger_policy.cooldown_seconds > 0:
            self.phase = "Cooldown"
            self.cooldown_until = event_time + timedelta(seconds=self.config.trigger_policy.cooldown_seconds)
