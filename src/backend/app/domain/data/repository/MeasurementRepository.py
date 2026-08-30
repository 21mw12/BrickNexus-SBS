"""测量数据持久化仓储。"""

from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domain.data.repository.models.Measurement import Measurement


class MeasurementRepository:
    """以 ``(point_id, time)`` 为键写入测量值。"""

    @staticmethod
    def _to_row(item: Measurement | Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(item, Measurement):
            return {"point_id": item.point_id, "time": item.time, "value": item.value}
        return {"point_id": item["point_id"], "time": item["time"], "value": item["value"]}

    def upsert_many(
        self,
        measurements: Sequence[Measurement | Mapping[str, Any]],
        db: Session,
    ) -> int:
        """批量 UPSERT，并返回输入记录数。

        PostgreSQL 使用原生 ``ON CONFLICT``。SQLite 分支只用于仓储单元测试；
        其他方言退化为按复合主键更新，保证调用方仍有一致语义。
        """
        rows = [self._to_row(item) for item in measurements]
        if not rows:
            return 0

        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            stmt = pg_insert(Measurement).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=[Measurement.point_id, Measurement.time],
                set_={"value": stmt.excluded.value},
            )
            db.execute(stmt)
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            stmt = sqlite_insert(Measurement).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=[Measurement.point_id, Measurement.time],
                set_={"value": stmt.excluded.value},
            )
            db.execute(stmt)
        else:
            for row in rows:
                existing = db.get(Measurement, (row["point_id"], row["time"]))
                if existing is None:
                    db.add(Measurement(**row))
                else:
                    existing.value = row["value"]

        db.flush()
        return len(rows)

    def get(self, point_id: str, measurement_time: datetime, db: Session) -> Measurement | None:
        """按复合主键读取一条测量记录。"""
        return db.get(Measurement, (point_id, measurement_time))

    def stream_history(
        self,
        point_id: str,
        start_time: datetime,
        end_time: datetime,
        db: Session,
        batch_size: int = 1000,
    ) -> tuple[int, Iterator[tuple[datetime, float]]]:
        """流式读取 ``[start_time, end_time)`` 内的有序数据及其稳定总数。

        总数使用窗口函数随同数据在同一条 SQL 中返回，保证计数与数据来自
        同一个数据库语句快照，不受采集器并发写入影响。
        """
        statement = (
            select(
                Measurement.time,
                Measurement.value,
                func.count().over().label("raw_count"),
            )
            .where(
                Measurement.point_id == point_id,
                Measurement.time >= start_time,
                Measurement.time < end_time,
            )
            .order_by(Measurement.time.asc())
            .execution_options(stream_results=True, yield_per=batch_size)
        )
        result = db.execute(statement)
        first = result.fetchone()
        if first is None:
            result.close()
            return 0, iter(())

        raw_count = int(first.raw_count)

        def iter_points() -> Iterator[tuple[datetime, float]]:
            try:
                yield first.time, float(first.value)
                for row in result:
                    yield row.time, float(row.value)
            finally:
                result.close()

        return raw_count, iter_points()
