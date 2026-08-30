from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _config(database: Path) -> Config:
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database}")
    return config


def test_api_channel_revision_is_renamed_without_losing_data(tmp_path: Path) -> None:
    database = tmp_path / "http-channel.db"
    engine = create_engine(f"sqlite+pysqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE assets (asset_id VARCHAR(100) PRIMARY KEY, asset_type VARCHAR(20))"
        ))
        connection.execute(text(
            "CREATE TABLE assets_sensor (asset_id VARCHAR(100) PRIMARY KEY)"
        ))

    config = _config(database)
    command.stamp(config, "20260818_0004")
    command.upgrade(config, "20260825_0005")
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO assets (asset_id, asset_type) VALUES ('sensor-1', 'sensor')"
        ))
        connection.execute(text(
            "INSERT INTO assets_sensor (asset_id) VALUES ('sensor-1')"
        ))
        connection.execute(text(
            "INSERT INTO channel_api "
            "(channel_api_id, base_url, default_headers, default_timeout, created_at) "
            "VALUES ('channel-1', 'https://example.com', '{}', 20, CURRENT_TIMESTAMP)"
        ))
        connection.execute(text(
            "INSERT INTO request "
            "(request_id, name, type, channel_id, interval_seconds, status, created_at, "
            "api_method, api_path) VALUES "
            "('request-1', 'temperature', 'api', 'channel-1', 60, 0, "
            "CURRENT_TIMESTAMP, 'GET', '/measurements')"
        ))
        connection.execute(text(
            "INSERT INTO control "
            "(control_id, name, type, channel_id, sensor_id, status, created_at, "
            "mqtt_topic, mqtt_retained, mqtt_payload) VALUES "
            "('control-1', 'switch', 'mqtt', 'mqtt-channel', 'sensor-1', 0, "
            "CURRENT_TIMESTAMP, '/switch', 0, 'on')"
        ))

    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert "channel_http" in inspect(connection).get_table_names()
        assert "channel_api" not in inspect(connection).get_table_names()
        base_url_column = next(
            column for column in inspect(connection).get_columns("channel_http")
            if column["name"] == "base_url"
        )
        assert base_url_column["type"].length == 200
        assert connection.execute(text(
            "SELECT type, http_method, http_path FROM request WHERE request_id='request-1'"
        )).one() == ("http", "GET", "/measurements")
        assert connection.execute(text(
            "SELECT channel_http_id, base_url FROM channel_http"
        )).one() == ("channel-1", "https://example.com")
        control_columns = {column["name"] for column in inspect(connection).get_columns("control")}
        assert {"asset_type", "asset_id"} <= control_columns
        assert "sensor_id" not in control_columns
        assert connection.execute(text(
            "SELECT asset_type, asset_id FROM control WHERE control_id='control-1'"
        )).one() == ("sensor", "sensor-1")

    command.downgrade(config, "20260825_0007")
    with engine.connect() as connection:
        control_columns = {column["name"] for column in inspect(connection).get_columns("control")}
        assert "sensor_id" in control_columns
        assert "asset_type" not in control_columns and "asset_id" not in control_columns
        assert connection.execute(text(
            "SELECT sensor_id FROM control WHERE control_id='control-1'"
        )).scalar_one() == "sensor-1"

    engine.dispose()
