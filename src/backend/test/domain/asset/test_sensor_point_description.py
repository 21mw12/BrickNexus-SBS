"""全局 Point、型号绑定与传感器实例测点测试。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from pydantic import ValidationError as PydanticValidationError
import pytest

from app.common.validators import ValidationError
from app.domain.asset.repository.models.ModelPoint import ModelPoint
from app.domain.asset.repository.models.Point import Point
from app.domain.asset.repository.models.SensorModel import SensorModel
from app.domain.asset.repository.models.SensorPoint import SensorPoint
from app.domain.asset.schema.PointSchema import PointAddSchema, PointUpdateSchema
from app.domain.asset.schema.SensorModelSchema import (
    ModelPointResponseSchema,
    SensorModelAddSchema,
    SensorModelUpdateSchema,
)
from app.domain.asset.schema.SensorResponseSchema import SensorResponseSchema
from app.domain.asset.service.PointService import PointService
from app.domain.asset.service.SensorModelService import SensorModelService
from app.domain.asset.service.SensorPointService import SensorPointService
from app.infra.DB.SQLConnection import Base


TABLES = [
    SensorModel.__table__,
    Point.__table__,
    ModelPoint.__table__,
    SensorPoint.__table__,
]


def _engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TABLES)
    return engine


def test_description_is_read_from_point_instead_of_copied() -> None:
    engine = _engine()
    with Session(engine) as db:
        point = Point(
            point_id="point-1",
            point_name="温度",
            point_unit="℃",
            point_description="设备周围环境温度",
        )
        model_point = ModelPoint(model_id="model-1", point_id="point-1")
        db.add_all([SensorModel(model_id="model-1"), point, model_point])
        db.flush()

        copied = SensorPointService.copy_from_model("model-1", "sensor-1", db)

        assert len(copied) == 1
        assert copied[0].source_model_id == "model-1"
        assert copied[0].source_point_id == "point-1"
        assert "point_description" not in SensorPoint.__table__.columns
        assert copied[0].point_description == "设备周围环境温度"
        assert ModelPointResponseSchema.from_model(model_point).model_dump() == {
            "point_id": "point-1",
            "point_name": "温度",
            "point_unit": "℃",
            "point_description": "设备周围环境温度",
        }

        response = SensorResponseSchema.from_models(
            {"asset_id": "sensor-1", "asset_type": "sensor"},
            None,
            points=[model_point],
            sensor_points=copied,
        ).model_dump()
        assert response["points"][0]["point_id"] == "point-1"
        assert response["sensor_points"][0]["source_point_id"] == "point-1"
        assert response["sensor_points"][0]["point_description"] == "设备周围环境温度"


def test_model_creation_binds_existing_points_and_rejects_duplicates() -> None:
    engine = _engine()
    with Session(engine) as db:
        db.add(Point(point_id="point-1", point_name="温度", point_unit="℃"))
        db.flush()

        result = SensorModelService.create_model(
            SensorModelAddSchema(model_name="DHT22", points=[{"point_id": "point-1"}]),
            db,
        )
        assert result["points"][0]["point_id"] == "point-1"

        with pytest.raises(ValidationError, match="duplicate point_id"):
            SensorModelService.create_model(
                SensorModelAddSchema(
                    model_name="duplicate",
                    points=[{"point_id": "point-1"}, {"point_id": "point-1"}],
                ),
                db,
            )


def test_model_edit_does_not_accept_point_changes() -> None:
    with pytest.raises(PydanticValidationError):
        SensorModelUpdateSchema.model_validate(
            {"model_name": "DHT22", "points": [{"point_id": "point-1"}]}
        )


def test_point_identity_and_description_update() -> None:
    engine = _engine()
    with Session(engine) as db:
        celsius = PointService.create_point(
            PointAddSchema(point_name=" 温度 ", point_unit=" ℃ "), db
        )
        fahrenheit = PointService.create_point(
            PointAddSchema(point_name="温度", point_unit="℉"), db
        )
        phase_a = PointService.create_point(
            PointAddSchema(point_name="A相电流", point_unit="A"), db
        )
        phase_b = PointService.create_point(
            PointAddSchema(point_name="B相电流", point_unit="A"), db
        )
        phase_c = PointService.create_point(
            PointAddSchema(point_name="C相电流", point_unit="A"), db
        )
        unitless = PointService.create_point(
            PointAddSchema(point_name="功率因数", point_unit=""), db
        )
        assert len({celsius["point_id"], fahrenheit["point_id"]}) == 2
        assert len({phase_a["point_id"], phase_b["point_id"], phase_c["point_id"]}) == 3
        assert unitless["point_unit"] == ""

        with pytest.raises(ValidationError, match="already exist"):
            PointService.create_point(
                PointAddSchema(point_name="温度", point_unit="℃"), db
            )

        updated = PointService.update_point(
            celsius["point_id"],
            PointUpdateSchema(point_description="环境温度"),
            db,
        )
        assert updated["point_description"] == "环境温度"

        with pytest.raises(PydanticValidationError):
            PointUpdateSchema.model_validate(
                {"point_name": "室温", "point_description": "环境温度"}
            )


def test_point_description_update_only_refreshes_runtime_cache(monkeypatch) -> None:
    engine = _engine()
    with Session(engine) as db:
        db.add_all(
            [
                SensorModel(model_id="model-1"),
                Point(point_id="point-1", point_name="温度", point_unit="℃"),
                ModelPoint(model_id="model-1", point_id="point-1"),
                SensorPoint(
                    point_id="sensor-point-1",
                    sensor_id="sensor-1",
                    source_model_id="model-1",
                    source_point_id="point-1",
                    point_name="温度",
                    point_unit="℃",
                ),
            ]
        )
        db.flush()

        from app.domain.collector.loader.request_loader import request_loader

        refreshed = {}
        monkeypatch.setattr(
            request_loader,
            "update_point_descriptions",
            lambda descriptions: refreshed.update(descriptions) or len(descriptions),
        )

        PointService.update_point(
            "point-1",
            PointUpdateSchema(point_description="新说明"),
            db,
        )

        assert refreshed == {"sensor-point-1": "新说明"}
        assert "point_description" not in SensorPoint.__table__.columns
