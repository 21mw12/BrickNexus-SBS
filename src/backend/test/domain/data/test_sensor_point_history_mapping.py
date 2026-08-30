from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.asset.repository.SensorPointRepository import SensorPointRepository
from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.repository.models.SensorPoint import SensorPoint
from app.infra.DB.SQLConnection import Base


def test_point_sensor_mapping_only_returns_valid_sensor_assets() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine, tables=[Asset.__table__, SensorPoint.__table__])
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add_all(
        [
            Asset(asset_id="sensor-1", asset_type="sensor", name="Sensor 1"),
            Asset(asset_id="terminal-1", asset_type="terminal", name="Terminal 1"),
            SensorPoint(point_id="valid", sensor_id="sensor-1", source_model_id="m", source_point_id="p", point_name="温度", point_unit="℃"),
            SensorPoint(point_id="wrong-type", sensor_id="terminal-1", source_model_id="m", source_point_id="p", point_name="温度", point_unit="℃"),
            SensorPoint(point_id="orphan", sensor_id="missing-sensor", source_model_id="m", source_point_id="p", point_name="温度", point_unit="℃"),
        ]
    )
    session.commit()

    result = SensorPointRepository().get_sensor_ids_by_point_ids(
        ["valid", "wrong-type", "orphan", "missing-point"],
        session,
    )

    assert result == {"valid": "sensor-1"}
