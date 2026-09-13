import asyncio
import importlib
import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.agent.rule.schema import GenerateRequest, RuleFormDraft, ModelSuggestion, DraftPatch
from app.domain.agent.rule.service import RuleAgentService, merge_draft
from app.domain.agent.rule.tools import RuleCandidateTools
from app.domain.agent.rule.model import RuleModelClient, ModelConfigurationError
from app.domain.rule.service.RuleService import RuleService
from app.domain.rule.service.RulePermissionService import RulePermissionService
from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.repository.models.Point import Point
from app.domain.asset.repository.models.SensorPoint import SensorPoint
from app.domain.asset.repository.models.ModelPoint import ModelPoint
from app.domain.asset.repository.models.SensorModel import SensorModel
from app.domain.channel.repository.models.Control import Control
from app.infra.DB.SQLConnection import Base

permissions_module = importlib.import_module("app.domain.rule.service.RulePermissionService")


@pytest.fixture
def database(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[m.__table__ for m in (Asset, Point, SensorModel, ModelPoint, SensorPoint, Control)])
    monkeypatch.setattr(permissions_module, "get_viewable_asset_ids", lambda *_: {"building", "room", "sensor"})
    monkeypatch.setattr(permissions_module, "check_asset_instance_permission", lambda token, asset, code, db: asset == "sensor" and token == "user-token")
    with Session(engine) as db:
        for aid, parent, kind, path in [
            ("building", None, "building", "building"),
            ("room", "building", "room", "building/room"),
            ("sensor", "room", "sensor", "building/room/sensor"),
            ("hidden", "building", "sensor", "building/hidden"),
        ]:
            db.add(Asset(asset_id=aid, asset_id_parent=parent, asset_type=kind, asset_path=path, name=aid, is_use=True))
        db.add(Point(point_id="co2", point_name="二氧化碳", point_unit="ppm"))
        db.add(SensorModel(model_id="model"))
        db.add(ModelPoint(model_id="model", point_id="co2"))
        for pid, sid in [("p1", "sensor"), ("hidden-point", "hidden")]:
            db.add(SensorPoint(point_id=pid, sensor_id=sid, source_model_id="model", source_point_id="co2", point_name="二氧化碳", point_unit="ppm"))
        db.add(Control(control_id="c1", name="开启新风", type="http", channel_id="channel", asset_type="sensor", asset_id="sensor", status=True, created_at=datetime.now(timezone.utc), http_method="POST", http_path="/open"))
        db.commit()
        yield db
    engine.dispose()


def test_candidates_filter_permissions_before_returning(database):
    tools = RuleCandidateTools("user-token", database)
    result = tools.dispatch("search_points", {"keyword": "二氧化碳"})
    assert [item["point_id"] for item in result["items"]] == ["p1"]
    assert "hidden" not in json.dumps(result)
    assert tools.dispatch("search_controls", {})["items"][0]["control_id"] == "c1"
    assert RuleCandidateTools("other-user", database).dispatch("search_controls", {})["items"] == []


def test_visible_ancestor_does_not_allow_whole_subtree(database):
    permission = RulePermissionService("user-token", database)
    assert permission.readable("building")
    with pytest.raises(PermissionError, match="未授权"):
        permission.location("building")
    assert permission.location("room").asset_id == "room"
    result = RuleCandidateTools("user-token", database).dispatch("search_locations", {})
    assert [item["location_id"] for item in result["items"]] == ["room"]


def test_patch_preserves_manual_fields_and_allows_incomplete_numbers():
    current = RuleFormDraft.model_validate({"form": {"rule_name": "手动命名"}, "comparisons": [{"constant": 40}],
        "actions": [{"type": "EmailAction", "params": {"recipients": ["a@example.com"], "subject": "告警"}}]})
    result = merge_draft(current, DraftPatch(form={"trigger_duration": 600}, comparisons=[{"constant": 1000}]))
    assert result.form.rule_name == "手动命名"
    assert result.form.trigger_duration == 600
    assert result.actions == current.actions
    assert merge_draft(current, DraftPatch(comparisons=[{"constant": ""}])).comparisons[0].constant == ""
    with pytest.raises(ValidationError):
        merge_draft(current, DraftPatch(form={"invented": 1}))


