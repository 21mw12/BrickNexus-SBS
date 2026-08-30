from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.domain.data.repository.MeasurementRepository import MeasurementRepository
from app.domain.data.repository.models.Measurement import Measurement
from app.infra.DB.SQLConnection import Base


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine, tables=[Measurement.__table__])
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_upsert_same_point_and_time_overwrites_value() -> None:
    session = _session()
    repository = MeasurementRepository()
    measurement_time = datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)

    repository.upsert_many(
        [{"point_id": "point-1", "time": measurement_time, "value": 12.5}],
        session,
    )
    repository.upsert_many(
        [{"point_id": "point-1", "time": measurement_time, "value": 18.75}],
        session,
    )
    session.commit()

    rows = session.execute(select(Measurement)).scalars().all()
    assert len(rows) == 1
    assert rows[0].point_id == "point-1"
    # SQLite 不保留 tzinfo；PostgreSQL 集成测试验证 timestamptz 的实际往返。
    assert rows[0].time.replace(tzinfo=timezone.utc) == measurement_time
    assert rows[0].value == 18.75


def test_measurement_time_round_trips_as_aware_datetime() -> None:
    session = _session()
    repository = MeasurementRepository()
    measurement_time = datetime(2026, 8, 3, 18, 30, tzinfo=timezone(timedelta(hours=8)))

    repository.upsert_many(
        [{"point_id": "point-timezone", "time": measurement_time, "value": 1.0}],
        session,
    )
    session.commit()
    session.expire_all()

    result = repository.get("point-timezone", measurement_time, session)
    assert result is not None
    # SQLite 不保留 tzinfo；PostgreSQL 集成测试会验证 timestamptz 的实际往返。
    assert result.time.replace(tzinfo=measurement_time.tzinfo) == measurement_time


def test_stream_history_is_left_closed_right_open_and_ordered() -> None:
    session = _session()
    repository = MeasurementRepository()
    start = datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=30)

    repository.upsert_many(
        [
            {"point_id": "point-1", "time": end, "value": 4.0},
            {"point_id": "point-1", "time": start + timedelta(minutes=15), "value": 2.0},
            {"point_id": "point-1", "time": start, "value": 1.0},
            {"point_id": "point-2", "time": start, "value": 99.0},
        ],
        session,
    )
    session.commit()

    raw_count, points = repository.stream_history("point-1", start, end, session)
    result = list(points)

    assert raw_count == 2
    assert [item[1] for item in result] == [1.0, 2.0]
    assert [item[0].replace(tzinfo=timezone.utc) for item in result] == [
        start,
        start + timedelta(minutes=15),
    ]


def test_stream_history_returns_empty_iterator() -> None:
    session = _session()
    repository = MeasurementRepository()
    start = datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)

    raw_count, points = repository.stream_history(
        "missing",
        start,
        start + timedelta(minutes=15),
        session,
    )

    assert raw_count == 0
    assert list(points) == []
