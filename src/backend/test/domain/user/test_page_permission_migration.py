from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def _config(database: Path) -> Config:
    config = Config(str(Path(__file__).parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database}")
    return config


def test_legacy_rule_log_permissions_are_merged_and_removed(tmp_path):
    database = tmp_path / "permissions.db"
    engine = create_engine(f"sqlite+pysqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE page (page_id VARCHAR(100) PRIMARY KEY, "
            "page_id_parent VARCHAR(100), name VARCHAR(50) NOT NULL, path_code VARCHAR(50) NOT NULL)"
        ))
        connection.execute(text(
            "CREATE TABLE role_page (role_id VARCHAR(100) NOT NULL, page_id VARCHAR(100) NOT NULL, "
            "PRIMARY KEY (role_id, page_id))"
        ))
        connection.execute(text(
            "INSERT INTO page VALUES "
            "('data', NULL, '数据管理', 'data'), "
            "('old-rule', 'data', '规则管理', 'data:rules'), "
            "('old-logs', 'data', '日志管理', 'data:logs'), "
            "('new-rule-a', 'data', '错误父级', 'rule'), "
            "('new-rule-b', NULL, '重复规则', 'rule')"
        ))
        connection.execute(text(
            "INSERT INTO role_page VALUES "
            "('role-a', 'old-rule'), ('role-a', 'new-rule-b'), "
            "('role-b', 'old-logs'), ('role-c', 'new-rule-a')"
        ))

    config = _config(database)
    command.stamp(config, "20260818_0003")
    command.upgrade(config, "head")

    with engine.connect() as connection:
        pages = connection.execute(text(
            "SELECT page_id, page_id_parent, name, path_code FROM page ORDER BY path_code, page_id"
        )).mappings().all()
        assert not {"data:rules", "data:logs"} & {row["path_code"] for row in pages}
        rule_pages = [row for row in pages if row["path_code"] == "rule"]
        log_pages = [row for row in pages if row["path_code"] == "logs"]
        assert len(rule_pages) == len(log_pages) == 1
        assert rule_pages[0]["page_id_parent"] is None and rule_pages[0]["name"] == "规则管理"
        assert log_pages[0]["page_id_parent"] is None and log_pages[0]["name"] == "系统日志"
        links = set(connection.execute(text(
            "SELECT rp.role_id, p.path_code FROM role_page rp JOIN page p ON p.page_id = rp.page_id"
        )).tuples())
        assert {("role-a", "rule"), ("role-b", "logs"), ("role-c", "rule")} <= links

    command.downgrade(config, "20260818_0003")
    with engine.connect() as connection:
        codes = set(connection.execute(text("SELECT path_code FROM page")).scalars())
        assert {"data:rules", "data:logs"} <= codes
    engine.dispose()
