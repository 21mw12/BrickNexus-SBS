from datetime import date

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LogQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["rule_action", "rule_operation"] | None = None
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = None
    operator: str | None = Field(default=None, max_length=30)
    time: date | None = None
