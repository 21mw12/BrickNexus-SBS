"""API 与 MQTT 共用的 Terminal/Sensor 状态更新。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import update

from app.domain.asset.repository.models.AssetSensor import AssetSensor
from app.domain.asset.repository.models.AssetTerminal import AssetTerminal
from app.infra.DB.SQLConnection import sql_manager
from app.core.config.ConfigLoader import config

from .redis_storage import redis_storage


class StatusStorage:
    """使用批量 UPDATE 写状态，不先查询每个资产的当前状态。"""

    default_timezone = ZoneInfo(config.time.default_timezone)

    @staticmethod
    def update_online_statuses(
        terminal_ids: list[str],
        sensor_statuses: dict[str, bool],
        measurement_time: datetime,
    ) -> None:
        """按测量时间更新 Terminal 及解析成功 Sensor 的最后接收时间。"""
        online_sensor_ids = [sensor_id for sensor_id, value in sensor_statuses.items() if value]
        offline_sensor_ids = [sensor_id for sensor_id, value in sensor_statuses.items() if not value]

        with sql_manager.get_db("main") as db:
            if terminal_ids:
                db.execute(
                    update(AssetTerminal)
                    .where(AssetTerminal.asset_id.in_(terminal_ids))
                    .values(is_online=True, last_receive_time=measurement_time)
                )
            if online_sensor_ids:
                db.execute(
                    update(AssetSensor)
                    .where(AssetSensor.asset_id.in_(online_sensor_ids))
                    .values(is_online=True, last_receive_time=measurement_time)
                )
            if offline_sensor_ids:
                db.execute(
                    update(AssetSensor)
                    .where(AssetSensor.asset_id.in_(offline_sensor_ids))
                    .values(is_online=False)
                )

    @staticmethod
    def set_all_offline(request_data: dict, status_time: datetime | None = None) -> None:
        """将一个 Request 下的全部 Terminal/Sensor 批量设为离线并刷新 Redis。"""
        terminal_ids = request_data["terminal_list"]
        sensor_ids = list({point["sensor_id"] for point in request_data["point_list"]})

        with sql_manager.get_db("main") as db:
            if terminal_ids:
                db.execute(
                    update(AssetTerminal)
                    .where(AssetTerminal.asset_id.in_(terminal_ids))
                    .values(is_online=False)
                )
            if sensor_ids:
                db.execute(
                    update(AssetSensor)
                    .where(AssetSensor.asset_id.in_(sensor_ids))
                    .values(is_online=False)
                )

        redis_storage.save(
            request_data,
            measurements=[],
            sensor_statuses={sensor_id: False for sensor_id in sensor_ids},
            terminal_status=False,
            measurement_time=status_time or datetime.now(StatusStorage.default_timezone),
        )


status_storage = StatusStorage()
