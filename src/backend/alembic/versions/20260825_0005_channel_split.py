"""Split channels from requests and add sensor controls.

This is intentionally destructive for legacy request configuration.
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260825_0005"
down_revision = "20260818_0004"
branch_labels = None
depends_on = None


def _json_type():
    return postgresql.JSONB(astext_type=sa.Text()) if op.get_bind().dialect.name == "postgresql" else sa.JSON()


def _migrate_permission(upgrade: bool = True) -> None:
    bind = op.get_bind()
    names = set(sa.inspect(bind).get_table_names())
    if "page" not in names:
        return
    page = sa.table("page", sa.column("page_id", sa.String(100)), sa.column("page_id_parent", sa.String(100)), sa.column("name", sa.String(50)), sa.column("path_code", sa.String(50)))
    role_page = sa.table("role_page", sa.column("role_id", sa.String(100)), sa.column("page_id", sa.String(100)))
    has_links = "role_page" in names
    def add_links(role_ids: set[str], page_id: str) -> None:
        if not has_links or not role_ids:
            return
        existing = set(bind.execute(sa.select(role_page.c.role_id).where(role_page.c.page_id == page_id)).scalars())
        if role_ids - existing:
            bind.execute(role_page.insert(), [{"role_id": role_id, "page_id": page_id} for role_id in sorted(role_ids - existing)])

    def canonical(code: str, name: str, parent_id: str | None) -> str:
        ids = list(bind.execute(sa.select(page.c.page_id).where(page.c.path_code == code).order_by(page.c.page_id)).scalars())
        if ids:
            page_id = ids[0]
            bind.execute(page.update().where(page.c.page_id == page_id).values(page_id_parent=parent_id, name=name))
        else:
            page_id = str(uuid4())
            bind.execute(page.insert().values(page_id=page_id, page_id_parent=parent_id, name=name, path_code=code))
        duplicate_ids = set(ids[1:])
        if duplicate_ids:
            if has_links:
                roles = set(bind.execute(sa.select(role_page.c.role_id).where(role_page.c.page_id.in_(duplicate_ids))).scalars())
                add_links(roles, page_id)
                bind.execute(role_page.delete().where(role_page.c.page_id.in_(duplicate_ids)))
            bind.execute(page.delete().where(page.c.page_id.in_(duplicate_ids)))
        return page_id

    channel_id = canonical("channel", "采控通道配置", None)

    target_code, source_code = ("channel:requests", "data:requests") if upgrade else ("data:requests", "channel:requests")
    target_parent = channel_id if upgrade else bind.execute(sa.select(page.c.page_id).where(page.c.path_code == "data").limit(1)).scalar_one_or_none()
    target_id = canonical(target_code, "请求管理", target_parent)
    source_ids = set(bind.execute(sa.select(page.c.page_id).where(page.c.path_code == source_code)).scalars())
    if source_ids and has_links:
        roles = set(bind.execute(sa.select(role_page.c.role_id).where(role_page.c.page_id.in_(source_ids))).scalars())
        add_links(roles, target_id)
        bind.execute(role_page.delete().where(role_page.c.page_id.in_(source_ids)))
    if source_ids:
        bind.execute(page.delete().where(page.c.page_id.in_(source_ids)))

    if upgrade:
        canonical("channel:controls", "控制管理", channel_id)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "assets_terminal" in tables:
        bind.execute(sa.text("UPDATE assets_terminal SET request_id = NULL"))
    if "request" in tables:
        op.drop_table("request")
    json_type = _json_type()
    op.create_table(
        "channel_mqtt",
        sa.Column("channel_mqtt_id", sa.String(100), primary_key=True),
        sa.Column("broker_host", sa.String(30), nullable=False),
        sa.Column("broker_port", sa.Integer(), nullable=False, server_default="1883"),
        sa.Column("client_id", sa.String(100), nullable=False),
        sa.Column("username", sa.String(20)), sa.Column("password", sa.Text()),
        sa.Column("qos", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("connect_timeout", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("data_timeout", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("broker_port BETWEEN 1 AND 65535", name="ck_channel_mqtt_port"),
        sa.CheckConstraint("qos IN (0, 1, 2)", name="ck_channel_mqtt_qos"),
        sa.CheckConstraint("connect_timeout > 0", name="ck_channel_mqtt_connect_timeout"),
        sa.CheckConstraint("data_timeout > 0", name="ck_channel_mqtt_data_timeout"),
        sa.UniqueConstraint("client_id", name="uq_channel_mqtt_client_id"),
    )
    op.create_index("ix_channel_mqtt_broker", "channel_mqtt", ["broker_host", "broker_port"])
    op.create_table(
        "channel_api", sa.Column("channel_api_id", sa.String(100), primary_key=True),
        sa.Column("base_url", sa.String(50), nullable=False),
        sa.Column("default_headers", json_type, nullable=False),
        sa.Column("default_timeout", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("default_timeout > 0", name="ck_channel_api_timeout"),
    )
    op.create_index("ix_channel_api_base_url", "channel_api", ["base_url"])
    op.create_table(
        "request", sa.Column("request_id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(20), nullable=False), sa.Column("type", sa.String(10), nullable=False),
        sa.Column("channel_id", sa.String(100), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("time_json_path", sa.String(200)), sa.Column("time_format", sa.String(50)),
        sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mqtt_topic", sa.String(30)), sa.Column("api_method", sa.String(10)),
        sa.Column("api_path", sa.String(100)), sa.Column("api_header", json_type),
        sa.Column("api_params", json_type), sa.Column("api_body", json_type),
        sa.CheckConstraint("type IN ('mqtt', 'api')", name="ck_request_type"),
        sa.CheckConstraint("interval_seconds > 0", name="ck_request_interval_positive"),
        sa.CheckConstraint("(type = 'mqtt' AND mqtt_topic IS NOT NULL AND api_method IS NULL AND api_path IS NULL AND api_header IS NULL AND api_params IS NULL AND api_body IS NULL) OR (type = 'api' AND mqtt_topic IS NULL AND api_method IN ('GET', 'POST') AND api_path IS NOT NULL)", name="ck_request_protocol_fields"),
        sa.UniqueConstraint("name", name="uq_request_name"),
    )
    op.create_index("ix_request_type_status", "request", ["type", "status"])
    op.create_index("ix_request_channel_id", "request", ["channel_id"])
    op.create_table(
        "control", sa.Column("control_id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(30), nullable=False), sa.Column("type", sa.String(10), nullable=False),
        sa.Column("channel_id", sa.String(100), nullable=False),
        sa.Column("sensor_id", sa.String(100), sa.ForeignKey("assets_sensor.asset_id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mqtt_topic", sa.String(30)), sa.Column("mqtt_retained", sa.Boolean()), sa.Column("mqtt_payload", sa.Text()),
        sa.Column("api_method", sa.String(10)), sa.Column("api_path", sa.String(100)),
        sa.Column("api_header", json_type), sa.Column("api_params", json_type), sa.Column("api_body", json_type),
        sa.CheckConstraint("type IN ('mqtt', 'api')", name="ck_control_type"),
        sa.CheckConstraint("(type = 'mqtt' AND mqtt_topic IS NOT NULL AND mqtt_payload IS NOT NULL AND api_method IS NULL AND api_path IS NULL AND api_header IS NULL AND api_params IS NULL AND api_body IS NULL) OR (type = 'api' AND mqtt_topic IS NULL AND mqtt_retained IS NULL AND mqtt_payload IS NULL AND api_method IN ('GET', 'POST') AND api_path IS NOT NULL)", name="ck_control_protocol_fields"),
        sa.UniqueConstraint("name", name="uq_control_name"),
    )
    op.create_index("ix_control_type_status", "control", ["type", "status"])
    op.create_index("ix_control_channel_id", "control", ["channel_id"])
    op.create_index("ix_control_sensor_id", "control", ["sensor_id"])
    _migrate_permission(True)


def downgrade() -> None:
    _migrate_permission(False)
    op.drop_table("control")
    op.drop_table("request")
    op.drop_table("channel_api")
    op.drop_table("channel_mqtt")
    op.create_table(
        "request", sa.Column("request_id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False), sa.Column("request_type", sa.String(10), nullable=False),
        sa.Column("request_info", _json_type(), nullable=False), sa.Column("time_json_path", sa.String(200)),
        sa.Column("time_parse", sa.String(50)), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
