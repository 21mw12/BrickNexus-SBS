"""Compatibility marker for databases upgraded by the pre-2.0 migration chain.

The pre-2.0 project ended at revision ``20260827_0008``. The 2.0 baseline
consolidated that chain into ``20260817_0001`` and removed the old revision
files. Existing databases still keep ``20260827_0008`` in ``alembic_version``;
retaining this no-op marker lets Alembic resolve those databases and continue
with subsequent migrations.
"""

revision = "20260827_0008"
down_revision = "20260817_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The consolidated baseline already contains the historical schema changes.
    pass


def downgrade() -> None:
    # This compatibility marker has no schema operation.
    pass
