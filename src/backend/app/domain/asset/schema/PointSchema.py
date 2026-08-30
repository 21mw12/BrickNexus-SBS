from pydantic import BaseModel, ConfigDict, Field

from app.domain.asset.repository.models.Point import Point


class PointBaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PointAddSchema(PointBaseSchema):
    point_name: str = Field(min_length=1, max_length=20)
    # 空字符串表示无单位；仍参与 point_name + point_unit 唯一性约束。
    point_unit: str = Field(max_length=10)
    point_description: str | None = Field(default=None, max_length=200)

    def to_model(self) -> Point:
        return Point(
            point_name=self.point_name,
            point_unit=self.point_unit,
            point_description=self.point_description,
        )


class PointUpdateSchema(PointBaseSchema):
    point_description: str | None = Field(max_length=200)


class PointResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    point_id: str
    point_name: str
    point_unit: str
    point_description: str | None = None
