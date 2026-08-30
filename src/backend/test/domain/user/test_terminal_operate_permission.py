import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain import *  # noqa: F401,F403
from app.domain.asset.repository.models.Asset import Asset
from app.domain.auth.repository.models.RoleAsset import RoleAsset
from app.domain.auth.repository.models.UserAsset import UserAsset
from app.domain.auth.service.RoleAssetService import RoleAssetService
from app.domain.auth.service.UserAssetService import UserAssetService
from app.domain.common import PermissionChecker
from app.domain.user.schema.AssetPermissionSchema import (
    AssetIdPermissionNode,
    AssetPermissionInputSchema,
)
from app.domain.user.service.UserService import UserService
from app.infra.DB.SQLConnection import Base


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Asset(asset_id="room-1", asset_type="room", name="Room", is_use=True),
                Asset(
                    asset_id="terminal-1",
                    asset_type="terminal",
                    name="Terminal",
                    is_use=True,
                ),
                Asset(
                    asset_id="sensor-1",
                    asset_type="sensor",
                    name="Sensor",
                    is_use=True,
                ),
            ]
        )
        session.flush()
        yield session


def test_role_operate_permission_accepts_terminal_and_sensor(db: Session) -> None:
    permission = AssetPermissionInputSchema(
        part_asset_id=[
            AssetIdPermissionNode(asset_id="terminal-1", permission="RO"),
            AssetIdPermissionNode(asset_id="sensor-1", permission="RO"),
        ]
    )

    assert RoleAssetService().save_role_asset_permission(
        "role-1", permission, db
    ) == 2
    records = db.query(RoleAsset).all()
    assert {record.asset_id for record in records if record.perm_operate} == {
        "terminal-1",
        "sensor-1",
    }


def test_role_operate_permission_rejects_non_operable_asset(db: Session) -> None:
    permission = AssetPermissionInputSchema(
        part_asset_id=[AssetIdPermissionNode(asset_id="room-1", permission="RO")]
    )

    with pytest.raises(ValidationError, match="terminal or sensor"):
        RoleAssetService().save_role_asset_permission("role-1", permission, db)


def test_terminal_creator_receives_operate_permission(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(UserService, "refresh_user_cache", lambda *_args: 1)

    UserAssetService.grant_creator_permissions(
        "user-1", "terminal-1", "terminal", db
    )
    record = db.query(UserAsset).filter_by(asset_id="terminal-1").one()

    assert record.perm_retrieve is True
    assert record.perm_update is True
    assert record.perm_delete is True
    assert record.perm_operate is True


def test_user_operate_permission_rejects_room(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(UserService, "refresh_user_cache", lambda *_args: 1)

    with pytest.raises(ValidationError, match="terminal or sensor"):
        UserAssetService.grant_user_asset_permission(
            "user-1", "room-1", {"perm_retrieve": True, "perm_operate": True}, db
        )


def test_role_and_user_asset_permissions_are_unioned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        PermissionChecker,
        "_get_login_cache",
        lambda _token: {"role_id": "role-1", "user_id": "user-1"},
    )
    monkeypatch.setattr(
        PermissionChecker, "_get_role_asset_perms", lambda _role_id: {"t-1": "RO"}
    )
    monkeypatch.setattr(
        PermissionChecker, "_get_user_asset_perms", lambda _user_id: {"t-1": "RU"}
    )

    assert PermissionChecker._get_union_asset_perms("token") == {"t-1": "RUO"}
