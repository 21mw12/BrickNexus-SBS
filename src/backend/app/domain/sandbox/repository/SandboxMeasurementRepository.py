from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models import SandboxMeasurement


class SandboxMeasurementRepository:
    @staticmethod
    def recent_for_points(
        sandbox_id: str,
        point_ids: Sequence[str],
        limit_per_point: int,
        db: Session,
    ) -> list[dict]:
        """Return the most recent rows for each point in ascending tick order."""
        if not point_ids:
            return []
        ranked = (
            select(
                SandboxMeasurement.point_id.label("point_id"),
                SandboxMeasurement.tick.label("tick"),
                SandboxMeasurement.value.label("value"),
                func.row_number().over(
                    partition_by=SandboxMeasurement.point_id,
                    order_by=SandboxMeasurement.tick.desc(),
                ).label("row_number"),
            )
            .where(
                SandboxMeasurement.sandbox_id == sandbox_id,
                SandboxMeasurement.point_id.in_(list(point_ids)),
            )
            .subquery()
        )
        rows = db.execute(
            select(ranked.c.point_id, ranked.c.tick, ranked.c.value)
            .where(ranked.c.row_number <= limit_per_point)
            .order_by(ranked.c.point_id.asc(), ranked.c.tick.asc())
        ).all()
        return [
            {
                "point_id": row.point_id,
                "tick": int(row.tick),
                "value": None if row.value is None else float(row.value),
            }
            for row in rows
        ]

    @staticmethod
    def latest_by_sandbox(sandbox_id: str, db: Session) -> list[dict]:
        latest = (
            select(
                SandboxMeasurement.point_id.label("point_id"),
                func.max(SandboxMeasurement.tick).label("tick"),
            )
            .where(SandboxMeasurement.sandbox_id == sandbox_id)
            .group_by(SandboxMeasurement.point_id)
            .subquery()
        )
        rows = db.execute(
            select(SandboxMeasurement)
            .join(
                latest,
                (SandboxMeasurement.point_id == latest.c.point_id)
                & (SandboxMeasurement.tick == latest.c.tick),
            )
            .where(SandboxMeasurement.sandbox_id == sandbox_id)
            .order_by(SandboxMeasurement.point_id.asc())
        ).scalars().all()
        return [{
            "point_id": row.point_id,
            "tick": int(row.tick),
            "value": None if row.value is None else float(row.value),
        } for row in rows]

    @staticmethod
    def upsert_many(rows: Sequence[Mapping[str, Any]], db: Session) -> int:
        values = [dict(row) for row in rows]
        if not values:
            return 0
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            statement = pg_insert(SandboxMeasurement).values(values)
            statement = statement.on_conflict_do_update(
                index_elements=[
                    SandboxMeasurement.sandbox_id,
                    SandboxMeasurement.point_id,
                    SandboxMeasurement.tick,
                ],
                set_={"value": statement.excluded.value},
            )
            db.execute(statement)
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            statement = sqlite_insert(SandboxMeasurement).values(values)
            statement = statement.on_conflict_do_update(
                index_elements=[
                    SandboxMeasurement.sandbox_id,
                    SandboxMeasurement.point_id,
                    SandboxMeasurement.tick,
                ],
                set_={"value": statement.excluded.value},
            )
            db.execute(statement)
        else:
            for row in values:
                key = (row["sandbox_id"], row["point_id"], row["tick"])
                current = db.get(SandboxMeasurement, key)
                if current is None:
                    db.add(SandboxMeasurement(**row))
                else:
                    current.value = row["value"]
        db.flush()
        return len(values)

    @staticmethod
    def stream_full(
        sandbox_id: str,
        point_id: str,
        start_tick: int,
        end_tick: int,
        db: Session,
        batch_size: int = 1000,
    ) -> tuple[int, Iterator[tuple[int, float | None]]]:
        statement = (
            select(
                SandboxMeasurement.tick,
                SandboxMeasurement.value,
                func.count().over().label("raw_count"),
            )
            .where(
                SandboxMeasurement.sandbox_id == sandbox_id,
                SandboxMeasurement.point_id == point_id,
                SandboxMeasurement.tick >= start_tick,
                SandboxMeasurement.tick < end_tick,
            )
            .order_by(SandboxMeasurement.tick.asc())
            .execution_options(stream_results=True, yield_per=batch_size)
        )
        result = db.execute(statement)
        first = result.fetchone()
        if first is None:
            result.close()
            return 0, iter(())
        count = int(first.raw_count)

        def iterator():
            try:
                yield int(first.tick), (
                    None if first.value is None else float(first.value)
                )
                for row in result:
                    yield int(row.tick), (
                        None if row.value is None else float(row.value)
                    )
            finally:
                result.close()

        return count, iterator()

    @staticmethod
    def stream_sandbox(
        sandbox_id: str, db: Session, batch_size: int = 1000
    ) -> Iterator[SandboxMeasurement]:
        return db.scalars(
            select(SandboxMeasurement)
            .where(SandboxMeasurement.sandbox_id == sandbox_id)
            .order_by(
                SandboxMeasurement.tick.asc(), SandboxMeasurement.point_id.asc()
            )
            .execution_options(stream_results=True, yield_per=batch_size)
        )

    @staticmethod
    def has_null(
        sandbox_id: str,
        point_id: str,
        start_tick: int,
        end_tick: int,
        db: Session,
    ) -> bool:
        return bool(db.scalar(select(exists().where(
            SandboxMeasurement.sandbox_id == sandbox_id,
            SandboxMeasurement.point_id == point_id,
            SandboxMeasurement.tick >= start_tick,
            SandboxMeasurement.tick < end_tick,
            SandboxMeasurement.value.is_(None),
        ))))
