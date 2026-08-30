from typing import Union, Literal
from pydantic import BaseModel, ConfigDict


class AssetBaseUpdateSchame(BaseModel):

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    is_use: bool | None = None
    is_use_all: bool | None = False
    asset_id_parent: str | None = None


class BuildingUpdateSchema(AssetBaseUpdateSchame):
    asset_type: Literal["building"]
    number: str | None = None
    address: str | None = None


class FloorUpdateSchema(AssetBaseUpdateSchame):
    asset_type: Literal["floor"]
    level: str | None = None


class RoomUpdateSchema(AssetBaseUpdateSchame):
    asset_type: Literal["room"]
    number: str | None = None
    room_purpose: str | None = None
    max_current: str | None = None
    manager_name: str | None = None


class TerminalUpdateSchema(AssetBaseUpdateSchame):
    asset_type: Literal["terminal"]
    request_id: str | None = None
    number: str | None = None
    model: str | None = None
    location: str | None = None
    iot_number: str | None = None
    iot_activate_human: str | None = None


class SensorUpdateSchema(AssetBaseUpdateSchame):
    asset_type: Literal["sensor"]


AssetUpdateSchema = Union[
    BuildingUpdateSchema,
    FloorUpdateSchema,
    RoomUpdateSchema,
    TerminalUpdateSchema,
    SensorUpdateSchema
]
