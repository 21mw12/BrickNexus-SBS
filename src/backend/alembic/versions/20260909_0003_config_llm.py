"""add LLM provider settings

Revision ID: 20260909_0003
Revises: 20260902_0002
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260909_0003"
down_revision = "20260902_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "config_llm",
        sa.Column("llm_id", sa.String(100), nullable=False),
        sa.Column("service_name", sa.String(50), nullable=False),
        sa.Column("service_type", sa.String(20), nullable=False),
        sa.Column("content", json_type, nullable=False),
        sa.Column("is_use", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "service_type IN ('vllm', 'ollama', 'deepseek')",
            name="ck_config_llm_service_type",
        ),
        sa.PrimaryKeyConstraint("llm_id"),
    )
    op.create_index("ix_config_llm_created_at", "config_llm", ["created_at"])
    op.create_index(
        "uq_config_llm_single_active",
        "config_llm",
        ["is_use"],
        unique=True,
        postgresql_where=sa.text("is_use = true"),
        sqlite_where=sa.text("is_use = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_config_llm_single_active", table_name="config_llm")
    op.drop_index("ix_config_llm_created_at", table_name="config_llm")
    op.drop_table("config_llm")

