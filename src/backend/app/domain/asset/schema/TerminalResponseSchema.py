from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from datetime import datetime


class TerminalResponseSchema(BaseModel):

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

    # Terminal specific
    request_id: Optional[str] = None
    number: Optional[str] = None
    model: Optional[str] = None
    location: Optional[str] = None
    iot_number: Optional[str] = None
    iot_activate_human: Optional[str] = None
    last_receive_time: Optional[datetime] = None
    time_json_path: Optional[str] = None
    time_parse: Optional[str] = None

    @classmethod
    def from_models(cls, asset_model: Any, terminal_model: Any, parent_name: str | None = None, sensor_model_info: Any = None, points: Any = None, sensor_points: Any = None):
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
            is_online=_get(terminal_model, "is_online", False) or False,
            asset_parent_name=parent_name,
            request_id=_get(terminal_model, "request_id"),
            number=_get(terminal_model, "number"),
            model=_get(terminal_model, "model"),
            location=_get(terminal_model, "location"),
            iot_number=_get(terminal_model, "iot_number"),
            iot_activate_human=_get(terminal_model, "iot_activate_human"),
            last_receive_time=_get(terminal_model, "last_receive_time"),
            time_json_path=_get(terminal_model, "time_json_path"),
            time_parse=_get(terminal_model, "time_parse"),
        )
