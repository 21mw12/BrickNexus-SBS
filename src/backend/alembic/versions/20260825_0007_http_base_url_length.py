"""Expand HTTP channel base_url to 200 characters."""

from alembic import op
import sqlalchemy as sa


revision = "20260825_0007"
down_revision = "20260825_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("channel_http") as batch:
        batch.alter_column(
            "base_url",
            existing_type=sa.String(50),
            type_=sa.String(200),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("channel_http") as batch:
        batch.alter_column(
            "base_url",
            existing_type=sa.String(200),
            type_=sa.String(50),
            existing_nullable=False,
        )
