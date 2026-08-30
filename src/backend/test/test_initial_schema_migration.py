from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.domain import *  # noqa: F401,F403
from app.infra.DB.SQLConnection import Base


BASELINE_REVISION = "20260817_0001"


def _config(database: Path) -> Config:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database}")
    return config


def test_baseline_creates_fresh_database_and_can_downgrade(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    config = _config(database)

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite+pysqlite:///{database}")
    expected_tables = set(Base.metadata.tables) | {"alembic_version"}
    assert set(inspect(engine).get_table_names()) == expected_tables
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert revision == BASELINE_REVISION

    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}


def test_baseline_adopts_matching_existing_schema(tmp_path: Path) -> None:
    database = tmp_path / "existing.db"
    engine = create_engine(f"sqlite+pysqlite:///{database}")
    Base.metadata.create_all(engine)

    command.upgrade(_config(database), "head")

    expected_tables = set(Base.metadata.tables) | {"alembic_version"}
    assert set(inspect(engine).get_table_names()) == expected_tables
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert revision == BASELINE_REVISION
