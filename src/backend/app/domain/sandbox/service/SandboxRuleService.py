from __future__ import annotations

import copy
import shutil
from datetime import datetime, timezone
from pathlib import Path

from rdflib import Graph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.EnvLoader import get_env_settings
from app.common.validators import ValidationError
from app.core.utils.UUIDGenerator import uuid_generator
from app.domain.rule.schema import RuleConfig
from app.domain.rule.service.RuleRDFService import RuleRDFService
from app.domain.sandbox.repository.models import Sandbox, SandboxMeasurement
from app.domain.sandbox.schema import SandboxConfig
from .SandboxDataService import sandbox_point_ids


class SandboxRuleService:
    ROOT = get_env_settings().rdf_dir / "sandbox_rule"

    @classmethod
    def rdf_service(cls, sandbox_id: str) -> RuleRDFService:
        return RuleRDFService(cls.ROOT / sandbox_id)

    @staticmethod
    def _sandbox(sandbox_id: str, db: Session) -> Sandbox:
        row = db.get(Sandbox, sandbox_id)
        if row is None:
            raise ValidationError("sandbox not found")
        return row

    @staticmethod
    def _validate_config(rule: RuleConfig, sandbox: Sandbox) -> None:
        if rule.selector.type != "PointIdSelector":
            raise ValidationError("sandbox rule only supports PointIdSelector")
        if rule.selector.point_id not in sandbox_point_ids(sandbox.config):
            raise ValidationError("rule point does not belong to sandbox")

    @staticmethod
    def _ref(config: dict, rule_id: str) -> dict | None:
        return next(
            (item for item in config.get("sandbox_rule", []) if item["rule_id"] == rule_id),
            None,
        )

    @classmethod
    def list_rules(cls, sandbox_id: str, db: Session) -> list[dict]:
        sandbox = cls._sandbox(sandbox_id, db)
        service = cls.rdf_service(sandbox_id)
        result = []
        for ref in sandbox.config.get("sandbox_rule", []):
            try:
                config, _ = service.read(f"{ref['rule_id']}.ttl", ref["rule_id"])
                result.append({
                    **ref,
                    "rule_name": config.rule_name,
                    "description": config.description,
                    "point_id": config.selector.point_id,
                })
            except Exception as exc:
                result.append({**ref, "rule_name": ref["rule_id"], "error": str(exc)})
        return result

    @classmethod
    def find(cls, sandbox_id: str, rule_id: str, db: Session) -> dict:
        sandbox = cls._sandbox(sandbox_id, db)
        ref = cls._ref(sandbox.config, rule_id)
        if ref is None:
            raise ValidationError("sandbox rule not found")
        config, fingerprint = cls.rdf_service(sandbox_id).read(
            f"{rule_id}.ttl", rule_id
        )
        return {**ref, "fingerprint": fingerprint, "config": config.model_dump(mode="json")}

    @classmethod
    def create(cls, sandbox_id: str, rule: RuleConfig, db: Session) -> dict:
        sandbox = cls._sandbox(sandbox_id, db)
        if sandbox.state:
            raise ValidationError("运行中的沙盒不能创建或修改规则，请先暂停沙盒")
        cls._validate_config(rule, sandbox)
        service = cls.rdf_service(sandbox_id)
        rule = service.ensure_action_ids(rule)
        rule_id = uuid_generator.random()
        data = service.serialize(rule_id, rule)
        service.parse_graph(Graph().parse(data=data, format="turtle"), rule_id)
        path = service.path(f"{rule_id}.ttl")
        try:
            service.write_atomic(path.name, data)
            config = copy.deepcopy(sandbox.config)
            config.setdefault("sandbox_rule", []).append({
                "rule_id": rule_id, "state": True, "effective_tick": sandbox.tick,
            })
            sandbox.config = SandboxConfig.model_validate(config).model_dump(mode="json")
            db.add(sandbox)
            db.flush()
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return cls.find(sandbox_id, rule_id, db)

    @classmethod
    def edit(
        cls, sandbox_id: str, rule_id: str, rule: RuleConfig, db: Session
    ) -> dict:
        sandbox = cls._sandbox(sandbox_id, db)
        if sandbox.state:
            raise ValidationError("运行中的沙盒不能创建或修改规则，请先暂停沙盒")
        ref = cls._ref(sandbox.config, rule_id)
        if ref is None:
            raise ValidationError("sandbox rule not found")
        cls._validate_config(rule, sandbox)
        service = cls.rdf_service(sandbox_id)
        rule = service.ensure_action_ids(rule)
        data = service.serialize(rule_id, rule)
        service.parse_graph(Graph().parse(data=data, format="turtle"), rule_id)
        path = service.path(f"{rule_id}.ttl")
        old = path.read_bytes() if path.exists() else None
        try:
            service.write_atomic(path.name, data)
            config = copy.deepcopy(sandbox.config)
            config_ref = cls._ref(config, rule_id)
            config_ref["effective_tick"] = sandbox.tick
            sandbox.config = SandboxConfig.model_validate(config).model_dump(mode="json")
            db.add(sandbox)
            db.flush()
        except Exception:
            if old is not None:
                service.write_atomic(path.name, old)
            raise
        return cls.find(sandbox_id, rule_id, db)

    @classmethod
    def toggle(cls, sandbox_id: str, rule_id: str, db: Session) -> dict:
        sandbox = cls._sandbox(sandbox_id, db)
        if sandbox.state:
            raise ValidationError("运行中的沙盒不能创建或修改规则，请先暂停沙盒")
        config = copy.deepcopy(sandbox.config)
        ref = cls._ref(config, rule_id)
        if ref is None:
            raise ValidationError("sandbox rule not found")
        ref["state"] = not ref["state"]
        if ref["state"]:
            ref["effective_tick"] = sandbox.tick
        sandbox.config = SandboxConfig.model_validate(config).model_dump(mode="json")
        db.add(sandbox)
        db.flush()
        return cls.find(sandbox_id, rule_id, db)

    @classmethod
    def delete(cls, sandbox_id: str, rule_id: str, db: Session) -> bool:
        sandbox = cls._sandbox(sandbox_id, db)
        if sandbox.state:
            raise ValidationError("运行中的沙盒不能创建或修改规则，请先暂停沙盒")
        config = copy.deepcopy(sandbox.config)
        ref = cls._ref(config, rule_id)
        if ref is None:
            raise ValidationError("sandbox rule not found")
        service = cls.rdf_service(sandbox_id)
        path = service.path(f"{rule_id}.ttl")
        backup = path.with_name(f".{path.name}.deleting")
        if path.exists():
            path.replace(backup)
        try:
            config["sandbox_rule"] = [
                item for item in config["sandbox_rule"] if item["rule_id"] != rule_id
            ]
            sandbox.config = SandboxConfig.model_validate(config).model_dump(mode="json")
            db.add(sandbox)
            db.flush()
        except Exception:
            if backup.exists():
                backup.replace(path)
            raise
        backup.unlink(missing_ok=True)
        return True

    @classmethod
    def ttl(cls, sandbox_id: str, rule_id: str, db: Session) -> str:
        sandbox = cls._sandbox(sandbox_id, db)
        if cls._ref(sandbox.config, rule_id) is None:
            raise ValidationError("sandbox rule not found")
        return cls.rdf_service(sandbox_id).read_ttl(
            f"{rule_id}.ttl", rule_id
        ).decode("utf-8")

    @classmethod
    def remove_directory(cls, sandbox_id: str) -> None:
        path = cls.ROOT / sandbox_id
        if path.exists():
            shutil.rmtree(path)


sandbox_rule_service = SandboxRuleService()
