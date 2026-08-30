from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain import *  # noqa: F401,F403
from app.domain.asset.repository.AssetTerminalRepository import AssetTerminalRepository
from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.repository.models.AssetTerminal import AssetTerminal
from app.domain.asset.service.AssetService import AssetService
from app.domain.channel.repository.RequestRepository import RequestRepository
from app.domain.channel.repository.models.Request import Request
from app.domain.channel.schema.ChannelSchema import HttpChannelAddSchema
from app.domain.channel.schema.RequestSchema import RequestAddSchema, RequestEditSchema
from app.domain.channel.schema.TerminalRequestSchema import TerminalTreeEditSchema
from app.domain.channel.service.ChannelService import ChannelService
from app.domain.channel.service.RequestService import RequestService
from app.domain.channel.service.TerminalRequestService import TerminalRequestService
from app.domain.collector.loader.request_loader import request_loader
from app.infra.DB.SQLConnection import Base


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _http_channel(db: Session) -> str:
    return ChannelService.add_http(db, HttpChannelAddSchema(base_url="https://example.com"))["channel_http_id"]


def _http_request(db: Session) -> dict:
    return RequestService.create_request(
        RequestAddSchema(
            name="test request", type="http", channel_id=_http_channel(db),
            interval_seconds=60, http_method="GET", http_path="/measurements",
        ), db,
    )


def test_new_request_defaults_to_stopped_state(db: Session) -> None:
    result = _http_request(db)
    assert result["status"] is False
    assert result["created_at"] is not None
    assert result["channel"]["base_url"] == "https://example.com"


def test_request_repository_allows_status_toggle() -> None:
    request = Request(name="test", type="http", channel_id="channel", http_method="GET", http_path="/v")
    values = {"status": True}
    RequestRepository()._before_update(request, values, db=None)  # type: ignore[arg-type]
    assert values == {"status": True}


def test_toggle_starts_and_stops_normalized_runtime(monkeypatch, db: Session) -> None:
    result = _http_request(db)
    started, stopped = [], []
    monkeypatch.setattr(request_loader, "start", lambda item: started.append(item) or {})
    monkeypatch.setattr(request_loader, "stop", lambda kind, ident: stopped.append((kind, ident)))

    active = RequestService.toggle_active(result["request_id"], db)
    assert active["status"] is True
    assert started[0].request_info["url"] == "https://example.com/measurements"

    inactive = RequestService.toggle_active(result["request_id"], db)
    assert inactive["status"] is False
    assert stopped == [("http", result["request_id"])]


def test_running_request_cannot_be_edited_or_deleted(monkeypatch, db: Session) -> None:
    result = _http_request(db)
    monkeypatch.setattr(request_loader, "start", lambda item: {})
    RequestService.toggle_active(result["request_id"], db)
    with pytest.raises(ValidationError, match="cannot be edited"):
        RequestService.edit_request(result["request_id"], RequestEditSchema(name="changed"), db)
    with pytest.raises(ValidationError, match="cannot be deleted"):
        RequestService.delete_request(result["request_id"], db)


@pytest.mark.parametrize("invalid_value", [0, -1])
def test_request_rejects_invalid_interval(invalid_value) -> None:
    with pytest.raises(PydanticValidationError):
        RequestAddSchema(
            name="mqtt request", type="mqtt", channel_id="channel",
            mqtt_topic="building/one", interval_seconds=invalid_value,
        )


class _TerminalRequestDb:
    def __init__(self, terminal_request_id, requests):
        self.terminal_request_id = terminal_request_id
        self.requests = requests

    def get(self, model, ident):
        if model is Asset: return SimpleNamespace(asset_id=ident, asset_type="terminal")
        if model is AssetTerminal: return SimpleNamespace(asset_id=ident, request_id=self.terminal_request_id)
        if model is Request: return self.requests.get(ident)
        return None


def test_terminal_cannot_bind_to_running_request() -> None:
    db = _TerminalRequestDb(None, {"request-1": SimpleNamespace(is_active=True)})
    with pytest.raises(ValidationError, match="cannot bind"):
        TerminalRequestService.update_tree("terminal-1", TerminalTreeEditSchema(request_id="request-1"), db)


def test_terminal_bound_to_running_request_cannot_change_structure() -> None:
    db = _TerminalRequestDb("request-1", {"request-1": SimpleNamespace(is_active=True)})
    with pytest.raises(ValidationError, match="cannot be edited"):
        TerminalRequestService.update_tree("terminal-1", TerminalTreeEditSchema(request_id=None), db)


def test_terminal_repository_does_not_depend_on_request_model() -> None:
    db = _TerminalRequestDb(None, {})
    values = {"request_id": "request-1"}
    AssetTerminalRepository()._before_update(SimpleNamespace(asset_id="terminal-1"), values, db)
    assert values == {"request_id": "request-1"}


def test_asset_service_rejects_running_request_binding() -> None:
    db = _TerminalRequestDb(None, {"request-1": SimpleNamespace(is_active=True)})
    with pytest.raises(ValidationError, match="cannot bind"):
        AssetService._validate_terminal_request_binding(db, "request-1")
