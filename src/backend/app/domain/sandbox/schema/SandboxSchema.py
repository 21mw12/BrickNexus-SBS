from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GeneratorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    noise: float = Field(default=0, ge=0)
    min: float
    max: float

    @model_validator(mode="after")
    def validate_values(self):
        if not all(math.isfinite(item) for item in (self.noise, self.min, self.max)):
            raise ValueError("generator values must be finite")
        if self.min > self.max:
            raise ValueError("generator min must not exceed max")
        return self


class SandboxPointConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    source_point_id: str | None = Field(default=None, min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    unit: str = Field(default="", max_length=30)
    base_value: float
    generator: GeneratorConfig

    @model_validator(mode="after")
    def validate_base_value(self):
        if isinstance(self.base_value, bool) or not math.isfinite(self.base_value):
            raise ValueError("base_value must be finite")
        if not self.generator.min <= self.base_value <= self.generator.max:
            raise ValueError("base_value must be between generator min and max")
        return self


class SandboxSensorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    model_id: str | None = Field(default=None, min_length=1, max_length=100)
    points: list[SandboxPointConfig] = Field(min_length=1)


class SandboxTerminalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    sensors: list[SandboxSensorConfig] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def discard_legacy_interval(cls, value):
        """Older sandbox exports stored a terminal-level sampling interval."""
        if isinstance(value, dict) and "interval_ticks" in value:
            value = dict(value)
            value.pop("interval_ticks", None)
        return value


class SandboxRuleRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_id: str = Field(min_length=1, max_length=100)
    state: bool = True
    effective_tick: int = Field(ge=0)


class SandboxConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    speed: Literal[1, 2, 5, 10] = 1
    terminals: list[SandboxTerminalConfig] = Field(min_length=1)
    sandbox_rule: list[SandboxRuleRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self):
        point_ids = [
            point.id
            for terminal in self.terminals
            for sensor in terminal.sensors
            for point in sensor.points
        ]
        if len(point_ids) != len(set(point_ids)):
            raise ValueError("point id must be unique within sandbox")
        rule_ids = [rule.rule_id for rule in self.sandbox_rule]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rule id must be unique within sandbox")
        return self


class SandboxCreateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sandbox_name: str = Field(min_length=1, max_length=30)
    description: str | None = Field(default=None, max_length=500)
    config: SandboxConfig


class SandboxEditSchema(SandboxCreateSchema):
    pass


class SandboxSpeedSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    speed: Literal[1, 2, 5, 10]


class SandboxDataQuerySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    point_ids: list[str] = Field(min_length=1, max_length=10)
    start_tick: int = Field(ge=0)
    end_tick: int = Field(gt=0)
    method: Literal["lttb", "fixed_interval"] = "lttb"
    sample_count: int = Field(default=500, ge=3, le=5000)
    interval_ticks: int | None = Field(default=None, ge=1)
    aggregation: Literal["mean", "min", "max", "first", "last"] = "mean"

    @field_validator("point_ids")
    @classmethod
    def normalize_points(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            item = value.strip()
            if not item:
                raise ValueError("point id must not be empty")
            if item not in result:
                result.append(item)
        return result

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_tick <= self.start_tick:
            raise ValueError("end_tick must be greater than start_tick")
        if self.method == "fixed_interval" and self.interval_ticks is None:
            raise ValueError("fixed_interval requires interval_ticks")
        return self


class SandboxRawQuerySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    point_ids: list[str] = Field(min_length=1, max_length=10)
    start_tick: int = Field(ge=0)
    end_tick: int = Field(gt=0)

    @field_validator("point_ids")
    @classmethod
    def normalize_points(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            item = value.strip()
            if not item:
                raise ValueError("point id must not be empty")
            if item not in result:
                result.append(item)
        return result

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_tick <= self.start_tick:
            raise ValueError("end_tick must be greater than start_tick")
        return self


class SandboxFaultSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fault_type: Literal["offset", "drift", "spike", "stuck", "noise"]
    point_id: str = Field(min_length=1, max_length=100)
    duration_ticks: int | None = Field(default=None, ge=1)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_parameters(self):
        required = {
            "offset": ("offset",),
            "drift": ("offset_per_tick",),
            "spike": ("value",),
            "stuck": (),
            "noise": ("noise",),
        }[self.fault_type]
        missing = [key for key in required if key not in self.parameters]
        if missing:
            raise ValueError(f"missing fault parameters: {', '.join(missing)}")
        for key in required:
            value = self.parameters[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"fault parameter {key} must be finite")
        if self.fault_type == "noise" and self.parameters["noise"] < 0:
            raise ValueError("noise must be non-negative")
        if self.fault_type == "spike" and self.parameters.get("mode", "set") not in {"set", "add"}:
            raise ValueError("spike mode must be set or add")
        return self


class SandboxEventQuerySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: str | None = Field(default=None, max_length=30)
