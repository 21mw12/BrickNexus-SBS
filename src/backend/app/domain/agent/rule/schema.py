from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DraftModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_default=True)


Number = float | Literal[""]


class FormFields(DraftModel):
    rule_name: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=1000)
    selector_id: str = Field(default="monitor", max_length=100)
    selector_type: Literal["PointIdSelector", "SemanticPointSelector"] = "PointIdSelector"
    point_id: str = Field(default="", max_length=100)
    point_definition_id: str = Field(default="", max_length=100)
    location_id: str = Field(default="", max_length=100)
    location_type: Literal["", "building", "floor", "room"] = ""
    logic: Literal["single", "AND", "OR", "NOT"] = "single"
    trigger_count: Number = 1
    trigger_duration: Number = 0
    recovery_count: Number = 1
    recovery_duration: Number = 0
    repeat_policy: Literal["OncePerIncident", "NewMatch", "Periodic"] = "OncePerIncident"
    repeat_interval: Number = 60
    cooldown: Number = 0
    merge_window: Number = 0


class ComparisonForm(DraftModel):
    operator: Literal["GreaterThan", "GreaterThanOrEqual", "LessThan", "LessThanOrEqual", "Equal", "NotEqual"] = "GreaterThan"
    leftType: Literal["PointValue", "PreviousDifference", "AbsolutePreviousDifference", "SampleLagDifference", "TimeLagDifference", "WindowAverageDifference", "WindowRange", "RateOfChange"] = "PointValue"
    constant: Number = ""
    samples: Number = 1
    duration: Number = 60
    tolerance: Number = 5
    window: Number = 300
    timeUnit: Number = 60
    rateReference: Literal["samples", "duration"] = "samples"


class ActionParams(DraftModel):
    level: Literal["", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = None
    content: str | None = Field(default=None, max_length=10000)
    recipients: list[str] | None = Field(default=None, max_length=50)
    subject: str | None = Field(default=None, max_length=200)
    control_id: str | None = Field(default=None, max_length=100)


class ActionDraft(DraftModel):
    action_id: str | None = Field(default=None, max_length=100)
    type: Literal["LogAction", "EmailAction", "SensorControlAction"]
    params: ActionParams

    @model_validator(mode="after")
    def check_params(self):
        allowed = {
            "LogAction": {"level", "content"},
            "EmailAction": {"recipients", "subject", "content"},
            "SensorControlAction": {"control_id"},
        }[self.type]
        if set(self.params.model_dump(exclude_none=True)) - allowed:
            raise ValueError("action has parameters of another action type")
        return self


class RuleFormDraft(DraftModel):
    form: FormFields = Field(default_factory=FormFields)
    sensor_id: str = Field(default="", max_length=100)
    comparisons: list[ComparisonForm] = Field(default_factory=list, max_length=30)
    actions: list[ActionDraft] = Field(default_factory=list, max_length=30)


class GenerateRequest(DraftModel):
    conversation_id: str | None = Field(default=None, max_length=100)
    message: str = Field(min_length=1, max_length=6000)
    current_form: RuleFormDraft = Field(default_factory=RuleFormDraft)


class DraftPatch(DraftModel):
    form: dict = Field(default_factory=dict, description="仅包含需要修改的 FormFields 字段，不变字段省略")
    sensor_id: str | None = None
    comparisons: list[ComparisonForm] | None = None
    actions: list[ActionDraft] | None = None


class ModelSuggestion(DraftModel):
    reply: str = Field(max_length=6000)
    patch: DraftPatch


class SearchQuery(DraftModel):
    keyword: str = Field(default="", max_length=100)
    location_id: str = Field(default="", max_length=100)
    asset_type: Literal["", "building", "floor", "room"] = ""
    unit: str = Field(default="", max_length=10)
    page: int = Field(default=1, ge=1, le=100)
