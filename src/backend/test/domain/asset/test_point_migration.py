from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


MODEL_1 = "00000000-0000-0000-0000-000000000011"
MODEL_2 = "00000000-0000-0000-0000-000000000012"
OLD_POINT_1 = "00000000-0000-0000-0000-000000000101"
OLD_POINT_2 = "00000000-0000-0000-0000-000000000102"
SENSOR_POINT_1 = "00000000-0000-0000-0000-000000000201"
SENSOR_POINT_2 = "00000000-0000-0000-0000-000000000202"
ORPHAN_MODEL = "00000000-0000-0000-0000-000000000099"
ORPHAN_POINT = "00000000-0000-0000-0000-000000000199"


def _config(database: Path) -> Config:
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database}")
    return config


def _create_legacy_database(database: Path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE sensor_model (
                model_id VARCHAR(100) PRIMARY KEY,
                sensor_type VARCHAR(50), model_name VARCHAR(50), remark VARCHAR(100)
            )
        """))
        connection.execute(text("""
            CREATE TABLE model_point (
                point_id VARCHAR(100) PRIMARY KEY,
                model_id VARCHAR(100), point_name VARCHAR(20), point_unit VARCHAR(10),
                point_description VARCHAR(200)
            )
        """))
        connection.execute(text("""
            CREATE TABLE sensor_point (
                point_id VARCHAR(100) PRIMARY KEY,
                sensor_id VARCHAR(100) NOT NULL,
                model_point_id VARCHAR(100), point_name VARCHAR(20), point_unit VARCHAR(10),
                point_description VARCHAR(200), json_path VARCHAR(200)
            )
        """))
        connection.execute(text("""
            CREATE TABLE measurement (
                point_id VARCHAR(100) NOT NULL,
                time DATETIME NOT NULL,
                value FLOAT NOT NULL,
                PRIMARY KEY (point_id, time)
            )
        """))
        connection.execute(
            text("INSERT INTO sensor_model VALUES (:id, '温湿度', :name, NULL)"),
            [{"id": MODEL_1, "name": "M1"}, {"id": MODEL_2, "name": "M2"}],
        )
        connection.execute(
            text("""
                INSERT INTO model_point
                (point_id, model_id, point_name, point_unit, point_description)
                VALUES (:point_id, :model_id, :point_name, :point_unit, :description)
            """),
            [
                {"point_id": OLD_POINT_1, "model_id": MODEL_1, "point_name": "功率因数", "point_unit": None, "description": "说明一"},
                {"point_id": OLD_POINT_2, "model_id": MODEL_2, "point_name": "功率因数", "point_unit": None, "description": "说明二"},
                {"point_id": ORPHAN_POINT, "model_id": ORPHAN_MODEL, "point_name": "孤立测点", "point_unit": "V", "description": "无实例引用"},
            ],
        )
        connection.execute(
            text("""
                INSERT INTO sensor_point
                (point_id, sensor_id, model_point_id, point_name, point_unit, point_description, json_path)
                VALUES (:point_id, :sensor_id, :model_point_id, '功率因数', NULL, :description, :json_path)
            """),
            [
                {"point_id": SENSOR_POINT_1, "sensor_id": "sensor-1", "model_point_id": OLD_POINT_1, "description": "实例说明一", "json_path": "$.a"},
                {"point_id": SENSOR_POINT_2, "sensor_id": "sensor-2", "model_point_id": OLD_POINT_2, "description": "实例说明二", "json_path": "$.b"},
            ],
        )
        connection.execute(
            text("INSERT INTO measurement VALUES (:point_id, '2026-08-17 00:00:00', 1.0)"),
            [{"point_id": SENSOR_POINT_1}, {"point_id": SENSOR_POINT_2}],
        )


def test_point_migration_preserves_instances_and_measurements(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    _create_legacy_database(database)
    config = _config(database)
    command.stamp(config, "20260817_0001")
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite+pysqlite:///{database}")
    with engine.connect() as connection:
        inspector = inspect(connection)
        table_names = inspector.get_table_names()
        assert "sensor_model" not in table_names
        assert {"rule", "rule_event", "action_task", "log"}.issubset(table_names)
        assert {item["name"] for item in inspector.get_indexes("rule")} == {"ix_rule_status"}
        assert {item["name"] for item in inspector.get_indexes("rule_event")} == {
            "ix_rule_event_rule_time", "ix_rule_event_type"
        }
        assert {item["name"] for item in inspector.get_indexes("action_task")} == {
            "ix_action_task_rule_action", "ix_action_task_status_created"
        }
        assert {item["name"] for item in inspector.get_indexes("log")} == {
            "ix_log_level", "ix_log_operator", "ix_log_time", "ix_log_type"
        }
        assert {fk["referred_table"] for fk in inspector.get_foreign_keys("action_task")} == {
            "rule", "rule_event"
        }
        assert connection.execute(text("SELECT count(*) FROM point")).scalar_one() == 1
        point = connection.execute(text("SELECT * FROM point")).mappings().one()
        assert point["point_id"] == OLD_POINT_1
        assert point["point_unit"] == ""
        assert point["point_description"] is None
        assert connection.execute(text("SELECT count(*) FROM model_point")).scalar_one() == 2
        sensor_points = connection.execute(
            text("SELECT * FROM sensor_point ORDER BY point_id")
        ).mappings().all()
        assert [row["point_id"] for row in sensor_points] == [SENSOR_POINT_1, SENSOR_POINT_2]
        assert [row["source_model_id"] for row in sensor_points] == [MODEL_1, MODEL_2]
        assert {row["source_point_id"] for row in sensor_points} == {OLD_POINT_1}
        assert {row["point_unit"] for row in sensor_points} == {""}
        assert [row["json_path"] for row in sensor_points] == ["$.a", "$.b"]
        assert connection.execute(text("SELECT count(*) FROM measurement")).scalar_one() == 2

    command.downgrade(config, "20260817_0001")
    with engine.connect() as connection:
        assert "sensor_model" in inspect(connection).get_table_names()
        assert connection.execute(text("SELECT count(*) FROM measurement")).scalar_one() == 2
        assert connection.execute(text("SELECT count(*) FROM sensor_point")).scalar_one() == 2


def test_point_migration_rejects_referenced_binding_with_missing_model(
    tmp_path: Path,
) -> None:
    database = tmp_path / "referenced-orphan.db"
    _create_legacy_database(database)
    config = _config(database)
    command.stamp(config, "20260817_0001")

    engine = create_engine(f"sqlite+pysqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE model_point SET model_id = :model_id WHERE point_id = :point_id"),
            {"model_id": ORPHAN_MODEL, "point_id": OLD_POINT_1},
        )

    with pytest.raises(RuntimeError, match="referenced model_point has invalid model_id"):
        command.upgrade(config, "head")

    with engine.connect() as connection:
        assert "sensor_model" in inspect(connection).get_table_names()
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "20260817_0001"
