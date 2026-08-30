import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain import *  # noqa: F401,F403
from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.repository.models.AssetSensor import AssetSensor
from app.domain.asset.repository.models.AssetTerminal import AssetTerminal
from app.domain.channel.repository.models.Control import Control
from app.domain.channel.repository.models.Request import Request
from app.domain.dashboard.api import DashboardAPI
from app.domain.dashboard.service import DashboardService
from app.domain.rule.repository.models.Rule import Rule
from app.domain.user.repository.models.User import User
from app.infra.DB.SQLConnection import Base


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _asset(asset_id: str, asset_type: str, *, enabled: bool = True) -> Asset:
    return Asset(
        asset_id=asset_id,
        asset_type=asset_type,
        name=asset_id,
        is_use=enabled,
    )


def _seed(db: Session) -> None:
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            User(user_id="user-1", role_id="role-1", account="one", nickname="One", password="x"),
            User(user_id="user-2", role_id="role-1", account="two", nickname="Two", password="x"),
            Rule(
                rule_id="rule-1",
                rule_name="Rule",
                rule_file_name="rule-1.ttl",
                status="paused",
                created_at=now,
            ),
            Request(
                request_id="request-1",
                name="Request",
                type="mqtt",
                channel_id="channel-1",
                interval_seconds=60,
                status=False,
                created_at=now,
                mqtt_topic="building/data",
            ),
            _asset("building-1", "building"),
            _asset("floor-1", "floor"),
            _asset("room-disabled", "room", enabled=False),
            _asset("terminal-online", "terminal"),
            _asset("terminal-offline", "terminal"),
            _asset("terminal-disabled", "terminal", enabled=False),
            _asset("sensor-online", "sensor"),
            _asset("sensor-offline", "sensor"),
            _asset("sensor-hidden", "sensor"),
            AssetTerminal(asset_id="terminal-online", is_online=True),
            AssetTerminal(asset_id="terminal-offline", is_online=False),
            AssetTerminal(asset_id="terminal-disabled", is_online=True),
            AssetSensor(asset_id="sensor-online", is_online=True),
            AssetSensor(asset_id="sensor-offline", is_online=False),
            AssetSensor(asset_id="sensor-hidden", is_online=True),
            Control(
                control_id="control-1",
                name="Control",
                type="mqtt",
                channel_id="channel-1",
                asset_type="terminal",
                asset_id="terminal-online",
                status=False,
                created_at=now,
                mqtt_topic="building/control",
                mqtt_retained=False,
                mqtt_payload="on",
            ),
        ]
    )
    db.flush()


def _pages(result: dict) -> dict[str, dict]:
    return {page["key"]: page for page in result["page"]}


def test_overview_merges_description_usage_and_statistics(db: Session):
    _seed(db)

    result = DashboardService.get_overview(
        db,
        {"user", "asset", "channel:requests", "rule"},
        {"building-1", "floor-1", "room-disabled", "terminal-online", "sensor-online"},
    )
    pages = _pages(result)

    assert set(pages) == {"user", "asset", "channel:requests", "rule"}
    assert pages["asset"]["item"] == "资产中心"
    assert all(page["description"] for page in result["page"])
    assert all(page["usage"] for page in result["page"])
    assert result["statistics"] == {
        "user_count": 2,
        "request_count": 1,
        "control_count": 1,
        "rule_count": 1,
        "building": {"enabled_total": 1},
        "floor": {"enabled_total": 1},
        "room": {"enabled_total": 0},
        "terminal": {"enabled_total": 1, "online_count": 1},
        "sensor": {"enabled_total": 1, "online_count": 1},
    }


def test_root_asset_scope_counts_all_enabled_assets(db: Session):
    _seed(db)

    assets = DashboardService.get_overview(db, set(), None)["statistics"]

    assert assets["building"] == {"enabled_total": 1}
    assert assets["floor"] == {"enabled_total": 1}
    assert assets["room"] == {"enabled_total": 0}
    assert assets["terminal"] == {"enabled_total": 2, "online_count": 1}
    assert assets["sensor"] == {"enabled_total": 3, "online_count": 2}


def test_empty_asset_scope_returns_zero_assets_but_keeps_global_counts(db: Session):
    _seed(db)

    result = DashboardService.get_overview(
        db,
        set(),
        set(),
    )

    assert result["page"] == []
    assert result["statistics"]["user_count"] == 2
    assert result["statistics"]["request_count"] == 1
    assert result["statistics"]["control_count"] == 1
    assert result["statistics"]["rule_count"] == 1
    for asset_type in DashboardService.ASSET_TYPES:
        assert result["statistics"][asset_type]["enabled_total"] == 0
    assert result["statistics"]["terminal"]["online_count"] == 0
    assert result["statistics"]["sensor"]["online_count"] == 0


def test_page_permissions_do_not_limit_global_statistics(
    db: Session,
    monkeypatch,
):
    _seed(db)
    counted_models = []
    original_count = DashboardService._count

    def track_count(session, model):
        counted_models.append(model)
        return original_count(session, model)

    monkeypatch.setattr(DashboardService, "_count", staticmethod(track_count))

    result = DashboardService.get_overview(
        db,
        {"data:history"},
        set(),
    )

    assert [page["key"] for page in result["page"]] == ["data:history"]
    assert result["statistics"]["user_count"] == 2
    assert result["statistics"]["request_count"] == 1
    assert result["statistics"]["control_count"] == 1
    assert result["statistics"]["rule_count"] == 1
    assert counted_models == [User, Request, Control, Rule]


def test_api_uses_login_asset_scope_without_page_permission(db: Session, monkeypatch):
    _seed(db)
    seen = {}

    def viewable(token, session):
        seen["token"] = token
        seen["session"] = session
        return {"terminal-online"}

    def page_allowed(token, page_codes):
        seen.setdefault("page_checks", []).append(tuple(page_codes))
        return page_codes[0] in {"asset:tree", "rule"}

    monkeypatch.setattr(DashboardAPI, "check_page_permission", page_allowed)
    monkeypatch.setattr(DashboardAPI, "get_viewable_asset_ids", viewable)

    response = DashboardAPI.get_dashboard_overview("Bearer token", db)
    body = json.loads(response.body)
    pages = _pages(body["data"])

    assert response.status_code == 200
    assert body["success"] is True
    assert set(pages) == {"asset:tree", "rule"}
    assert body["data"]["statistics"]["terminal"] == {
        "enabled_total": 1,
        "online_count": 1,
    }
    assert body["data"]["statistics"]["user_count"] == 2
    assert seen["token"] == "Bearer token"
    assert seen["session"] is db
    assert len(seen["page_checks"]) == len(DashboardService.PAGES)


def test_api_rejects_invalid_login(db: Session, monkeypatch):
    monkeypatch.setattr(
        DashboardAPI,
        "get_viewable_asset_ids",
        lambda token, session: (_ for _ in ()).throw(ValidationError("unauthorized")),
    )

    response = DashboardAPI.get_dashboard_overview(None, db)
    body = json.loads(response.body)

    assert response.status_code == 403
    assert body["success"] is False
    assert body["message"] == "unauthorized"
