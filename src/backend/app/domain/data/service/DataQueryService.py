"""真实测点的全量流式读取服务。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.data.repository.MeasurementRepository import MeasurementRepository
from app.domain.data.schema.HistorySchema import RawHistoryQuerySchema
from app.domain.data.service.TimeRangeService import time_range_service


class DataQueryService:
    """为 API、沙盒基准和未来分析代码提供未经采样的数据。"""

    def __init__(self, repository: MeasurementRepository | None = None) -> None:
        self.repository = repository or MeasurementRepository()

    def stream_full(
        self,
        point_id: str,
        start_time: datetime,
        end_time: datetime,
        db: Session,
    ) -> tuple[int, Iterator[tuple[datetime, float | None]]]:
        return self.repository.stream_history(point_id, start_time, end_time, db)

    def query_raw(
        self,
        data: RawHistoryQuerySchema,
        db: Session,
        now: datetime | None = None,
    ) -> dict:
        resolved = time_range_service.resolve(
            data, now, require_start_alignment=False, require_min_range=False
        )
        business_timezone = resolved["business_timezone"]
        start = resolved["start_time"]
        requested_end = resolved["requested_end_time"]
        actual_end = resolved["actual_end_time"]

        result = []
        for point_id in data.point_ids:
            count, stream = self.stream_full(
                point_id,
                resolved["start_utc"],
                resolved["end_utc"],
                db,
            )
            try:
                rows = list(stream)
            finally:
                close = getattr(stream, "close", None)
                if close is not None:
                    close()
            result.append(
                {
                    "point_id": point_id,
                    "count": count,
                    "times": [
                        time_range_service.format(item[0], business_timezone)
                        for item in rows
                    ],
                    "values": [item[1] for item in rows],
                }
            )
        return {
            "timezone": str(business_timezone),
            "start_time": time_range_service.format(start, business_timezone),
            "requested_end_time": time_range_service.format(
                requested_end, business_timezone
            ),
            "actual_end_time": time_range_service.format(
                actual_end, business_timezone
            ),
            "points": result,
        }


data_query_service = DataQueryService()
