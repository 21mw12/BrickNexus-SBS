from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.data.schema.TimeSeriesQuerySchema import SampledPointTimeRangeSchema


class PreprocessingSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aggregation: Literal["mean", "min", "max", "first", "last"] = "mean"
    missing_strategy: Literal["drop", "interpolate", "forward_fill", "reject"] = "interpolate"
    max_gap: int = Field(default=3, ge=1, le=20)


class AlgorithmSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=50)
    mode: Literal["per_point", "joint"] = "per_point"
    parameters: dict[str, Any] = Field(default_factory=dict)


class AnalyticsRequest(SampledPointTimeRangeSchema):
    analysis_type: Literal["anomaly", "clustering", "forecasting"]
    preprocessing: PreprocessingSchema = Field(default_factory=PreprocessingSchema)
    algorithm: AlgorithmSchema

    @model_validator(mode="after")
    def validate_task_shape(self):
        if self.analysis_type == "clustering" and len(self.point_ids) < 2:
            raise ValueError("clustering requires at least two points")
        if self.algorithm.mode == "joint" and len(self.point_ids) < 2:
            raise ValueError("joint analysis requires at least two points")
        return self


class AnomalyAnalyticsRequest(AnalyticsRequest):
    analysis_type: Literal["anomaly"]


class ClusteringAnalyticsRequest(AnalyticsRequest):
    analysis_type: Literal["clustering"]


class ForecastingAnalyticsRequest(AnalyticsRequest):
    analysis_type: Literal["forecasting"]


AnalyticsRunRequest = Annotated[
    AnomalyAnalyticsRequest | ClusteringAnalyticsRequest | ForecastingAnalyticsRequest,
    Field(discriminator="analysis_type"),
]
