from pydantic import BaseModel, ConfigDict
from typing import Optional, Any, List
from datetime import datetime


class SensorResponseSchema(BaseModel):

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
    is_online: bool = False
    asset_parent_name: Optional[str] = None

    # Sensor specific
    sensor_type: Optional[str] = None
    model_name: Optional[str] = None
    last_receive_time: Optional[datetime] = None
    points: List[dict] = []
    sensor_points: List[dict] = []

    @classmethod
    def from_models(cls, asset_model: Any, sensor_model: Any, sensor_model_info: Any = None, points: List[Any] | None = None, sensor_points: List[Any] | None = None, parent_name: str | None = None):
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
            is_online=_get(sensor_model, "is_online", False) or False,
            asset_parent_name=parent_name,
            sensor_type=_get(sensor_model_info, "sensor_type"),
            model_name=_get(sensor_model_info, "model_name"),
            last_receive_time=_get(sensor_model, "last_receive_time"),
            points=[
                {
                    "point_id": p.point_id,
                    "point_name": p.point_name,
                    "point_unit": p.point_unit,
                    "point_description": p.point_description,
                }
                for p in points
            ] if points else [],
            sensor_points=[
                {
                    "point_id": sp.point_id,
                    "source_model_id": sp.source_model_id,
                    "source_point_id": sp.source_point_id,
                    "point_name": sp.point_name,
                    "point_unit": sp.point_unit,
                    "point_description": sp.point_description,
                    "json_path": sp.json_path,
                }
                for sp in sensor_points
            ] if sensor_points else [],
        )
