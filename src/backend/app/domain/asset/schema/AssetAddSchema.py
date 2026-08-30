from typing import Union, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.domain.asset.repository.models import *


# ==========================================================
# 基类
# ==========================================================
class AssetBaseAddSchame(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    name: str
    is_use: bool
    asset_id_parent: str | None = None

    def to_asset_model(self):
        """ 转换为 Asset 对象 """
        return Asset(
            asset_type=self.asset_type,
            name=self.name,
            asset_id_parent=self.asset_id_parent,
            is_use=self.is_use,
        )

    def to_type_model(self, asset_id: str):
        """ 转换为具体的 Asset 类型对象 """
        raise NotImplementedError


# ==========================================================
# 具体属性子类
# ==========================================================

class BuildingAddSchema(AssetBaseAddSchame):
    asset_type: Literal["building"]
    number: str | None = None
    address: str | None = None

    def to_type_model(self, asset_id: str):
        return AssetBuilding(
            asset_id=asset_id,
            number=self.number,
            address=self.address,
        )

class FloorAddSchema(AssetBaseAddSchame):
    asset_type: Literal["floor"]
    level: str | None = None

    def to_type_model(self, asset_id: str):
        return AssetFloor(
            asset_id=asset_id,
            level=self.level,
        )

class RoomAddSchema(AssetBaseAddSchame):
    asset_type: Literal["room"]
    number: str | None = None
    room_purpose: str | None = None
    max_current: str | None = None
    manager_name: str | None = None

    def to_type_model(self, asset_id: str):
        return AssetRoom(
            asset_id=asset_id,
            number=self.number,
            room_purpose=self.room_purpose,
            max_current=self.max_current,
            manager_name=self.manager_name,
        )

class TerminalAddSchema(AssetBaseAddSchame):
    asset_type: Literal["terminal"]
    request_id: str | None = None
    number: str | None = None
    model: str | None = None
    location: str | None = None
    iot_number: str | None = None
    iot_activate_human: str | None = None
    last_receive_time: datetime | None = None

    def to_type_model(self, asset_id: str):
        return AssetTerminal(
            asset_id=asset_id,
            request_id=self.request_id,
            number=self.number,
            model=self.model,
            location=self.location,
            iot_number=self.iot_number,
            iot_activate_human=self.iot_activate_human,
            last_receive_time=self.last_receive_time,
        )

class SensorAddSchema(AssetBaseAddSchame):
    asset_type: Literal["sensor"]
    model_id: str | None = None

    def to_type_model(self, asset_id: str):
        return AssetSensor(
            asset_id=asset_id,
            model_id=self.model_id,
        )

AssetAddSchema = Union[
    BuildingAddSchema,
    FloorAddSchema,
    RoomAddSchema,
    TerminalAddSchema,
    SensorAddSchema
]
