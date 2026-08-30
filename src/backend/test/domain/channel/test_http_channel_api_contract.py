import json

from app.domain.channel.api import ControlAPI
from main import app


def test_http_channel_routes_replace_api_channel_routes() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/channel/http/list",
        "/channel/http/find/{channel_http_id}",
        "/channel/http/add",
        "/channel/http/edit/{channel_http_id}",
        "/channel/http/drop/{channel_http_id}",
    }
    assert expected <= set(paths)
    assert not any(path.startswith("/channel/api/") for path in paths)


def test_control_api_uses_polymorphic_asset_binding_and_type_filter() -> None:
    openapi = app.openapi()
    schemas = openapi["components"]["schemas"]

    list_body = openapi["paths"]["/control/list"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    query_ref = next(item["$ref"] for item in list_body["anyOf"] if "$ref" in item)
    query_schema = schemas[query_ref.rsplit("/", 1)[-1]]
    assert set(query_schema["properties"]) == {
        "name", "type", "status", "asset_type", "asset_id"
    }
    assert "sensor_id" not in query_schema["properties"]

    add_schema = schemas["ControlAddSchema"]
    assert {"asset_type", "asset_id"} <= set(add_schema["required"])
    assert "sensor_id" not in add_schema["properties"]


def test_control_toggle_only_returns_success_flag(monkeypatch) -> None:
    class FakeDb:
        def commit(self):
            pass

        def rollback(self):
            pass

    monkeypatch.setattr(
        ControlAPI.ControlService,
        "get_bound_asset_id",
        lambda *_args: "terminal-1",
    )
    monkeypatch.setattr(
        ControlAPI, "check_asset_instance_permission", lambda *_args: True
    )
    monkeypatch.setattr(ControlAPI.ControlService, "toggle", lambda *_args: True)

    response = ControlAPI.toggle_control(
        authorization="Bearer token", control_id="control-1", db=FakeDb()
    )
    payload = json.loads(response.body)

    assert payload["data"] == {"ok": True}


def test_control_list_returns_forbidden_for_invisible_requested_asset(
    monkeypatch,
) -> None:
    class FakeDb:
        def commit(self):
            pass

        def rollback(self):
            pass

    monkeypatch.setattr(
        ControlAPI, "check_asset_instance_permission", lambda *_args: False
    )

    response = ControlAPI.list_controls(
        authorization="Bearer token",
        page=1,
        limit=20,
        filters=ControlAPI.ControlQuerySchema(
            status=True, asset_type="sensor", asset_id="sensor-1"
        ),
        db=FakeDb(),
    )
    payload = json.loads(response.body)

    assert response.status_code == 403
    assert payload["message"] == "no view permission for this asset"
