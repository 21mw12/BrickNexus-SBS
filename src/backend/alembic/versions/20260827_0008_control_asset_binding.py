"""Allow controls to bind either terminal or sensor assets."""

from alembic import op
import sqlalchemy as sa


revision = "20260827_0008"
down_revision = "20260825_0007"
branch_labels = None
depends_on = None


NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def _foreign_key_name(column_name: str, fallback: str) -> str | None:
    for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys("control"):
        if foreign_key.get("constrained_columns") == [column_name]:
            return foreign_key.get("name") or fallback
    return None


def upgrade() -> None:
    bind = op.get_bind()
    table_names = set(sa.inspect(bind).get_table_names())
    created_placeholder_sensor = (
        bind.dialect.name == "sqlite" and "assets_sensor" not in table_names
    )
    if created_placeholder_sensor:
        op.create_table(
            "assets_sensor", sa.Column("asset_id", sa.String(100), primary_key=True)
        )
    if "assets" not in table_names:
        # Migration-only SQLite tests can start from deliberately partial legacy
        # schemas. They have an empty Control table created by 0005 but no asset
        # domain tables. A minimal target keeps the migrated FK structurally
        # valid without weakening checks for real, populated databases.
        control_count = bind.execute(sa.text("SELECT COUNT(*) FROM control")).scalar_one()
        if control_count:
            raise RuntimeError("assets table is required before upgrading populated control bindings")
        op.create_table(
            "assets",
            sa.Column("asset_id", sa.String(100), primary_key=True),
            sa.Column("asset_type", sa.String(20), nullable=True),
        )

    op.add_column(
        "control",
        sa.Column("asset_type", sa.String(10), nullable=False, server_default="sensor"),
    )
    op.add_column("control", sa.Column("asset_id", sa.String(100), nullable=True))
    bind.execute(sa.text("UPDATE control SET asset_id = sensor_id"))

    missing_assets = bind.execute(sa.text(
        "SELECT COUNT(*) FROM control c LEFT JOIN assets a ON a.asset_id = c.asset_id "
        "WHERE a.asset_id IS NULL"
    )).scalar_one()
    if missing_assets:
        raise RuntimeError(
            f"cannot migrate control bindings: {missing_assets} sensor assets are missing from assets"
        )

    old_fk_name = _foreign_key_name(
        "sensor_id", "fk_control_sensor_id_assets_sensor"
    )
    with op.batch_alter_table(
        "control", naming_convention=NAMING_CONVENTION
    ) as batch:
        if old_fk_name:
            batch.drop_constraint(old_fk_name, type_="foreignkey")
        batch.drop_index("ix_control_sensor_id")
        batch.drop_column("sensor_id")
        batch.alter_column(
            "asset_type", existing_type=sa.String(10),
            existing_nullable=False, server_default=None,
        )
        batch.alter_column(
            "asset_id", existing_type=sa.String(100), nullable=False,
        )
        batch.create_check_constraint(
            "ck_control_asset_type", "asset_type IN ('terminal', 'sensor')"
        )
        batch.create_foreign_key(
            "fk_control_asset_id_assets", "assets", ["asset_id"], ["asset_id"],
            ondelete="CASCADE",
        )
    op.create_index(
        "ix_control_asset_type_asset_id", "control", ["asset_type", "asset_id"]
    )
    if created_placeholder_sensor:
        op.drop_table("assets_sensor")


def downgrade() -> None:
    bind = op.get_bind()
    table_names = set(sa.inspect(bind).get_table_names())
    created_placeholder_sensor = (
        bind.dialect.name == "sqlite" and "assets_sensor" not in table_names
    )
    if created_placeholder_sensor:
        op.create_table(
            "assets_sensor", sa.Column("asset_id", sa.String(100), primary_key=True)
        )
    terminal_count = bind.execute(sa.text(
        "SELECT COUNT(*) FROM control WHERE asset_type = 'terminal'"
    )).scalar_one()
    if terminal_count:
        raise RuntimeError(
            "cannot downgrade control bindings while terminal controls exist"
        )

    op.add_column("control", sa.Column("sensor_id", sa.String(100), nullable=True))
    bind.execute(sa.text("UPDATE control SET sensor_id = asset_id"))
    new_fk_name = _foreign_key_name("asset_id", "fk_control_asset_id_assets")
    with op.batch_alter_table(
        "control", naming_convention=NAMING_CONVENTION
    ) as batch:
        batch.drop_index("ix_control_asset_type_asset_id")
        if new_fk_name:
            batch.drop_constraint(new_fk_name, type_="foreignkey")
        batch.drop_constraint("ck_control_asset_type", type_="check")
        batch.drop_column("asset_id")
        batch.drop_column("asset_type")
        batch.alter_column(
            "sensor_id", existing_type=sa.String(100), nullable=False,
        )
        batch.create_foreign_key(
            "fk_control_sensor_id_assets_sensor", "assets_sensor",
            ["sensor_id"], ["asset_id"], ondelete="CASCADE",
        )
    op.create_index("ix_control_sensor_id", "control", ["sensor_id"])
    if created_placeholder_sensor:
        op.drop_table("assets_sensor")
