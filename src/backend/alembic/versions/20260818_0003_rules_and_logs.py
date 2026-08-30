"""Add rule runtime and business log tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_0003"
down_revision = "20260817_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = (
        postgresql.JSONB(astext_type=sa.Text())
        if op.get_bind().dialect.name == "postgresql"
        else sa.JSON()
    )
    op.create_table(
        "rule",
        sa.Column("rule_id", sa.String(100), primary_key=True),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("rule_file_name", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="paused"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rule_status", "rule", ["status"])
    op.create_table(
        "rule_event",
        sa.Column("event_id", sa.String(100), primary_key=True),
        sa.Column("rule_id", sa.String(100), sa.ForeignKey("rule.rule_id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("evidence", json_type, nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rule_event_rule_time", "rule_event", ["rule_id", "event_time"])
    op.create_index("ix_rule_event_type", "rule_event", ["event_type"])
    op.create_table(
        "action_task",
        sa.Column("task_id", sa.String(100), primary_key=True),
        sa.Column("rule_id", sa.String(100), sa.ForeignKey("rule.rule_id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.String(100), sa.ForeignKey("rule_event.event_id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_id", sa.String(100), nullable=False),
        sa.Column("action_type", sa.String(20), nullable=False),
        sa.Column("action_params", json_type, nullable=False),
        sa.Column("is_executed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_action_task_status_created", "action_task", ["status", "created_at"])
    op.create_index("ix_action_task_rule_action", "action_task", ["rule_id", "action_id"])
    op.create_table(
        "log",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("operator", sa.String(30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("type", "level", "operator", "time"):
        op.create_index(f"ix_log_{column}", "log", [column])


def downgrade() -> None:
    op.drop_table("log")
    op.drop_table("action_task")
    op.drop_table("rule_event")
    op.drop_table("rule")
