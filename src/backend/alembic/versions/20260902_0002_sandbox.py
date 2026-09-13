"""add digital twin sandbox tables

Revision ID: 20260902_0002
Revises: 20260817_0001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260902_0002"
down_revision = "20260827_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "sandbox",
        sa.Column("sandbox_id", sa.String(100), nullable=False),
        sa.Column("sandbox_name", sa.String(30), nullable=False),
        sa.Column("config", json_type, nullable=False),
        sa.Column("state", sa.Boolean(), nullable=False),
        sa.Column("tick", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("sandbox_id"),
    )
    op.create_table(
        "sandbox_measurement",
        sa.Column("sandbox_id", sa.String(100), nullable=False),
        sa.Column("point_id", sa.String(100), nullable=False),
        sa.Column("tick", sa.BigInteger(), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["sandbox_id"], ["sandbox.sandbox_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("sandbox_id", "point_id", "tick"),
    )
    op.create_index(
        "ix_sandbox_measurement_sandbox_tick",
        "sandbox_measurement",
        ["sandbox_id", "tick"],
    )
    op.create_table(
        "sandbox_event",
        sa.Column("event_id", sa.String(100), nullable=False),
        sa.Column("sandbox_id", sa.String(100), nullable=False),
        sa.Column("tick", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.ForeignKeyConstraint(
            ["sandbox_id"], ["sandbox.sandbox_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_sandbox_event_sandbox_tick",
        "sandbox_event",
        ["sandbox_id", "tick"],
    )


def downgrade() -> None:
    op.drop_index("ix_sandbox_event_sandbox_tick", table_name="sandbox_event")
    op.drop_table("sandbox_event")
    op.drop_index(
        "ix_sandbox_measurement_sandbox_tick",
        table_name="sandbox_measurement",
    )
    op.drop_table("sandbox_measurement")
    op.drop_table("sandbox")
