from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.core.data_processing import TimeSeriesProcessor
from app.domain.sandbox.repository import SandboxMeasurementRepository
from app.domain.sandbox.repository.models import Sandbox
from app.domain.sandbox.schema import SandboxDataQuerySchema, SandboxRawQuerySchema


def sandbox_point_ids(config: dict) -> set[str]:
    return {
        str(point["id"])
        for terminal in config.get("terminals", [])
        for sensor in terminal.get("sensors", [])
        for point in sensor.get("points", [])
    }


class SandboxDataService:
    def __init__(self, repository: SandboxMeasurementRepository | None = None):
        self.repository = repository or SandboxMeasurementRepository()

    def stream_full(
        self,
        sandbox_id: str,
        point_id: str,
        start_tick: int,
        end_tick: int,
        db: Session,
    ) -> tuple[int, Iterator[tuple[int, float | None]]]:
        return self.repository.stream_full(
            sandbox_id, point_id, start_tick, end_tick, db
        )

    @staticmethod
    def _validate(sandbox_id: str, point_ids: list[str], db: Session) -> Sandbox:
        row = db.get(Sandbox, sandbox_id)
        if row is None:
            raise ValidationError("sandbox not found")
        known = sandbox_point_ids(row.config)
        if any(point_id not in known for point_id in point_ids):
            raise ValidationError("point does not belong to sandbox")
        return row

    def query_raw(
        self, sandbox_id: str, data: SandboxRawQuerySchema, db: Session
    ) -> dict:
        self._validate(sandbox_id, data.point_ids, db)
        points = []
        for point_id in data.point_ids:
            count, stream = self.stream_full(
                sandbox_id, point_id, data.start_tick, data.end_tick, db
            )
            try:
                rows = TimeSeriesProcessor.raw(stream)
            finally:
                close = getattr(stream, "close", None)
                if close is not None:
                    close()
            points.append({
                "point_id": point_id,
                "original_count": count,
                "returned_count": len(rows),
                "ticks": [item[0] for item in rows],
                "values": [item[1] for item in rows],
            })
        return {
            "start_tick": data.start_tick,
            "end_tick": data.end_tick,
            "points": points,
        }

    def query_sampled(
        self, sandbox_id: str, data: SandboxDataQuerySchema, db: Session
    ) -> dict:
        self._validate(sandbox_id, data.point_ids, db)
        results = []
        for point_id in data.point_ids:
            count, stream = self.stream_full(
                sandbox_id, point_id, data.start_tick, data.end_tick, db
            )
            try:
                if data.method == "fixed_interval":
                    selected = TimeSeriesProcessor.fixed_interval(
                        stream,
                        float(data.interval_ticks),
                        data.aggregation,
                        data.start_tick,
                    )
                elif self.repository.has_null(
                    sandbox_id,
                    point_id,
                    data.start_tick,
                    data.end_tick,
                    db,
                ):
                    selected = TimeSeriesProcessor.lttb_with_gaps(
                        list(stream), data.sample_count
                    )
                else:
                    selected = TimeSeriesProcessor.lttb(
                        ((tick, float(value)) for tick, value in stream),
                        count,
                        data.sample_count,
                    )
            finally:
                close = getattr(stream, "close", None)
                if close is not None:
                    close()
            results.append({
                "point_id": point_id,
                "original_count": count,
                "returned_count": len(selected),
                "downsampled": data.method == "lttb" and count > len(selected),
                "ticks": [item[0] for item in selected],
                "values": [item[1] for item in selected],
            })
        return {
            "start_tick": data.start_tick,
            "end_tick": data.end_tick,
            "method": data.method,
            "points": results,
        }


sandbox_data_service = SandboxDataService()
