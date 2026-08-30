"""Rename API channels and protocol fields to HTTP.

The previous revision introduced the normalized channel tables with ``api``
names.  This revision preserves their data while making the persisted contract
match the actual transport protocol.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260825_0006"
down_revision = "20260825_0005"
branch_labels = None
depends_on = None


REQUEST_HTTP_CHECK = (
    "(type = 'mqtt' AND mqtt_topic IS NOT NULL AND http_method IS NULL "
    "AND http_path IS NULL AND http_header IS NULL AND http_params IS NULL "
    "AND http_body IS NULL) OR (type = 'http' AND mqtt_topic IS NULL "
    "AND http_method IN ('GET', 'POST') AND http_path IS NOT NULL)"
)
CONTROL_HTTP_CHECK = (
    "(type = 'mqtt' AND mqtt_topic IS NOT NULL AND mqtt_payload IS NOT NULL "
    "AND http_method IS NULL AND http_path IS NULL AND http_header IS NULL "
    "AND http_params IS NULL AND http_body IS NULL) OR (type = 'http' "
    "AND mqtt_topic IS NULL AND mqtt_retained IS NULL AND mqtt_payload IS NULL "
    "AND http_method IN ('GET', 'POST') AND http_path IS NOT NULL)"
)
REQUEST_API_CHECK = (
    "(type = 'mqtt' AND mqtt_topic IS NOT NULL AND api_method IS NULL "
    "AND api_path IS NULL AND api_header IS NULL AND api_params IS NULL "
    "AND api_body IS NULL) OR (type = 'api' AND mqtt_topic IS NULL "
    "AND api_method IN ('GET', 'POST') AND api_path IS NOT NULL)"
)
CONTROL_API_CHECK = (
    "(type = 'mqtt' AND mqtt_topic IS NOT NULL AND mqtt_payload IS NOT NULL "
    "AND api_method IS NULL AND api_path IS NULL AND api_header IS NULL "
    "AND api_params IS NULL AND api_body IS NULL) OR (type = 'api' "
    "AND mqtt_topic IS NULL AND mqtt_retained IS NULL AND mqtt_payload IS NULL "
    "AND api_method IN ('GET', 'POST') AND api_path IS NOT NULL)"
)


def _rename_protocol_columns(table_name: str, source: str, target: str) -> None:
    with op.batch_alter_table(table_name) as batch:
        batch.drop_constraint(f"ck_{table_name}_type", type_="check")
        batch.drop_constraint(f"ck_{table_name}_protocol_fields", type_="check")
        for suffix in ("method", "path", "header", "params", "body"):
            batch.alter_column(f"{source}_{suffix}", new_column_name=f"{target}_{suffix}")


def _create_protocol_checks(table_name: str, protocol: str) -> None:
    expression = (
        REQUEST_HTTP_CHECK if table_name == "request" and protocol == "http"
        else CONTROL_HTTP_CHECK if table_name == "control" and protocol == "http"
        else REQUEST_API_CHECK if table_name == "request"
        else CONTROL_API_CHECK
    )
    with op.batch_alter_table(table_name) as batch:
        batch.create_check_constraint(
            f"ck_{table_name}_type", f"type IN ('mqtt', '{protocol}')"
        )
        batch.create_check_constraint(f"ck_{table_name}_protocol_fields", expression)


def upgrade() -> None:
    # Some migration-only SQLite tests stamp an intermediate revision on a
    # deliberately partial schema.  ``control`` still contains the FK emitted
    # by 0005, and SQLite reflection needs its target table while rebuilding
    # constraints.  Real databases always have assets_sensor.
    bind = op.get_bind()
    created_placeholder_sensor = (
        bind.dialect.name == "sqlite"
        and "assets_sensor" not in sa.inspect(bind).get_table_names()
    )
    if created_placeholder_sensor:
        op.create_table(
            "assets_sensor", sa.Column("asset_id", sa.String(100), primary_key=True)
        )

    op.drop_index("ix_channel_api_base_url", table_name="channel_api")
    with op.batch_alter_table("channel_api") as batch:
        batch.drop_constraint("ck_channel_api_timeout", type_="check")
        batch.alter_column("channel_api_id", new_column_name="channel_http_id")
    op.rename_table("channel_api", "channel_http")
    with op.batch_alter_table("channel_http") as batch:
        batch.create_check_constraint("ck_channel_http_timeout", "default_timeout > 0")
    op.create_index("ix_channel_http_base_url", "channel_http", ["base_url"])

    _rename_protocol_columns("request", "api", "http")
    _rename_protocol_columns("control", "api", "http")
    op.execute(sa.text("UPDATE request SET type = 'http' WHERE type = 'api'"))
    op.execute(sa.text("UPDATE control SET type = 'http' WHERE type = 'api'"))
    _create_protocol_checks("request", "http")
    _create_protocol_checks("control", "http")
    if created_placeholder_sensor:
        op.drop_table("assets_sensor")


def downgrade() -> None:
    bind = op.get_bind()
    created_placeholder_sensor = (
        bind.dialect.name == "sqlite"
        and "assets_sensor" not in sa.inspect(bind).get_table_names()
    )
    if created_placeholder_sensor:
        op.create_table(
            "assets_sensor", sa.Column("asset_id", sa.String(100), primary_key=True)
        )

    op.drop_index("ix_channel_http_base_url", table_name="channel_http")
    with op.batch_alter_table("channel_http") as batch:
        batch.drop_constraint("ck_channel_http_timeout", type_="check")
        batch.alter_column("channel_http_id", new_column_name="channel_api_id")
    op.rename_table("channel_http", "channel_api")
    with op.batch_alter_table("channel_api") as batch:
        batch.create_check_constraint("ck_channel_api_timeout", "default_timeout > 0")
    op.create_index("ix_channel_api_base_url", "channel_api", ["base_url"])

    _rename_protocol_columns("request", "http", "api")
    _rename_protocol_columns("control", "http", "api")
    op.execute(sa.text("UPDATE request SET type = 'api' WHERE type = 'http'"))
    op.execute(sa.text("UPDATE control SET type = 'api' WHERE type = 'http'"))
    _create_protocol_checks("request", "api")
    _create_protocol_checks("control", "api")
    if created_placeholder_sensor:
        op.drop_table("assets_sensor")
