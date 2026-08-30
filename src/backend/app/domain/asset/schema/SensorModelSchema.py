from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from app.domain.asset.repository.models.SensorModel import SensorModel
from app.domain.asset.repository.models.ModelPoint import ModelPoint


class SensorModelBaseSchema(BaseModel):
    """ 传感器型号基础 Schema """
    model_config = ConfigDict(extra="forbid")


class ModelPointItemSchema(BaseModel):
    """新增传感器型号时选择的全局测点。"""

    model_config = ConfigDict(extra="forbid")

    point_id: str


class ModelPointResponseSchema(BaseModel):
    """ 查询时的测点信息 """
    model_config = ConfigDict(from_attributes=True)

    point_id: str
    point_name: Optional[str] = None
    point_unit: Optional[str] = None
    point_description: Optional[str] = None

    @classmethod
    def from_model(cls, point: ModelPoint):
        return cls(
            point_id=point.point_id,
            point_name=point.point_name,
            point_unit=point.point_unit,
            point_description=point.point_description,
        )


class SensorModelAddSchema(SensorModelBaseSchema):
    """ 新增传感器型号（model_id 自动生成）"""
    sensor_type: str | None = None
    model_name: str | None = None
    remark: str | None = None
    points: List[ModelPointItemSchema] | None = None

    def to_model(self) -> SensorModel:
        return SensorModel(
            sensor_type=self.sensor_type,
            model_name=self.model_name,
            remark=self.remark,
        )


class SensorModelUpdateSchema(SensorModelBaseSchema):
    """更新传感器型号基本信息；测点绑定创建后不可修改。"""
    sensor_type: str | None = None
    model_name: str | None = None
    remark: str | None = None


class SensorModelResponseSchema(BaseModel):
    """ 传感器型号响应 """
    model_config = ConfigDict(from_attributes=True)

    model_id: str
    sensor_type: Optional[str] = None
    model_name: Optional[str] = None
    remark: Optional[str] = None
    points: List[ModelPointResponseSchema] = Field(default_factory=list)

    @classmethod
    def from_model(cls, model: SensorModel, points: List[ModelPoint] | None = None):
        return cls(
            model_id=model.model_id,
            sensor_type=model.sensor_type,
            model_name=model.model_name,
            remark=model.remark,
            points=[ModelPointResponseSchema.from_model(p) for p in points] if points else [],
        )
