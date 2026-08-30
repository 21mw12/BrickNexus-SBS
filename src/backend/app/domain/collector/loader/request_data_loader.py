"""API 与 MQTT 共用的 Request 数据处理结构加载器。"""

from sqlalchemy import select

from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.repository.models.AssetTerminal import AssetTerminal
from app.domain.asset.repository.models.SensorPoint import SensorPoint
from app.domain.asset.repository.models.Point import Point
from app.domain.channel.repository.models.Request import Request
from app.infra.DB.SQLConnection import sql_manager


class RequestDataLoader:
    """输入 request_id，返回处理采集结果所需的终端和测点 JSON。"""

    def load(self, request_id: str) -> dict:
        with sql_manager.get_db("main") as db:
            request = db.get(Request, request_id)
            if request is None:
                raise ValueError("request not found")

            terminal_list = db.scalars(
                select(AssetTerminal.asset_id)
                .where(AssetTerminal.request_id == request_id)
                .order_by(AssetTerminal.asset_id)
            ).all()

            point_list = []
            if terminal_list:
                rows = db.execute(
                    select(
                        SensorPoint.point_id,
                        SensorPoint.sensor_id,
                        Asset.asset_id_parent.label("terminal_id"),
                        SensorPoint.json_path,
                        SensorPoint.point_unit.label("unit"),
                        Point.point_description,
                    )
                    .join(Asset, Asset.asset_id == SensorPoint.sensor_id)
                    .join(Point, Point.point_id == SensorPoint.source_point_id)
                    .where(
                        Asset.asset_type == "sensor",
                        Asset.asset_id_parent.in_(terminal_list),
                    )
                    .order_by(
                        Asset.asset_id_parent,
                        SensorPoint.sensor_id,
                        SensorPoint.point_id,
                    )
                ).all()
                point_list = [
                    {
                        "point_id": row.point_id,
                        "sensor_id": row.sensor_id,
                        "terminal_id": row.terminal_id,
                        "json_path": row.json_path,
                        "unit": row.unit,
                        "point_description": row.point_description,
                    }
                    for row in rows
                ]

        return {
            "terminal_list": list(terminal_list),
            "point_list": point_list,
            "time_json_path": request.time_json_path or "",
            "time_parse": request.time_parse or "",
        }


request_data_loader = RequestDataLoader()
