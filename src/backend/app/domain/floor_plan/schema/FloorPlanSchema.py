"""楼层平面图领域的接口数据结构。"""

from pydantic import BaseModel, ConfigDict, Field


class FloorRoomRegionItemSchema(BaseModel):
    """一个房间在原始平面图上的矩形坐标。"""

    model_config = ConfigDict(extra="forbid")

    room_id: str = Field(min_length=1, max_length=100)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class FloorRoomRegionSaveSchema(BaseModel):
    """以楼层为中心批量覆盖当前全部房间标记。"""

    model_config = ConfigDict(extra="forbid")

    regions: list[FloorRoomRegionItemSchema] = Field(default_factory=list)
