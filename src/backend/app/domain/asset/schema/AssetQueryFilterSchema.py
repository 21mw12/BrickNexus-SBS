from typing import Union, Literal
from pydantic import BaseModel, ConfigDict

class AssetBaseQuerySchame(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    name: str | None = None
    is_use: bool | None = None

class EmptyFilterSchema(BaseModel):
    """空过滤条件，匹配 {} 或无 asset_type 时的兜底"""

    model_config = ConfigDict(
        extra="ignore"
    )

    name: str | None = None
    is_use: bool | None = None
    asset_type: str | None = None

class BuildingQuerySchema(AssetBaseQuerySchame):
    asset_type: Literal["building"]
    number: str | None = None
    address: str | None = None

class FloorQuerySchema(AssetBaseQuerySchame):
    asset_type: Literal["floor"]
    level: str | None = None

class RoomQuerySchema(AssetBaseQuerySchame):
    asset_type: Literal["room"]
    number: str | None = None
    room_purpose: str | None = None
    max_current: str | None = None
    manager_name: str | None = None

class TerminalQuerySchema(AssetBaseQuerySchame):
    asset_type: Literal["terminal"]
    number: str | None = None
    model: str | None = None
    location: str | None = None
    iot_number: str | None = None
    iot_activate_human: str | None = None
    is_online: bool | None = None

class SensorQuerySchema(AssetBaseQuerySchame):
    asset_type: Literal["sensor"]
    model_id: str | None = None
    is_online: bool | None = None


AssetQueryFilterSchema = Union[
    EmptyFilterSchema,
    BuildingQuerySchema,
    FloorQuerySchema,
    RoomQuerySchema,
    TerminalQuerySchema,
    SensorQuerySchema
]
