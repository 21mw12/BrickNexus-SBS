from rdflib import Graph
from rdflib.namespace import RDF
import pytest

from app.common.validators import ValidationError
from app.domain.rule.schema import RuleConfig
from app.domain.rule.service.RuleRDFService import RuleRDFService
from app.domain.rule.service.RuleOptionsService import RuleOptionsService
from app.infra.RDF.AssetRDF import SB


def test_json_ttl_round_trip_generates_action_ids_and_structure(tmp_path):
    service = RuleRDFService(tmp_path)
    config = RuleConfig.model_validate({
        "rule_name": "高温", "description": "test",
        "selector": {"selector_id": "monitor", "type": "PointIdSelector", "point_id": "p1"},
        "condition": {"type": "Logical", "operator": "AND", "children": [
            {"type": "Comparison", "operator": "GreaterThan", "left": {"type": "PointValue", "selector_id": "monitor"}, "right": {"type": "ConstantValue", "value": 40}},
            {"type": "Comparison", "operator": "LessThan", "left": {"type": "PointValue", "selector_id": "monitor"}, "right": {"type": "ConstantValue", "value": 50}},
        ]},
        "actions": [{"type": "LogAction", "params": {"level": "WARNING", "content": "{{$.value}}"}}],
    })
    config = service.ensure_action_ids(config)
    data = service.serialize("r1", config)
    graph = Graph().parse(data=data, format="turtle")
    assert len(list(graph.subjects(predicate=SB.leftOperand))) == 2
    service.write_atomic("r1.ttl", data)
    loaded, fingerprint = service.read("r1.ttl", "r1")
    assert loaded.actions[0].action_id == config.actions[0].action_id
    assert len(fingerprint) == 64


def test_rule_rdf_rejects_config_and_triple_mismatch(tmp_path):
    service = RuleRDFService(tmp_path)
    config = RuleConfig.model_validate({
        "rule_name": "高温", "description": "test",
        "selector": {"selector_id": "monitor", "type": "PointIdSelector", "point_id": "p1"},
        "condition": {
            "type": "Comparison", "operator": "GreaterThan",
            "left": {"type": "PointValue", "selector_id": "monitor"},
            "right": {"type": "ConstantValue", "value": 40},
        },
        "actions": [{"type": "LogAction", "params": {"level": "WARNING", "content": "{{$.value}}"}}],
    })
    config = service.ensure_action_ids(config)
    graph = service.build_graph("r1", config)
    selector = next(graph.objects(None, SB.hasSelector))
    graph.remove((selector, RDF.type, SB.PointIdSelector))
    with pytest.raises(ValidationError, match="triples do not match"):
        service.parse_graph(graph, "r1")


def test_semantic_selector_json_ttl_round_trip(tmp_path):
    service = RuleRDFService(tmp_path)
    config = RuleConfig.model_validate({
        "rule_name": "三楼温度", "description": "semantic",
        "selector": {
            "selector_id": "monitor",
            "type": "SemanticPointSelector",
            "point_definition_id": "global-temp-c",
            "location_id": "floor-3",
            "location_type": "floor",
        },
        "condition": {
            "type": "Comparison", "operator": "GreaterThan",
            "left": {"type": "PointValue", "selector_id": "monitor"},
            "right": {"type": "ConstantValue", "value": 40},
        },
        "actions": [{"type": "LogAction", "params": {"level": "WARNING", "content": "{{$.point_name}}"}}],
    })
    config = service.ensure_action_ids(config)
    graph = service.build_graph("r-semantic", config)
    selector = next(graph.objects(None, SB.hasSelector))
    assert (selector, RDF.type, SB.SemanticPointSelector) in graph
    assert str(graph.value(selector, SB.pointDefinitionId)) == "global-temp-c"
    assert str(graph.value(selector, SB.locationId)) == "floor-3"
    assert str(graph.value(selector, SB.locationType)) == "floor"
    loaded = service.parse_graph(graph, "r-semantic")
    assert loaded.selector == config.selector


def test_semantic_selector_rejects_non_spatial_location_type():
    data = {
        "rule_name": "invalid", "description": "",
        "selector": {
            "selector_id": "monitor", "type": "SemanticPointSelector",
            "point_definition_id": "global-temp-c", "location_id": "sensor-1",
            "location_type": "sensor",
        },
        "condition": {
            "type": "Comparison", "operator": "GreaterThan",
            "left": {"type": "PointValue", "selector_id": "monitor"},
            "right": {"type": "ConstantValue", "value": 40},
        },
        "actions": [{"type": "LogAction", "params": {"level": "WARNING", "content": "x"}}],
    }
    with pytest.raises(Exception, match="location_type"):
        RuleConfig.model_validate(data)


def test_rule_options_cover_every_backend_capability():
    RuleOptionsService.assert_matches_schema()
    options = RuleOptionsService.get_options()
    assert options["schema_version"] == "1.1"
    selectors = {item["value"]: item for item in options["selector_types"]}
    selector = selectors["PointIdSelector"]
    assert selector["asset_source"]["tree_endpoint"] == "GET /assets/tree"
    assert selector["asset_source"]["items_field"] == "sensor_points"
    semantic = selectors["SemanticPointSelector"]
    assert semantic["point_definition_source"]["list_endpoint"].startswith("GET /points/list")
    assert semantic["location_source"]["allowed_types"] == ["building", "floor", "room"]
    assert semantic["location_source"]["include_descendants"] is True
    assert {item["value"] for item in options["action_types"]} == {
        "LogAction", "EmailAction", "SensorControlAction"
    }


def test_email_and_control_actions_round_trip_with_inspectable_triples(tmp_path):
    service = RuleRDFService(tmp_path)
    config = RuleConfig.model_validate({
        "rule_name": "联动", "description": "",
        "selector": {"selector_id": "monitor", "type": "PointIdSelector", "point_id": "p1"},
        "condition": {
            "type": "Comparison", "operator": "GreaterThan",
            "left": {"type": "PointValue", "selector_id": "monitor"},
            "right": {"type": "ConstantValue", "value": 40},
        },
        "actions": [
            {"type": "EmailAction", "params": {
                "recipients": ["a@example.com", "b@example.com"],
                "subject": "高温", "content": "{{$.point_name}}={{$.value}}",
            }},
            {"type": "SensorControlAction", "params": {"control_id": "control-1"}},
        ],
    })
    config = service.ensure_action_ids(config)
    graph = service.build_graph("r-actions", config)
    email_uri = next(graph.subjects(RDF.type, SB.EmailAction))
    control_uri = next(graph.subjects(RDF.type, SB.SensorControlAction))
    assert {str(value) for value in graph.objects(email_uri, SB.recipient)} == {
        "a@example.com", "b@example.com"
    }
    assert str(graph.value(email_uri, SB.subject)) == "高温"
    assert str(graph.value(control_uri, SB.controlId)) == "control-1"
    assert service.parse_graph(graph, "r-actions") == config


@pytest.mark.parametrize("recipients", [[], ["not-an-email"], ["a@example.com"] * 51])
def test_email_action_rejects_invalid_recipients(recipients):
    with pytest.raises(Exception):
        RuleConfig.model_validate({
            "rule_name": "invalid", "description": "",
            "selector": {"selector_id": "monitor", "type": "PointIdSelector", "point_id": "p1"},
            "condition": {
                "type": "Comparison", "operator": "GreaterThan",
                "left": {"type": "PointValue", "selector_id": "monitor"},
                "right": {"type": "ConstantValue", "value": 40},
            },
            "actions": [{"type": "EmailAction", "params": {
                "recipients": recipients, "subject": "x", "content": "x",
            }}],
        })
