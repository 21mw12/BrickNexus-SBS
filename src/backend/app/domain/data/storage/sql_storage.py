"""measurement 表持久化。"""

from app.domain.data.repository.MeasurementRepository import MeasurementRepository
from app.infra.DB.SQLConnection import sql_manager


class SqlStorage:
    """将解析成功的测点数据批量 UPSERT 到 measurement 表。"""

    def __init__(self) -> None:
        self.repository = MeasurementRepository()

    def save(self, measurements: list[dict]) -> int:
        """只保留 measurement 表需要的 point_id、time 和 value。"""
        rows = [
            {
                "point_id": measurement["point_id"],
                "time": measurement["time"],
                "value": measurement["value"],
            }
            for measurement in measurements
        ]
        with sql_manager.get_db("main") as db:
            return self.repository.upsert_many(rows, db)


sql_storage = SqlStorage()
