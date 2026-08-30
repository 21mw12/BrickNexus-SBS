"""以 Terminal 为中心保存最新数据快照。"""

import json
from datetime import datetime

from app.infra.Redis.RedisManager import redis_manager


class RedisStorage:
    """每个 Terminal 使用一个 Redis Key，只保存最新状态和测点值。"""

    KEY_PREFIX = "terminal:latest:"
    UPDATE_CHANNEL = "terminal:updates"

    @classmethod
    def key(cls, terminal_id: str) -> str:
        return f"{cls.KEY_PREFIX}{terminal_id}"

    def save(
        self,
        request_data: dict,
        measurements: list[dict],
        sensor_statuses: dict[str, bool],
        terminal_status: bool,
        measurement_time: datetime,
    ) -> list[dict]:
        """构建并覆盖相关 Terminal 的最新快照。"""
        values = {measurement["point_id"]: measurement["value"] for measurement in measurements}
        snapshots = []

        for terminal_id in request_data["terminal_list"]:
            existing = self._get_existing(terminal_id)
            old_sensors = {
                sensor.get("sensor_id"): sensor
                for sensor in existing.get("sensor_list", [])
                if isinstance(sensor, dict)
            }
            sensors: dict[str, dict] = {}

            for point in request_data["point_list"]:
                if point["terminal_id"] != terminal_id:
                    continue
                sensor_id = point["sensor_id"]
                old_sensor = old_sensors.get(sensor_id, {})
                sensor = sensors.setdefault(
                    sensor_id,
                    {
                        "sensor_id": sensor_id,
                        "sensor_status": sensor_statuses.get(
                            sensor_id,
                            bool(old_sensor.get("sensor_status", False)),
                        ),
                        "point_list": [],
                    },
                )
                old_points = {
                    old_point.get("point_id"): old_point
                    for old_point in old_sensor.get("point_list", [])
                    if isinstance(old_point, dict)
                }
                old_point = old_points.get(point["point_id"], {})
                sensor["point_list"].append(
                    {
                        "point_id": point["point_id"],
                        "value": values.get(point["point_id"], old_point.get("value")),
                        "unit": point.get("unit") or "",
                        "point_description": point.get("point_description") or "",
                    }
                )

            snapshot = {
                "terminal_id": terminal_id,
                "terminal_status": terminal_status,
                "sensor_list": list(sensors.values()),
                "time": measurement_time.isoformat(),
            }
            snapshots.append(snapshot)

        # 使用同一个 Redis 事务依次写入快照并发布 Terminal ID。
        # Pub/Sub 收到通知时，对应的最新快照已经可以被 WebSocket 服务读取。
        if snapshots:
            pipeline = redis_manager.pipeline(transaction=True)
            for snapshot in snapshots:
                terminal_id = snapshot["terminal_id"]
                pipeline.set(
                    self.key(terminal_id),
                    json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
                )
                pipeline.publish(self.UPDATE_CHANNEL, terminal_id)
            pipeline.execute()

        return snapshots

    def _get_existing(self, terminal_id: str) -> dict:
        """读取旧快照以保留本次未成功解析的 Point 最新值。"""
        raw = redis_manager.get(self.key(terminal_id))
        if raw is None:
            return {}
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}


redis_storage = RedisStorage()