def test_agent_generates_full_draft_without_persisting(database):
    class FakeModel:
        async def suggest(self, message, draft, tools, **_kwargs):
            match = tools.dispatch("search_points", {"keyword": "二氧化碳"})["items"][0]
            return ModelSuggestion.model_validate({"reply": "已填入阈值，尚缺接收人。", "patch": {
                "form": {"rule_name": "二氧化碳告警", "point_id": match["point_id"], "trigger_duration": 600},
                "sensor_id": match["sensor_id"], "comparisons": [{"constant": 1000}],
                "actions": [{"type": "EmailAction", "params": {"recipients": [], "subject": "告警", "content": "超标"}}]}})
    result = asyncio.run(RuleAgentService(FakeModel(), lambda _: "user").generate(GenerateRequest(message="二氧化碳告警"), "user-token", database))
    assert set(result) == {"conversation_id", "conversation_reset", "reply", "form_data"}
    assert result["form_data"]["sensor_id"] == "sensor"
    assert result["form_data"]["form"]["trigger_duration"] == 600
    assert not database.new and not database.dirty and not database.deleted


def test_agent_rejects_fabricated_and_unauthorized_ids(database):
    class FakeModel:
        async def suggest(self, *args, **kwargs):
            return ModelSuggestion(reply="已填写", patch=DraftPatch(form={"point_id": "hidden-point"}, sensor_id="hidden"))
    with pytest.raises(PermissionError):
        asyncio.run(RuleAgentService(FakeModel(), lambda _: "user").generate(GenerateRequest(message="监控隐藏测点"), "user-token", database))
    with pytest.raises(PermissionError):
        RuleCandidateTools("user-token", database).validate_draft(RuleFormDraft(sensor_id="sensor", form={"point_id": "invented"}))


def test_current_form_is_validated_before_model_call(database):
    class NeverCall:
        async def suggest(self, *args, **kwargs):
            raise AssertionError("must not send unauthorized form to model")
    data = GenerateRequest(message="调整", current_form={"sensor_id": "hidden"})
    with pytest.raises(PermissionError):
        asyncio.run(RuleAgentService(NeverCall(), lambda _: "user").generate(data, "user-token", database))


def test_unconfigured_model_has_actionable_message(monkeypatch):
    from types import SimpleNamespace
    model_module = importlib.import_module("app.domain.agent.rule.model")
    monkeypatch.setattr(
        model_module.llm_config_service,
        "active_runtime",
        lambda _db: (_ for _ in ()).throw(model_module.ValidationError("模型服务未配置或未激活")),
    )
    with pytest.raises(ModelConfigurationError, match="模型服务未配置"):
        asyncio.run(RuleModelClient().suggest("需求", RuleFormDraft(), SimpleNamespace(db=None), user_id="user"))


def test_existing_create_and_edit_reject_unauthorized_monitor(database):
    from test.domain.rule.test_rule_service import _config
    payload = _config().model_dump()
    payload["selector"]["point_id"] = "hidden-point"
    from app.domain.rule.schema import RuleConfig
    config = RuleConfig.model_validate(payload)
    with pytest.raises(PermissionError):
        RuleService.create(config, "user-token", database)
    with pytest.raises(PermissionError):
        RuleService.edit("rule", config, "user-token", database)


def test_generate_api_timeout_and_permission_response(monkeypatch):
    api = importlib.import_module("app.domain.agent.rule.api")
    async def slow(*args):
        await asyncio.sleep(1)
    monkeypatch.setattr(api.config, "REQUEST_TIMEOUT_SECONDS", 0.001)
    monkeypatch.setattr(api.rule_agent_service, "generate", slow)
    response = asyncio.run(api.generate_rule_draft(GenerateRequest(message="测试"), "token", None))
    assert "超时" in json.loads(response.body)["message"]
    async def forbidden(*args):
        raise PermissionError("对象不可访问")
    monkeypatch.setattr(api.rule_agent_service, "generate", forbidden)
    response = asyncio.run(api.generate_rule_draft(GenerateRequest(message="测试"), "token", None))
    assert response.status_code == 403


def test_enable_checks_monitor_before_compilation(database, monkeypatch):
    from types import SimpleNamespace
    from test.domain.rule.test_rule_service import _config
    module = importlib.import_module("app.domain.rule.service.RuleService")
    cfg = _config().model_copy(deep=True)
    cfg.selector.point_id = "hidden-point"
    row = SimpleNamespace(status="paused", rule_file_name="test.ttl")
    monkeypatch.setattr(database, "get", lambda model, key: row if model is module.Rule else None)
    monkeypatch.setattr(module.LogService, "operator_from_token", lambda *_: "user")
    monkeypatch.setattr(module.rule_rdf_service, "read", lambda *_: (cfg, "fingerprint"))
    monkeypatch.setattr(module.rule_runtime, "compile_rule", lambda *_: pytest.fail("must not compile"))
    with pytest.raises(PermissionError):
        RuleService.toggle("rule", "user-token", database)
