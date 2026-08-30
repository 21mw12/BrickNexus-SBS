"""Migrate legacy rule/log page permissions to top-level page codes."""

from __future__ import annotations

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "20260818_0004"
down_revision = "20260818_0003"
branch_labels = None
depends_on = None


PAGE_SPECS = {
    "rule": {"name": "规则管理", "legacy": "data:rules"},
    "logs": {"name": "系统日志", "legacy": "data:logs"},
}


def _tables():
    page = sa.table(
        "page",
        sa.column("page_id", sa.String(100)),
        sa.column("page_id_parent", sa.String(100)),
        sa.column("name", sa.String(50)),
        sa.column("path_code", sa.String(50)),
    )
    role_page = sa.table(
        "role_page",
        sa.column("role_id", sa.String(100)),
        sa.column("page_id", sa.String(100)),
    )
    return page, role_page


def _insert_missing_links(bind, role_page, role_ids: set[str], page_id: str) -> None:
    if not role_ids:
        return
    existing = set(bind.execute(
        sa.select(role_page.c.role_id).where(
            role_page.c.page_id == page_id,
            role_page.c.role_id.in_(role_ids),
        )
    ).scalars())
    missing = sorted(role_ids - existing)
    if missing:
        bind.execute(role_page.insert(), [
            {"role_id": role_id, "page_id": page_id} for role_id in missing
        ])


def _ensure_canonical_page(bind, page, role_page, has_role_page: bool, code: str, name: str) -> str:
    page_ids = list(bind.execute(
        sa.select(page.c.page_id).where(page.c.path_code == code).order_by(page.c.page_id)
    ).scalars())
    if page_ids:
        canonical_id = page_ids[0]
    else:
        canonical_id = str(uuid4())
        bind.execute(page.insert().values(
            page_id=canonical_id,
            page_id_parent=None,
            name=name,
            path_code=code,
        ))
    bind.execute(page.update().where(page.c.page_id == canonical_id).values(
        page_id_parent=None,
        name=name,
        path_code=code,
    ))

    duplicate_ids = set(page_ids[1:])
    if duplicate_ids:
        if has_role_page:
            roles = set(bind.execute(
                sa.select(role_page.c.role_id).where(role_page.c.page_id.in_(duplicate_ids))
            ).scalars())
            _insert_missing_links(bind, role_page, roles, canonical_id)
            bind.execute(role_page.delete().where(role_page.c.page_id.in_(duplicate_ids)))
        bind.execute(page.delete().where(page.c.page_id.in_(duplicate_ids)))
    return canonical_id


def upgrade() -> None:
    bind = op.get_bind()
    table_names = set(sa.inspect(bind).get_table_names())
    if "page" not in table_names:
        return
    page, role_page = _tables()
    has_role_page = "role_page" in table_names

    for code, spec in PAGE_SPECS.items():
        target_id = _ensure_canonical_page(
            bind, page, role_page, has_role_page, code, spec["name"]
        )
        legacy_ids = set(bind.execute(
            sa.select(page.c.page_id).where(page.c.path_code == spec["legacy"])
        ).scalars())
        if not legacy_ids:
            continue
        if has_role_page:
            roles = set(bind.execute(
                sa.select(role_page.c.role_id).where(role_page.c.page_id.in_(legacy_ids))
            ).scalars())
            _insert_missing_links(bind, role_page, roles, target_id)
            bind.execute(role_page.delete().where(role_page.c.page_id.in_(legacy_ids)))
        bind.execute(page.delete().where(page.c.page_id.in_(legacy_ids)))


def downgrade() -> None:
    bind = op.get_bind()
    table_names = set(sa.inspect(bind).get_table_names())
    if "page" not in table_names:
        return
    page, role_page = _tables()
    has_role_page = "role_page" in table_names
    data_parent_id = bind.execute(
        sa.select(page.c.page_id).where(page.c.path_code == "data").limit(1)
    ).scalar_one_or_none()

    for code, spec in PAGE_SPECS.items():
        legacy_id = bind.execute(
            sa.select(page.c.page_id).where(page.c.path_code == spec["legacy"]).limit(1)
        ).scalar_one_or_none()
        if legacy_id is None:
            legacy_id = str(uuid4())
            bind.execute(page.insert().values(
                page_id=legacy_id,
                page_id_parent=data_parent_id,
                name=spec["name"],
                path_code=spec["legacy"],
            ))
        if not has_role_page:
            continue
        current_ids = set(bind.execute(
            sa.select(page.c.page_id).where(page.c.path_code == code)
        ).scalars())
        if current_ids:
            roles = set(bind.execute(
                sa.select(role_page.c.role_id).where(role_page.c.page_id.in_(current_ids))
            ).scalars())
            _insert_missing_links(bind, role_page, roles, legacy_id)
