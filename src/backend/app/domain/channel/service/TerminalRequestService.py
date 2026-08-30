from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.repository.models.AssetTerminal import AssetTerminal
from app.domain.asset.repository.SensorPointRepository import SensorPointRepository
from app.domain.channel.schema.TerminalRequestSchema import TerminalTreeEditSchema
from app.domain.channel.repository.models.Request import Request


class TerminalRequestService:

    @staticmethod
    def get_tree(terminal_id: str, db: Session) -> Dict[str, Any]:
        """ 查询终端 → 传感器 → 测点树 """
        terminal = db.get(Asset, terminal_id)
        if terminal is None or terminal.asset_type != "terminal":
            raise ValidationError("terminal not found")

        terminal_attr = db.get(AssetTerminal, terminal_id)

        # 从关联的 Request 获取时间解析相关字段
        request = None
        if terminal_attr and terminal_attr.request_id:
            request = db.get(Request, terminal_attr.request_id)

        sensors = db.execute(
            select(Asset).where(
                Asset.asset_id_parent == terminal_id,
                Asset.asset_type == "sensor",
            )
        ).scalars().all()

        point_repo = SensorPointRepository()
        sensor_list = []
        for s in sensors:
            points = point_repo.get_by_sensor_id(s.asset_id, db)
            sensor_list.append({
                "sensor_id": s.asset_id,
                "sensor_name": s.name,
                "points": [
                    {
                        "point_id": p.point_id,
                        "source_model_id": p.source_model_id,
                        "source_point_id": p.source_point_id,
                        "point_name": p.point_name,
                        "point_unit": p.point_unit,
                        "point_description": p.point_description,
                        "json_path": p.json_path,
                    }
                    for p in points
                ],
            })

        return {
            "terminal_id": terminal.asset_id,
            "terminal_name": terminal.name,
            "request_id": terminal_attr.request_id if terminal_attr else None,
            "last_receive_time": terminal_attr.last_receive_time if terminal_attr else None,
            "time_json_path": request.time_json_path if request else None,
            "time_format": request.time_format if request else None,
            "sensors": sensor_list,
        }

    @staticmethod
    def _get_valid_point_ids(terminal_id: str, db: Session) -> set:
        """ 收集终端下所有传感器的所有测点 ID """
        point_repo = SensorPointRepository()
        sensors = db.execute(
            select(Asset).where(
                Asset.asset_id_parent == terminal_id,
                Asset.asset_type == "sensor",
            )
        ).scalars().all()

        valid_ids = set()
        for s in sensors:
            for p in point_repo.get_by_sensor_id(s.asset_id, db):
                valid_ids.add(p.point_id)
        return valid_ids

    @staticmethod
    def update_tree(terminal_id: str, update_data: TerminalTreeEditSchema, db: Session) -> Dict[str, Any]:
        """ 更新终端 request_id 和测点 json_path """
        terminal = db.get(Asset, terminal_id)
        if terminal is None or terminal.asset_type != "terminal":
            raise ValidationError("terminal not found")

        terminal_attr = db.get(AssetTerminal, terminal_id)

        if terminal_attr is None:
            raise ValidationError("terminal attributes not found")

        # 运行中的 Request 使用的是启动时缓存，禁止修改绑定和 Point JSONPath。
        current_request = (
            db.get(Request, terminal_attr.request_id)
            if terminal_attr.request_id
            else None
        )
        if current_request is not None and current_request.is_active:
            if "request_id" in update_data.model_fields_set or update_data.points:
                raise ValidationError("terminal bound to a running request cannot be edited")

        # 1. 更新终端的 request_id。model_fields_set 用于区分“不修改”和显式解绑。
        if "request_id" in update_data.model_fields_set:
            target_request_id = update_data.request_id
            if target_request_id is not None:
                target_request = db.get(Request, target_request_id)
                if target_request is None:
                    raise ValidationError("request not found")
                if target_request.is_active:
                    raise ValidationError("terminal cannot bind to a running request")
            terminal_attr.request_id = target_request_id
            db.add(terminal_attr)

        # 2. 更新测点 json_path（校验归属）
        if update_data.points:
            valid_ids = TerminalRequestService._get_valid_point_ids(terminal_id, db)
            point_repo = SensorPointRepository()
            for p in update_data.points:
                if not p.point_id:
                    continue
                if p.point_id not in valid_ids:
                    raise ValidationError(f"point {p.point_id} does not belong to this terminal")
                if p.json_path is not None:
                    point_repo.update(p.point_id, {"json_path": p.json_path}, db=db)

        return TerminalRequestService.get_tree(terminal_id, db)
