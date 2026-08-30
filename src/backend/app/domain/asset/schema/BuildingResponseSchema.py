from pydantic import BaseModel, ConfigDict
from typing import Optional, Any


class BuildingResponseSchema(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    asset_id: str
    asset_id_parent: Optional[str] = None
    asset_type: Optional[str] = None
    name: Optional[str] = None
    floor_count: int = 0
    room_count: int = 0
    terminal_count: int = 0
    sensor_count: int = 0
    is_use: bool = False
    asset_parent_name: Optional[str] = None

    # Building specific
    number: Optional[str] = None
    address: Optional[str] = None

    @classmethod
    def from_models(cls, asset_model: Any, building_model: Any, parent_name: str | None = None, sensor_model_info: Any = None, points: Any = None, sensor_points: Any = None):
        """ 从 ORM 模型构建响应对象 """
        def _get(m, k, default=None):
            if m is None:
                return default
            if isinstance(m, dict):
                return m.get(k, default)
            return getattr(m, k, default)

        return cls(
            asset_id=_get(asset_model, "asset_id"),
            asset_id_parent=_get(asset_model, "asset_id_parent"),
            asset_type=_get(asset_model, "asset_type"),
            name=_get(asset_model, "name"),
            floor_count=_get(asset_model, "floor_count", 0) or 0,
            room_count=_get(asset_model, "room_count", 0) or 0,
            terminal_count=_get(asset_model, "terminal_count", 0) or 0,
            sensor_count=_get(asset_model, "sensor_count", 0) or 0,
            is_use=_get(asset_model, "is_use", False) or False,
            asset_parent_name=parent_name,
            number=_get(building_model, "number"),
            address=_get(building_model, "address"),
        )