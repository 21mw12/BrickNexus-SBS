from __future__ import annotations

import copy
import json
import statistics
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.core.utils.UUIDGenerator import uuid_generator
from app.domain.asset.repository.models import (
    Asset, AssetSensor, ModelPoint, Point, SensorModel, SensorPoint,
)
from app.domain.common.PermissionChecker import get_viewable_asset_ids
from app.domain.data.repository.models import Measurement
from app.domain.sandbox.repository import SandboxRepository
from app.domain.sandbox.repository.models import Sandbox
from app.domain.sandbox.schema import SandboxConfig, SandboxCreateSchema, SandboxEditSchema
from .SandboxDataService import sandbox_point_ids
from .SandboxRuleService import SandboxRuleService


class SandboxService:
    def __init__(self, repository: SandboxRepository | None = None) -> None:
        self.repository = repository or SandboxRepository()

    @staticmethod
    def as_dict(row: Sandbox) -> dict:
        return {
            "sandbox_id": row.sandbox_id,
            "sandbox_name": row.sandbox_name,
            "config": row.config,
            "state": row.state,
            "tick": row.tick,
            "description": row.description,
            "created_at": row.created_at,
        }

    def list(self, db: Session, page: int, limit: int) -> dict:
        total, rows = self.repository.list_page(db, page, limit)
        return {"total": total, "items": [self.as_dict(row) for row in rows]}

    def find(self, sandbox_id: str, db: Session) -> dict:
        row = db.get(Sandbox, sandbox_id)
        if row is None:
            raise ValidationError("sandbox not found")
        return self.as_dict(row)

    def create(self, data: SandboxCreateSchema, db: Session) -> dict:
        config = self._canonicalize_config(data.config, db)
        config["sandbox_rule"] = []
        row = Sandbox(
            sandbox_id=uuid_generator.random(),
            sandbox_name=data.sandbox_name,
            config=config,
            state=False,
            tick=0,
            description=data.description,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.flush()
        return self.as_dict(row)

    def edit(self, sandbox_id: str, data: SandboxEditSchema, db: Session) -> dict:
        row = db.get(Sandbox, sandbox_id)
        if row is None:
            raise ValidationError("sandbox not found")
        if row.state:
            raise ValidationError("running sandbox cannot be edited")
        config = self._canonicalize_config(data.config, db, row.config)
        config["sandbox_rule"] = copy.deepcopy(row.config.get("sandbox_rule", []))
        new_points = sandbox_point_ids(config)
        rule_service = SandboxRuleService.rdf_service(sandbox_id)
        for ref in config["sandbox_rule"]:
            rule, _ = rule_service.read(f"{ref['rule_id']}.ttl", ref["rule_id"])
            if rule.selector.point_id not in new_points:
                raise ValidationError(
                    f"point is referenced by sandbox rule: {rule.selector.point_id}"
                )
        row.sandbox_name = data.sandbox_name
        row.description = data.description
        row.config = SandboxConfig.model_validate(config).model_dump(mode="json")
        db.add(row)
        db.flush()
        return self.as_dict(row)

    def delete(self, sandbox_id: str, db: Session) -> bool:
        row = db.get(Sandbox, sandbox_id)
        if row is None:
            raise ValidationError("sandbox not found")
        if row.state:
            raise ValidationError("running sandbox cannot be deleted")
        db.delete(row)
        db.flush()
        return True

    def export_config(self, sandbox_id: str, db: Session) -> bytes:
        row = db.get(Sandbox, sandbox_id)
        if row is None:
            raise ValidationError("sandbox not found")
        document = {"version": 1, "terminals": row.config.get("terminals", [])}
        return json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")

    def import_config(
        self,
        sandbox_name: str,
        description: str | None,
        content: bytes,
        db: Session,
    ) -> dict:
        try:
            document = json.loads(content.decode("utf-8"))
        except Exception as exc:
            raise ValidationError("invalid sandbox JSON") from exc
        if not isinstance(document, dict) or document.get("version") != 1:
            raise ValidationError("unsupported sandbox export version")
        config = SandboxConfig.model_validate({
            "speed": 1,
            "terminals": document.get("terminals"),
            "sandbox_rule": [],
        })
        # Version 1 exports can contain free-form sensors. They remain runnable,
        # but the regular create/edit APIs require a concrete sensor model.
        row = Sandbox(
            sandbox_id=uuid_generator.random(), sandbox_name=sandbox_name,
            config=config.model_dump(mode="json"), state=False, tick=0,
            description=description, created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.flush()
        return self.as_dict(row)

    @staticmethod
    def _existing_points(config: dict | None) -> dict[str, tuple[str | None, str | None]]:
        result: dict[str, tuple[str | None, str | None]] = {}
        for terminal in (config or {}).get("terminals", []):
            for sensor in terminal.get("sensors", []):
                for point in sensor.get("points", []):
                    point_id = point.get("id")
                    if point_id:
                        result[point_id] = (sensor.get("model_id"), point.get("source_point_id"))
        return result

    @classmethod
    def _canonicalize_config(
        cls, config_model: SandboxConfig, db: Session, existing: dict | None = None,
    ) -> dict:
        config = config_model.model_dump(mode="json")
        existing_points = cls._existing_points(existing)
        for terminal in config["terminals"]:
            for sensor in terminal["sensors"]:
                model_id = sensor.get("model_id")
                if not model_id or db.get(SensorModel, model_id) is None:
                    raise ValidationError("sensor model is required")
                definitions = list(db.scalars(
                    select(ModelPoint)
                    .join(Point, Point.point_id == ModelPoint.point_id)
                    .where(ModelPoint.model_id == model_id)
                    .order_by(Point.point_name.asc(), ModelPoint.point_id.asc())
                ).all())
                if not definitions:
                    raise ValidationError("sensor model has no points")
                requested: dict[str, dict] = {}
                for point in sensor["points"]:
                    source_id = point.get("source_point_id")
                    if not source_id or source_id in requested:
                        raise ValidationError("sensor points must uniquely reference model points")
                    requested[source_id] = point
                definition_ids = {item.point_id for item in definitions}
                if set(requested) != definition_ids:
                    raise ValidationError("sensor points must exactly match the selected model")
                canonical_points = []
                for definition in definitions:
                    point = requested[definition.point_id]
                    submitted_id = point.get("id")
                    identity = existing_points.get(submitted_id)
                    point_id = (
                        submitted_id
                        if identity == (model_id, definition.point_id)
                        else uuid_generator.random()
                    )
                    canonical_points.append({
                        **point,
                        "id": point_id,
                        "source_point_id": definition.point_id,
                        "name": definition.point_name,
                        "unit": definition.point_unit or "",
                    })
                sensor["points"] = canonical_points
        return SandboxConfig.model_validate(config).model_dump(mode="json")

    @staticmethod
    def catalog_models(db: Session) -> list[dict]:
        models = list(db.scalars(
            select(SensorModel).order_by(
                func.lower(func.coalesce(SensorModel.model_name, "")).asc(),
                SensorModel.model_id.asc(),
            )
        ).all())
        definitions = list(db.scalars(
            select(ModelPoint).join(Point, Point.point_id == ModelPoint.point_id).order_by(
                ModelPoint.model_id.asc(), Point.point_name.asc(),
                ModelPoint.point_id.asc(),
            )
        ).all())
        points_by_model: dict[str, list[dict]] = {}
        for point in definitions:
            points_by_model.setdefault(point.model_id, []).append({
                "point_id": point.point_id,
                "point_name": point.point_name,
                "point_unit": point.point_unit or "",
                "point_description": point.point_description,
            })
        return [{
            "model_id": model.model_id,
            "model_name": model.model_name or "未命名型号",
            "sensor_type": model.sensor_type,
            "remark": model.remark,
            "points": points_by_model.get(model.model_id, []),
        } for model in models]

    @staticmethod
    def catalog_sensors(model_id: str, token: str, db: Session) -> list[dict]:
        if db.get(SensorModel, model_id) is None:
            raise ValidationError("sensor model not found")
        visible = get_viewable_asset_ids(token, db)
        statement = (
            select(Asset, AssetSensor)
            .join(AssetSensor, AssetSensor.asset_id == Asset.asset_id)
            .where(AssetSensor.model_id == model_id)
            .order_by(func.lower(Asset.name).asc(), Asset.asset_id.asc())
        )
        if visible is not None:
            if not visible:
                return []
            statement = statement.where(Asset.asset_id.in_(visible))
        rows = list(db.execute(statement).all())
        path_ids = {
            item
            for asset, _ in rows
            for item in (asset.asset_path or "").split("/")
            if item
        }
        names = dict(db.execute(
            select(Asset.asset_id, Asset.name).where(Asset.asset_id.in_(path_ids))
        ).all()) if path_ids else {}
        return [{
            "sensor_id": asset.asset_id,
            "sensor_name": asset.name,
            "model_id": sensor.model_id,
            "path": " / ".join(
                names.get(item, item)
                for item in (asset.asset_path or "").split("/")
                if item
            ),
        } for asset, sensor in rows]

    @staticmethod
    def baseline(sensor_id: str, db: Session) -> dict:
        sensor = db.get(AssetSensor, sensor_id)
        asset = db.get(Asset, sensor_id)
        if sensor is None or asset is None:
            raise ValidationError("sensor not found")
        point_rows = list(db.scalars(
            select(SensorPoint)
            .where(SensorPoint.sensor_id == sensor_id)
            .order_by(SensorPoint.point_name.asc(), SensorPoint.point_id.asc())
        ).all())
        now = datetime.now(timezone.utc)
        started_at = now - timedelta(hours=1)
        points = []
        for source in point_rows:
            conditions = (
                Measurement.point_id == source.point_id,
                Measurement.time >= started_at,
                Measurement.time < now,
            )
            if db.get_bind().dialect.name == "sqlite":
                values = [float(value) for value in db.scalars(
                    select(Measurement.value).where(*conditions)
                ).all()]
                count = len(values)
                mean = statistics.fmean(values) if values else None
                deviation = statistics.pstdev(values) if len(values) > 1 else 0.0
                minimum = min(values) if values else None
                maximum = max(values) if values else None
            else:
                count, mean, deviation, minimum, maximum = db.execute(
                    select(
                        func.count(Measurement.value),
                        func.avg(Measurement.value),
                        func.stddev_pop(Measurement.value),
                        func.min(Measurement.value),
                        func.max(Measurement.value),
                    ).where(*conditions)
                ).one()
            if not count:
                points.append({
                    "source_point_id": source.point_id,
                    "source_definition_id": source.source_point_id,
                    "id": uuid_generator.random(),
                    "name": source.point_name,
                    "unit": source.point_unit,
                    "base_value": 0.0,
                    "generator": {"noise": 0.1, "min": -1.0, "max": 1.0},
                    "sample_count": 0,
                    "available": False,
                })
                continue
            points.append({
                "source_point_id": source.point_id,
                "source_definition_id": source.source_point_id,
                "id": uuid_generator.random(),
                "name": source.point_name,
                "unit": source.point_unit,
                "base_value": float(mean),
                "generator": {
                    "noise": float(deviation or 0.0),
                    "min": float(minimum),
                    "max": float(maximum),
                },
                "sample_count": int(count),
                "available": True,
            })
        return {
            "sensor_id": sensor_id,
            "sensor_name": asset.name,
            "model_id": sensor.model_id,
            "start_time": started_at,
            "end_time": now,
            "points": points,
        }


sandbox_service = SandboxService()
