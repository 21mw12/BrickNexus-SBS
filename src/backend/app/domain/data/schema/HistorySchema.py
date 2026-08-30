"""历史数据查询请求模型。"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HistoryQuerySchema(BaseModel):
    """多测点共享时间范围和采样数量的历史查询。"""

    model_config = ConfigDict(extra="forbid")

    point_ids: list[str] = Field(min_length=1, max_length=10)
    start_time: str
    end_time: str
    sample_count: int = Field(ge=100, le=1000)

    @field_validator("point_ids")
    @classmethod
    def normalize_point_ids(cls, point_ids: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for point_id in point_ids:
            if not isinstance(point_id, str) or not point_id.strip():
                raise ValueError("each point_id must be a non-empty string")
            point_id = point_id.strip()
            if point_id not in seen:
                seen.add(point_id)
                normalized.append(point_id)
        return normalized
