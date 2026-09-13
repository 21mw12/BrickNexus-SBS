"""Shared schemas for point time-series queries."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PointTimeRangeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    point_ids: list[str] = Field(min_length=1, max_length=10)
    start_time: str
    end_time: str

    @field_validator("point_ids")
    @classmethod
    def normalize_point_ids(cls, point_ids: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in point_ids:
            if not isinstance(value, str) or not value.strip():
                raise ValueError("each point_id must be a non-empty string")
            point_id = value.strip()
            if point_id not in seen:
                seen.add(point_id)
                normalized.append(point_id)
        return normalized


class SampledPointTimeRangeSchema(PointTimeRangeSchema):
    sample_count: int = Field(ge=100, le=1000)
