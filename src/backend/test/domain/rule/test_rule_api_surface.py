import json
from inspect import signature

import pytest
from fastapi import HTTPException

import app.domain.common.AuthDecorator as auth_decorator
from app.domain.common.AuthDecorator import require_page
from app.domain.log.api.LogAPI import get_log_options, list_logs
from app.domain.rule.api.RuleAPI import get_rule_options, get_rule_ttl, list_rules
from app.domain.rule.service import RuleService
from main import app


def test_rule_and_log_api_surface_is_registered_and_logs_are_read_only():
    paths = app.openapi()["paths"]
    expected_rule_methods = {
        "/rules/list": "post",
        "/rules/find/{rule_id}": "get",
        "/rules/ttl/{rule_id}": "get",
        "/rules/options": "get",
        "/rules/add": "post",
        "/rules/edit/{rule_id}": "post",
        "/rules/toggle/{rule_id}": "post",
        "/rules/drop/{rule_id}": "get",
        "/rules/events": "post",
        "/rules/tasks": "post",
    }
    for path, method in expected_rule_methods.items():
        assert method in paths[path]
    assert set(paths["/logs/list"]) == {"post"}
    assert set(paths["/logs/options"]) == {"get"}
    assert "/logs/find/{log_id}" not in paths


def test_paged_filter_endpoints_only_expose_page_and_limit_as_query_parameters():
    paths = app.openapi()["paths"]
    for path in ("/rules/list", "/rules/events", "/rules/tasks", "/logs/list"):
        operation = paths[path]["post"]
        query_names = {
            parameter["name"] for parameter in operation.get("parameters", [])
            if parameter["in"] == "query"
        }
        assert query_names == {"page", "limit"}
        assert "requestBody" in operation


def test_rule_paged_filter_contract_matches_api_document():
    paths = app.openapi()["paths"]
    expected_properties = {
        "/rules/list": {"rule_name", "status", "create_at"},
        "/rules/events": {"rule_id", "event_type", "event_time"},
        "/rules/tasks": {
            "rule_id", "event_id", "action_type", "status", "create_time", "completed_time",
        },
    }
    schemas = app.openapi()["components"]["schemas"]
    for path, expected in expected_properties.items():
        body_schema = paths[path]["post"]["requestBody"]["content"]["application/json"]["schema"]
        schema_ref = next(item["$ref"] for item in body_schema["anyOf"] if "$ref" in item)
        schema_name = schema_ref.rsplit("/", 1)[-1]
        assert set(schemas[schema_name]["properties"]) == expected
        for property_name, definition in schemas[schema_name]["properties"].items():
            if property_name.endswith("_time") or property_name == "create_at":
                date_schema = next(
                    item for item in definition.get("anyOf", [definition])
                    if item.get("type") == "string"
                )
                assert date_schema["format"] == "date"


def test_log_paged_filter_contract_matches_api_document():
    openapi = app.openapi()
    body_schema = openapi["paths"]["/logs/list"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    schema_ref = next(item["$ref"] for item in body_schema["anyOf"] if "$ref" in item)
    schema = openapi["components"]["schemas"][schema_ref.rsplit("/", 1)[-1]]
    assert set(schema["properties"]) == {"type", "level", "operator", "time"}
    time_schema = next(
        item for item in schema["properties"]["time"]["anyOf"]
        if item.get("type") == "string"
    )
    assert time_schema["format"] == "date"


def test_rule_and_log_page_dependency_returns_401_or_403(monkeypatch):
    dependency = require_page("rule").dependency
    with pytest.raises(HTTPException) as missing:
        dependency(None)
    assert missing.value.status_code == 401

    monkeypatch.setattr(auth_decorator, "check_page_permission", lambda _token, _pages: False)
    with pytest.raises(HTTPException) as denied:
        dependency("Bearer token")
    assert denied.value.status_code == 403


def test_rule_and_log_endpoints_use_new_top_level_page_codes(monkeypatch):
    captured = []
    monkeypatch.setattr(
        auth_decorator,
        "check_page_permission",
        lambda _token, pages: captured.append(tuple(pages)) or True,
    )
    for endpoint in (list_rules, get_rule_options):
        dependency = signature(endpoint).parameters["_auth"].default.dependency
        dependency("Bearer token")
    for endpoint in (list_logs, get_log_options):
        dependency = signature(endpoint).parameters["_auth"].default.dependency
        dependency("Bearer token")
    assert captured == [("rule",), ("rule",), ("logs",), ("logs",)]


def test_ttl_endpoint_returns_content_for_frontend_visualization(monkeypatch):
    monkeypatch.setattr(
        RuleService,
        "get_ttl",
        staticmethod(lambda _rule_id, _db: "@prefix sb: <urn:sb:> ."),
    )
    response = get_rule_ttl("r1", object(), None)
    assert response.status_code == 200
    assert "content-disposition" not in response.headers
    assert json.loads(response.body)["data"] == {
        "rule_id": "r1",
        "ttl": "@prefix sb: <urn:sb:> .",
    }
