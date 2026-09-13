import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.domain import *  # noqa: F401,F403
from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.service.AssetService import AssetService
from app.domain.common.PermissionChecker import _build_viewable_set
from app.infra.DB.SQLConnection import Base


@pytest.fixture()
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _asset(
    asset_id: str,
    name: str,
    asset_type: str,
    parent_id: str | None = None,
    path: str | None = None,
) -> Asset:
    return Asset(
        asset_id=asset_id,
        asset_id_parent=parent_id,
        asset_path=path or asset_id,
        asset_type=asset_type,
        name=name,
        is_use=True,
    )


def _seed_assets(db: Session) -> None:
    db.add_all(
        [
            _asset("building-z", "Z Building", "building"),
            _asset("building-a", "A Building", "building"),
            _asset(
                "floor-z",
                "Z Floor",
                "floor",
                "building-a",
                "building-a/floor-z",
            ),
            _asset(
                "floor-a",
                "A Floor",
                "floor",
                "building-a",
                "building-a/floor-a",
            ),
            _asset(
                "room-hidden",
                "Hidden Room",
                "room",
                "floor-z",
                "building-a/floor-z/room-hidden",
            ),
        ]
    )
    db.flush()


def test_asset_tree_prefilters_permissions_and_sorts_each_level(db: Session):
    _seed_assets(db)
    statements: list[str] = []

    def capture_statement(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", capture_statement)
    try:
        tree = AssetService.query_assets_tree(
            db,
            viewable={"building-a", "floor-a", "floor-z"},
        )
    finally:
        event.remove(db.bind, "before_cursor_execute", capture_statement)

    assert [node["name"] for node in tree] == ["A Building"]
    assert [node["name"] for node in tree[0]["sub_assets"]] == [
        "A Floor",
        "Z Floor",
    ]
    assert "sub_assets" not in tree[0]["sub_assets"][1]
    assert any("WHERE assets.asset_id IN" in statement for statement in statements)


def test_empty_asset_scope_skips_tree_query(db: Session):
    statements: list[str] = []

    def capture_statement(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", capture_statement)
    try:
        assert AssetService.query_assets_tree(db, viewable=set()) == []
    finally:
        event.remove(db.bind, "before_cursor_execute", capture_statement)

    assert statements == []


def test_asset_form_sorts_by_name_before_pagination(db: Session):
    _seed_assets(db)

    first_page = AssetService.query_assets_form(db, page=1, limit=2)
    second_page = AssetService.query_assets_form(db, page=2, limit=2)

    assert [item["name"] for item in first_page["items"]] == [
        "A Building",
        "A Floor",
    ]
    assert [item["name"] for item in second_page["items"]] == [
        "Hidden Room",
        "Z Building",
    ]


def test_viewable_set_loads_all_permission_paths_in_one_query(db: Session):
    _seed_assets(db)
    statements: list[str] = []

    def capture_statement(_conn, _cursor, statement, _parameters, _context, _many):
        if "FROM assets" in statement:
            statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", capture_statement)
    try:
        viewable = _build_viewable_set(
            {"floor-a": "R", "room-hidden": "RU"},
            db,
            "user-1",
        )
    finally:
        event.remove(db.bind, "before_cursor_execute", capture_statement)

    assert viewable == {
        "building-a",
        "floor-a",
        "floor-z",
        "room-hidden",
    }
    assert len(statements) == 1
