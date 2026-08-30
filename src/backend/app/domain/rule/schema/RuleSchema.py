from __future__ import annotations

import math
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.common.validators import validate_email_address


COMPARISONS = {
    "GreaterThan", "GreaterThanOrEqual", "LessThan", "LessThanOrEqual", "Equal", "NotEqual"
}
LOGICAL = {"AND", "OR", "NOT"}
OPERANDS = {
    "PointValue", "ConstantValue", "PreviousDifference",
    "AbsolutePreviousDifference", "SampleLagDifference", "TimeLagDifference",
    "WindowAverageDifference", "WindowRange", "RateOfChange",
}
ACTION_TYPES = {"LogAction", "EmailAction", "SensorControlAction"}


class PointSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selector_id: str = Field(min_length=1, max_length=100)
    type: Literal["PointIdSelector"]
    point_id: str = Field(min_length=1, max_length=100)


class SemanticPointSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selector_id: str = Field(min_length=1, max_length=100)
    type: Literal["SemanticPointSelector"]
    point_definition_id: str = Field(min_length=1, max_length=100)
    location_id: str = Field(min_length=1, max_length=100)
    location_type: Literal["building", "floor", "room"]


RuleSelector = Annotated[
    PointSelector | SemanticPointSelector,
    Field(discriminator="type"),
]


class Operand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    selector_id: str | None = None
    value: float | None = None
    samples: int | None = None
    duration_seconds: float | None = None
    tolerance_seconds: float | None = None
    window_seconds: float | None = None
    time_unit_seconds: float | None = None

    @model_validator(mode="after")
    def validate_operand(self):
        if self.type not in OPERANDS:
            raise ValueError(f"unsupported operand: {self.type}")
        numeric_fields = (
            "value", "duration_seconds", "tolerance_seconds",
            "window_seconds", "time_unit_seconds",
        )
        for field_name in numeric_fields:
            field_value = getattr(self, field_name)
            if field_value is not None and not math.isfinite(field_value):
                raise ValueError(f"{field_name} must be finite")

        base_allowed = {"type", "selector_id"}
        allowed_by_type = {
            "PointValue": base_allowed,
            "ConstantValue": {"type", "value"},
            "PreviousDifference": base_allowed,
            "AbsolutePreviousDifference": base_allowed,
            "SampleLagDifference": base_allowed | {"samples"},
            "TimeLagDifference": base_allowed | {"duration_seconds", "tolerance_seconds"},
            "WindowAverageDifference": base_allowed | {"window_seconds"},
            "WindowRange": base_allowed | {"window_seconds"},
            "RateOfChange": base_allowed | {
                "samples", "duration_seconds", "tolerance_seconds", "time_unit_seconds"
            },
        }
        supplied = {name for name, value in self.model_dump().items() if value is not None}
        unexpected = supplied - allowed_by_type[self.type]
        if unexpected:
            raise ValueError(f"{self.type} has unexpected parameters: {', '.join(sorted(unexpected))}")
        if self.type == "ConstantValue":
            if self.value is None or isinstance(self.value, bool) or not math.isfinite(self.value):
                raise ValueError("ConstantValue requires a finite value")
        elif not self.selector_id:
            raise ValueError(f"{self.type} requires selector_id")
        if self.type == "SampleLagDifference" and (self.samples is None or self.samples < 1):
            raise ValueError("SampleLagDifference requires samples >= 1")
        if self.type == "TimeLagDifference":
            if self.duration_seconds is None or self.duration_seconds <= 0:
                raise ValueError("TimeLagDifference requires duration_seconds > 0")
            if self.tolerance_seconds is None or self.tolerance_seconds < 0:
                raise ValueError("TimeLagDifference requires tolerance_seconds >= 0")
        if self.type in {"WindowAverageDifference", "WindowRange"}:
            if self.window_seconds is None or self.window_seconds <= 0:
                raise ValueError(f"{self.type} requires window_seconds > 0")
        if self.type == "RateOfChange":
            by_sample = self.samples is not None and self.samples >= 1
            by_time = self.duration_seconds is not None and self.duration_seconds > 0
            if by_sample == by_time:
                raise ValueError("RateOfChange requires exactly one of samples or duration_seconds")
            if by_time and (self.tolerance_seconds is None or self.tolerance_seconds < 0):
                raise ValueError("time based RateOfChange requires tolerance_seconds >= 0")
            if by_sample and self.tolerance_seconds is not None:
                raise ValueError("sample based RateOfChange does not accept tolerance_seconds")
            if self.time_unit_seconds is None or self.time_unit_seconds <= 0:
                raise ValueError("RateOfChange requires time_unit_seconds > 0")
        return self


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["Comparison", "Logical"]
    operator: str
    left: Operand | None = None
    right: Operand | None = None
    children: list[Condition] | None = None

    @model_validator(mode="after")
    def validate_node(self):
        if self.type == "Comparison":
            if self.operator not in COMPARISONS or self.left is None or self.right is None:
                raise ValueError("invalid comparison node")
            if self.children is not None:
                raise ValueError("comparison cannot have children")
        else:
            if self.operator not in LOGICAL or not self.children:
                raise ValueError("invalid logical node")
            if self.left is not None or self.right is not None:
                raise ValueError("logical node cannot have operands")
            if self.operator == "NOT" and len(self.children) != 1:
                raise ValueError("NOT requires exactly one child")
            if self.operator in {"AND", "OR"} and len(self.children) < 2:
                raise ValueError(f"{self.operator} requires at least two children")
        return self


class TriggerPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trigger_count: int = Field(default=1, ge=1)
    trigger_duration_seconds: float = Field(default=0, ge=0)
    recovery_count: int = Field(default=1, ge=1)
    recovery_duration_seconds: float = Field(default=0, ge=0)
    repeat_policy: Literal["OncePerIncident", "NewMatch", "Periodic"] = "OncePerIncident"
    repeat_interval_seconds: float | None = None
    cooldown_seconds: float = Field(default=0, ge=0)
    merge_window_seconds: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_repeat(self):
        for field_name in (
            "trigger_duration_seconds", "recovery_duration_seconds",
            "repeat_interval_seconds", "cooldown_seconds", "merge_window_seconds",
        ):
            value = getattr(self, field_name)
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{field_name} must be finite")
        if self.repeat_policy == "Periodic":
            if self.repeat_interval_seconds is None or self.repeat_interval_seconds <= 0:
                raise ValueError("Periodic requires repeat_interval_seconds > 0")
        elif self.repeat_interval_seconds is not None:
            raise ValueError("repeat_interval_seconds is only valid for Periodic")
        return self


class LogActionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    content: str = Field(min_length=1, max_length=10000)


class LogAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str | None = Field(default=None, max_length=100)
    type: Literal["LogAction"]
    params: LogActionParams


class EmailActionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipients: list[str] = Field(min_length=1, max_length=50)
    subject: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)

    @field_validator("recipients")
    @classmethod
    def validate_recipients(cls, values: list[str]) -> list[str]:
        return [validate_email_address(value) for value in values]


class EmailAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str | None = Field(default=None, max_length=100)
    type: Literal["EmailAction"]
    params: EmailActionParams


class SensorControlActionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    control_id: str = Field(min_length=1, max_length=100)


class SensorControlAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str | None = Field(default=None, max_length=100)
    type: Literal["SensorControlAction"]
    params: SensorControlActionParams


RuleAction = Annotated[
    LogAction | EmailAction | SensorControlAction,
    Field(discriminator="type"),
]


class RuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    selector: RuleSelector
    condition: Condition
    trigger_policy: TriggerPolicy = Field(default_factory=TriggerPolicy)
    actions: list[RuleAction] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self):
        selector_id = self.selector.selector_id
        action_ids = [item.action_id for item in self.actions if item.action_id]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("action_id must be unique within a rule")

        def walk(node: Condition):
            if node.type == "Comparison":
                for operand in (node.left, node.right):
                    if operand and operand.type != "ConstantValue" and operand.selector_id != selector_id:
                        raise ValueError(f"unknown selector_id: {operand.selector_id}")
            else:
                for child in node.children or []:
                    walk(child)
        walk(self.condition)
        return self


class RuleQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_name: str | None = Field(default=None, max_length=100)
    status: Literal["paused", "running", "validating", "compile_failed"] | None = None
    create_at: date | None = None


class EventQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_id: str | None = Field(default=None, max_length=100)
    event_type: Literal["triggered", "recovered"] | None = None
    event_time: date | None = None


class TaskQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_id: str | None = Field(default=None, max_length=100)
    event_id: str | None = Field(default=None, max_length=100)
    action_type: Literal["LogAction", "EmailAction", "SensorControlAction"] | None = None
    status: Literal["pending", "executing", "succeeded", "failed"] | None = None
    create_time: date | None = None
    completed_time: date | None = None


Condition.model_rebuild()
