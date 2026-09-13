from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ShortEvidence = Annotated[str, Field(min_length=1, max_length=300)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_default=True)


class AnalysisAgentRequest(StrictModel):
    analysis_id: str = Field(min_length=1, max_length=100)
    conversation_id: str | None = Field(default=None, max_length=100)
    message: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_message(self):
        if self.message is not None:
            self.message = self.message.strip()
        if self.conversation_id and not self.message:
            raise ValueError("后续追问不能为空")
        return self


class InterpretationItem(StrictModel):
    title: str = Field(min_length=1, max_length=100)
    statement: str = Field(min_length=1, max_length=800)
    evidence: list[ShortEvidence] = Field(default_factory=list, max_length=6)
    confidence: Literal["high", "medium", "low"]


class AnalysisInterpretation(StrictModel):
    overview: str = Field(min_length=1, max_length=1200)
    findings: list[InterpretationItem] = Field(default_factory=list, max_length=8)
    inferences: list[InterpretationItem] = Field(default_factory=list, max_length=6)
    cautions: list[ShortEvidence] = Field(default_factory=list, max_length=8)
    recommended_checks: list[ShortEvidence] = Field(default_factory=list, max_length=8)
    limitations: list[ShortEvidence] = Field(default_factory=list, max_length=6)


class ReportAgentOutput(StrictModel):
    response_type: Literal["report"] = "report"
    report: AnalysisInterpretation
    reply: None = None


class AnswerAgentOutput(StrictModel):
    response_type: Literal["answer"] = "answer"
    report: None = None
    reply: str = Field(min_length=1, max_length=4000)
