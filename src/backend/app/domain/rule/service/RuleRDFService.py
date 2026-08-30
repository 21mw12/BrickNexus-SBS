from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from app.common.EnvLoader import get_env_settings
from app.common.validators import ValidationError
from app.core.utils.UUIDGenerator import uuid_generator
from app.infra.RDF.AssetRDF import EX, SB
from app.domain.rule.schema import RuleConfig


class RuleRDFService:
    """结构化规则与系统管理 TTL 之间的唯一转换入口。"""

    def __init__(self, rule_dir: Path | None = None) -> None:
        self.rule_dir = Path(rule_dir or (get_env_settings().rdf_dir / "rule"))

    def ensure_action_ids(self, config: RuleConfig) -> RuleConfig:
        data = config.model_dump(mode="json")
        for action in data["actions"]:
            action["action_id"] = action.get("action_id") or uuid_generator.random()
        return RuleConfig.model_validate(data)

    def build_graph(self, rule_id: str, config: RuleConfig) -> Graph:
        graph = Graph()
        graph.bind("sb", SB)
        graph.bind("ex", EX)
        rule = EX[f"rule_{rule_id}"]
        selector = EX[f"selector_{rule_id}_{config.selector.selector_id}"]
        condition = EX[f"condition_{rule_id}_root"]
        policy = EX[f"policy_{rule_id}"]
        graph.add((rule, RDF.type, SB.Rule))
        graph.add((rule, RDFS.label, Literal(config.rule_name)))
        graph.add((rule, RDFS.comment, Literal(config.description)))
        graph.add((rule, SB.hasSelector, selector))
        graph.add((selector, SB.selectorId, Literal(config.selector.selector_id)))
        graph.add((selector, RDF.type, SB[config.selector.type]))
        if config.selector.type == "PointIdSelector":
            graph.add((selector, SB.pointId, Literal(config.selector.point_id)))
        else:
            graph.add((selector, SB.pointDefinitionId, Literal(config.selector.point_definition_id)))
            graph.add((selector, SB.locationId, Literal(config.selector.location_id)))
            graph.add((selector, SB.locationType, Literal(config.selector.location_type)))
        graph.add((rule, SB.hasCondition, condition))
        self._emit_condition(graph, rule_id, condition, config.condition, "root")
        graph.add((rule, SB.hasTriggerPolicy, policy))
        graph.add((policy, RDF.type, SB.TriggerPolicy))
        for key, value in config.trigger_policy.model_dump().items():
            if value is not None:
                graph.add((policy, SB[key], Literal(value)))
        for action in config.actions:
            action_uri = EX[f"action_{action.action_id}"]
            graph.add((rule, SB.hasAction, action_uri))
            graph.add((action_uri, RDF.type, SB[action.type]))
            graph.add((action_uri, SB.actionId, Literal(action.action_id)))
            if action.type == "LogAction":
                graph.add((action_uri, SB.level, Literal(action.params.level)))
                graph.add((action_uri, SB.content, Literal(action.params.content)))
            elif action.type == "EmailAction":
                for recipient in action.params.recipients:
                    graph.add((action_uri, SB.recipient, Literal(str(recipient))))
                graph.add((action_uri, SB.subject, Literal(action.params.subject)))
                graph.add((action_uri, SB.content, Literal(action.params.content)))
            else:
                graph.add((action_uri, SB.controlId, Literal(action.params.control_id)))
        canonical = json.dumps(
            config.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        graph.add((rule, SB.configJson, Literal(canonical, datatype=XSD.string)))
        return graph

    def _emit_condition(self, graph: Graph, rule_id: str, uri: URIRef, node, path: str) -> None:
        graph.add((uri, RDF.type, SB[node.type]))
        graph.add((uri, SB.operator, Literal(node.operator)))
        if node.type == "Comparison":
            for side, operand in (("left", node.left), ("right", node.right)):
                operand_uri = EX[f"operand_{rule_id}_{path}_{side}"]
                graph.add((uri, SB[f"{side}Operand"], operand_uri))
                graph.add((operand_uri, RDF.type, SB[operand.type]))
                for key, value in operand.model_dump(exclude_none=True).items():
                    if key != "type":
                        graph.add((operand_uri, SB[key], Literal(value)))
            return
        for index, child in enumerate(node.children or []):
            child_path = f"{path}_{index}"
            child_uri = EX[f"condition_{rule_id}_{child_path}"]
            graph.add((uri, SB.hasChild, child_uri))
            graph.add((child_uri, SB.childIndex, Literal(index)))
            self._emit_condition(graph, rule_id, child_uri, child, child_path)

    def parse_graph(self, graph: Graph, expected_rule_id: str | None = None) -> RuleConfig:
        rules = list(graph.subjects(RDF.type, SB.Rule))
        if len(rules) != 1:
            raise ValidationError("rule RDF must contain exactly one Rule")
        rule = rules[0]
        if expected_rule_id and rule != EX[f"rule_{expected_rule_id}"]:
            raise ValidationError("rule RDF id does not match database rule_id")
        values = list(graph.objects(rule, SB.configJson))
        if len(values) != 1:
            raise ValidationError("rule RDF requires exactly one configJson")
        try:
            config = RuleConfig.model_validate(json.loads(str(values[0])))
        except Exception as exc:
            raise ValidationError(f"invalid rule RDF config: {exc}") from exc
        if not list(graph.objects(rule, SB.hasSelector)) or not list(graph.objects(rule, SB.hasCondition)):
            raise ValidationError("rule RDF structure is incomplete")
        root = graph.value(rule, SB.hasCondition)
        if graph.value(root, RDF.type) != SB[config.condition.type]:
            raise ValidationError("rule RDF condition does not match config")
        rdf_action_ids = {str(v) for a in graph.objects(rule, SB.hasAction) for v in graph.objects(a, SB.actionId)}
        if rdf_action_ids != {str(item.action_id) for item in config.actions}:
            raise ValidationError("rule RDF action definitions do not match config")
        # configJson gives deterministic Pydantic decoding, while these triples
        # remain the inspectable RDF rule definition. Require every generated
        # structural triple to be present so editing only one representation can
        # never silently change (or fail to change) runtime behavior.
        expected = self.build_graph(expected_rule_id or self._rule_id(rule), config)
        missing = [triple for triple in expected if triple not in graph]
        if missing:
            raise ValidationError("rule RDF triples do not match configJson")
        return config

    @staticmethod
    def _rule_id(rule: URIRef) -> str:
        value = str(rule)
        prefix = str(EX["rule_"])
        if not value.startswith(prefix) or len(value) == len(prefix):
            raise ValidationError("invalid rule RDF URI")
        return value[len(prefix):]

    def serialize(self, rule_id: str, config: RuleConfig) -> bytes:
        return self.build_graph(rule_id, config).serialize(format="turtle", encoding="utf-8")

    def fingerprint(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def path(self, file_name: str) -> Path:
        return self.rule_dir / file_name

    def write_atomic(self, file_name: str, data: bytes) -> None:
        self.rule_dir.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.rule_dir, prefix=".rule-", suffix=".ttl", delete=False) as f:
                temp_path = f.name
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.path(file_name))
            temp_path = None
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass

    def read(self, file_name: str, expected_rule_id: str | None = None) -> tuple[RuleConfig, str]:
        data = self.read_ttl(file_name, expected_rule_id)
        graph = Graph().parse(data=data, format="turtle")
        return self.parse_graph(graph, expected_rule_id), self.fingerprint(data)

    def read_ttl(self, file_name: str, expected_rule_id: str | None = None) -> bytes:
        path = self.path(file_name)
        if not path.exists():
            raise ValidationError(f"rule file not found: {file_name}")
        data = path.read_bytes()
        try:
            graph = Graph().parse(data=data, format="turtle")
            self.parse_graph(graph, expected_rule_id)
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError(f"invalid rule RDF: {exc}") from exc
        return data


rule_rdf_service = RuleRDFService()
