"""Create the schema used by a fresh installation.

Existing installations must stamp this revision before upgrading to the next
revision; no DDL is executed by ``stamp``.
"""

from alembic import op
import sqlalchemy as sa

from app.domain import *  # noqa: F401,F403 - 注册本 revision 的 ORM 表
from app.infra.DB.SQLConnection import Base


revision = "20260817_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fresh databases are created from the complete metadata snapshot.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(Base.metadata.sorted_tables):
        table.drop(bind=bind, checkfirst=True)
    if "sensor_model" in sa.inspect(bind).get_table_names():
        op.drop_table("sensor_model")
