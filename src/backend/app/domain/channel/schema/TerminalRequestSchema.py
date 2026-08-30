"""采集通道与终端、测点绑定的配置结构。"""

from typing import List
from pydantic import BaseModel


class PointEditItem(BaseModel):
    """测点编辑项"""
    point_id: str | None = None
    json_path: str | None = None


class TerminalTreeEditSchema(BaseModel):
    """终端测点树编辑请求"""
    request_id: str | None = None
    points: List[PointEditItem] = []
