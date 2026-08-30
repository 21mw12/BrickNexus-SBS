"""采集领域发布给 data/rule 消费者的不可变事件。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CollectedPoint:
    point_id: str
    sensor_id: str
    terminal_id: str
    unit: str = ""
    point_description: str = ""


@dataclass(frozen=True)
class MeasurementValue:
    point_id: str
    sensor_id: str
    terminal_id: str
    value: float


@dataclass(frozen=True)
class PointParseError:
    point_id: str
    error: str


@dataclass(frozen=True)
class MeasurementBatchEvent:
    request_id: str
    request_type: str
    occurred_at: datetime
    terminal_ids: tuple[str, ...]
    points: tuple[CollectedPoint, ...]
    measurements: tuple[MeasurementValue, ...]
    sensor_statuses: tuple[tuple[str, bool], ...]
    parse_errors: tuple[PointParseError, ...] = ()
    storage_interval_seconds: float | None = None


@dataclass(frozen=True)
class CollectionStatusEvent:
    request_id: str
    occurred_at: datetime
    terminal_ids: tuple[str, ...]
    points: tuple[CollectedPoint, ...]
    sensor_statuses: tuple[tuple[str, bool], ...]
    terminal_online: bool


@dataclass(frozen=True)
class CollectionRequestStartedEvent:
    request_id: str
    request_type: str
    started_at: datetime
    storage_interval_seconds: float | None = None


@dataclass(frozen=True)
class CollectionRequestStoppedEvent:
    request_id: str


def points_from_request_data(request_data: dict) -> tuple[CollectedPoint, ...]:
    return tuple(
        CollectedPoint(
            point_id=point["point_id"],
            sensor_id=point["sensor_id"],
            terminal_id=point["terminal_id"],
            unit=point.get("unit") or "",
            point_description=point.get("point_description") or "",
        )
        for point in request_data["point_list"]
    )


def request_data_from_event(event: MeasurementBatchEvent | CollectionStatusEvent) -> dict:
    return {
        "terminal_list": list(event.terminal_ids),
        "point_list": [
            {
                "point_id": point.point_id,
                "sensor_id": point.sensor_id,
                "terminal_id": point.terminal_id,
                "unit": point.unit,
                "point_description": point.point_description,
            }
            for point in event.points
        ],
    }
