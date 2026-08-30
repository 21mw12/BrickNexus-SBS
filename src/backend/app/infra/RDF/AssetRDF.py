"""SQL 资产主数据的 RDF 语义投影和单进程运行时。"""

from __future__ import annotations

import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.EnvLoader import get_env_settings
from app.core.middleware.LogRecorder import get_logger
from app.domain.asset.repository.models import (
    Asset,
    AssetSensor,
    AssetTerminal,
    ModelPoint,
    Point,
    SensorModel,
    SensorPoint,
)
from app.infra.DB.SQLConnection import sql_manager

logger = get_logger(__name__)

BRICK = Namespace("https://brickschema.org/schema/Brick#")
SB = Namespace("https://seee.sues.edu.cn/ontology#")
EX = Namespace("https://seee.sues.edu.cn/#")


def asset_uri(asset_id: str) -> URIRef:
    return EX[f"asset_{quote(str(asset_id), safe='')}"]


def sensor_point_uri(point_id: str) -> URIRef:
    return EX[f"sensor_point_{quote(str(point_id), safe='')}"]


def point_definition_uri(point_id: str) -> URIRef:
    return EX[f"point_definition_{quote(str(point_id), safe='')}"]


def sensor_model_uri(model_id: str) -> URIRef:
    return EX[f"sensor_model_{quote(str(model_id), safe='')}"]


def model_point_uri(model_id: str, point_id: str) -> URIRef:
    """复合键加入长度，避免下划线等合法 ID 组合产生 URI 碰撞。"""
    model_text = str(model_id)
    return EX[
        f"model_point_{len(model_text)}_{quote(model_text, safe='')}_"
        f"{quote(str(point_id), safe='')}"
    ]


class AssetRDFProjector:
    """在同一 SQL Session 快照中构建完整资产 Graph。"""

    ASSET_CLASSES = {
        "building": BRICK.Building,
        "floor": BRICK.Floor,
        "room": BRICK.Room,
        "terminal": SB.Terminal,
        "sensor": SB.SensorAsset,
    }

    @staticmethod
    def _literal(graph: Graph, subject: URIRef, predicate: URIRef, value) -> None:
        if value is not None:
            graph.add((subject, predicate, Literal(value)))

    def build(self, db: Session) -> Graph:
        graph = Graph()
        graph.bind("brick", BRICK)
        graph.bind("sb", SB)
        graph.bind("ex", EX)

        assets = list(db.scalars(select(Asset).order_by(Asset.asset_path)).all())
        terminals = {
            item.asset_id: item
            for item in db.scalars(select(AssetTerminal)).all()
        }
        sensors = {
            item.asset_id: item
            for item in db.scalars(select(AssetSensor)).all()
        }
        models = {
            item.model_id: item
            for item in db.scalars(select(SensorModel)).all()
        }
        points = list(db.scalars(select(Point).order_by(Point.point_id)).all())
        model_points = list(
            db.scalars(select(ModelPoint).order_by(ModelPoint.model_id, ModelPoint.point_id)).all()
        )
        sensor_points = list(
            db.scalars(select(SensorPoint).order_by(SensorPoint.point_id)).all()
        )

        graph.add((SB.Asset, RDF.type, RDFS.Class))
        graph.add((SB.SensorPoint, RDF.type, RDFS.Class))
        graph.add((SB.PointDefinition, RDF.type, RDFS.Class))
        graph.add((SB.SensorModel, RDF.type, RDFS.Class))
        graph.add((SB.ModelPoint, RDF.type, RDFS.Class))

        for asset in assets:
            uri = asset_uri(asset.asset_id)
            graph.add((uri, RDF.type, self.ASSET_CLASSES.get(asset.asset_type, SB.Asset)))
            graph.add((uri, SB.assetId, Literal(asset.asset_id)))
            graph.add((uri, SB.assetType, Literal(asset.asset_type)))
            graph.add((uri, SB.isEnabled, Literal(bool(asset.is_use), datatype=XSD.boolean)))
            graph.add((uri, RDFS.label, Literal(asset.name)))
            if asset.asset_id_parent:
                parent = asset_uri(asset.asset_id_parent)
                graph.add((uri, SB.parentAsset, parent))
                graph.add((uri, BRICK.isPartOf, parent))

            if asset.asset_type == "terminal":
                terminal = terminals.get(asset.asset_id)
                if terminal is not None:
                    self._literal(graph, uri, SB.terminalNumber, terminal.number)
                    self._literal(graph, uri, SB.terminalModel, terminal.model)
                    self._literal(graph, uri, SB.installationLocation, terminal.location)
            elif asset.asset_type == "sensor":
                sensor = sensors.get(asset.asset_id)
                if sensor is not None and sensor.model_id:
                    graph.add((uri, SB.hasModel, sensor_model_uri(sensor.model_id)))

        for model in models.values():
            uri = sensor_model_uri(model.model_id)
            graph.add((uri, RDF.type, SB.SensorModel))
            graph.add((uri, SB.modelId, Literal(model.model_id)))
            self._literal(graph, uri, RDFS.label, model.model_name)
            self._literal(graph, uri, SB.sensorType, model.sensor_type)
            self._literal(graph, uri, RDFS.comment, model.remark)

        for point in points:
            uri = point_definition_uri(point.point_id)
            graph.add((uri, RDF.type, SB.PointDefinition))
            graph.add((uri, SB.pointDefinitionId, Literal(point.point_id)))
            graph.add((uri, RDFS.label, Literal(point.point_name)))
            graph.add((uri, SB.unit, Literal(point.point_unit)))
            self._literal(graph, uri, RDFS.comment, point.point_description)

        for model_point in model_points:
            model = sensor_model_uri(model_point.model_id)
            definition = point_definition_uri(model_point.point_id)
            uri = model_point_uri(model_point.model_id, model_point.point_id)
            graph.add((uri, RDF.type, SB.ModelPoint))
            graph.add((uri, SB.forSensorModel, model))
            graph.add((uri, SB.pointDefinition, definition))
            graph.add((model, SB.hasModelPoint, uri))
            # 便利关系供只关心型号能力的查询直接使用。
            graph.add((model, SB.hasPointDefinition, definition))

        for point in sensor_points:
            uri = sensor_point_uri(point.point_id)
            sensor = asset_uri(point.sensor_id)
            definition = point_definition_uri(point.source_point_id)
            graph.add((uri, RDF.type, SB.SensorPoint))
            graph.add((uri, SB.pointId, Literal(point.point_id)))
            graph.add((uri, RDFS.label, Literal(point.point_name)))
            graph.add((uri, SB.unit, Literal(point.point_unit)))
            graph.add((uri, SB.belongsToSensor, sensor))
            graph.add((uri, SB.pointDefinition, definition))
            graph.add(
                (
                    uri,
                    SB.instantiatesModelPoint,
                    model_point_uri(point.source_model_id, point.source_point_id),
                )
            )
            graph.add((sensor, SB.hasSensorPoint, uri))

        return graph


@dataclass(frozen=True)
class AssetRDFStatus:
    ready: bool
    dirty: bool
    triple_count: int
    generated_at: datetime | None
    last_error: str | None


class AssetRDFRuntime:
    """持有只读 Graph 快照，并在后台合并、重试资产投影重建。"""

    RETRY_SECONDS = 5.0
    DEBOUNCE_SECONDS = 0.2

    def __init__(self, save_dir: Path | None = None) -> None:
        settings = get_env_settings()
        self.save_dir = Path(save_dir or settings.rdf_dir)
        self.output_path = self.save_dir / "assets.ttl"
        self.projector = AssetRDFProjector()
        self._graph = Graph()
        self._lock = threading.RLock()
        self._dirty_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._dirty = True
        self._requested_revision = 0
        self._ready = False
        self._generated_at: datetime | None = None
        self._last_error: str | None = None
        self._revision = 0
        self._listeners: list = []

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self.save_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.rebuild_now()
        except Exception as exc:
            logger.exception("资产 RDF 首次构建失败 error=%s", exc)
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker,
            name="asset-rdf-sync",
            daemon=True,
        )
        self._thread.start()

    def shutdown(self) -> None:
        thread = self._thread
        self._thread = None
        self._stop_event.set()
        self._dirty_event.set()
        if thread is not None:
            thread.join(timeout=5)

    def request_rebuild(self) -> None:
        with self._lock:
            self._dirty = True
            self._requested_revision += 1
        self._dirty_event.set()

    def rebuild_now(self) -> AssetRDFStatus:
        with self._lock:
            requested_revision = self._requested_revision
        try:
            with sql_manager.get_db("main") as db:
                graph = self.projector.build(db)
            self._write_atomic(graph)
        except Exception as exc:
            with self._lock:
                self._dirty = True
                self._last_error = str(exc)
            raise

        generated_at = datetime.now(timezone.utc)
        with self._lock:
            self._graph = graph
            self._dirty = self._requested_revision != requested_revision
            self._ready = True
            self._generated_at = generated_at
            self._last_error = None
            self._revision += 1
            listeners = tuple(self._listeners)
            if self._dirty:
                self._dirty_event.set()
        for listener in listeners:
            try:
                listener(self._revision)
            except Exception as exc:
                logger.exception("资产 RDF 监听器执行失败 error=%s", exc)
        logger.info("资产 RDF 已重建 triples=%s path=%s", len(graph), self.output_path)
        return self.get_status()

    def get_graph_snapshot(self) -> Graph:
        with self._lock:
            snapshot = Graph()
            for prefix, namespace in self._graph.namespaces():
                snapshot.bind(prefix, namespace)
            for triple in self._graph:
                snapshot.add(triple)
            return snapshot

    def get_status(self) -> AssetRDFStatus:
        with self._lock:
            return AssetRDFStatus(
                ready=self._ready,
                dirty=self._dirty,
                triple_count=len(self._graph),
                generated_at=self._generated_at,
                last_error=self._last_error,
            )

    def subscribe_rebuilt(self, listener) -> None:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def unsubscribe_rebuilt(self, listener) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def describe_sensor_point(self, point_id: str, *, include_disabled: bool = False) -> dict | None:
        """返回规则证据所需的实例测点和从 Sensor 向上的资产路径。"""
        point = sensor_point_uri(point_id)
        with self._lock:
            if not self._ready:
                raise RuntimeError("asset RDF is not ready")
            graph = self._graph
            sensor = graph.value(point, SB.belongsToSensor)
            if sensor is None:
                return None
            path = []
            current = sensor
            while current is not None:
                enabled_value = graph.value(current, SB.isEnabled)
                enabled = str(enabled_value).lower() == "true" if enabled_value is not None else True
                if not include_disabled and not enabled:
                    return None
                path.append(
                    {
                        "asset_id": str(graph.value(current, SB.assetId) or ""),
                        "asset_type": str(graph.value(current, SB.assetType) or ""),
                        "name": str(graph.value(current, RDFS.label) or ""),
                    }
                )
                current = graph.value(current, SB.parentAsset)
            definition = graph.value(point, SB.pointDefinition)
            return {
                "point_id": str(graph.value(point, SB.pointId) or point_id),
                "point_name": str(graph.value(point, RDFS.label) or ""),
                "unit": str(graph.value(point, SB.unit) or ""),
                "sensor_id": path[0]["asset_id"] if path else "",
                "point_definition_id": str(graph.value(definition, SB.pointDefinitionId) or ""),
                "asset_path": path,
            }

    def describe_asset(self, asset_id: str) -> dict | None:
        """返回语义选择器校验所需的稳定资产信息。"""
        subject = asset_uri(asset_id)
        with self._lock:
            if not self._ready:
                raise RuntimeError("asset RDF is not ready")
            graph = self._graph
            stored_id = graph.value(subject, SB.assetId)
            if stored_id is None:
                return None
            enabled_value = graph.value(subject, SB.isEnabled)
            return {
                "asset_id": str(stored_id),
                "asset_type": str(graph.value(subject, SB.assetType) or ""),
                "name": str(graph.value(subject, RDFS.label) or ""),
                "is_enabled": (
                    str(enabled_value).lower() == "true"
                    if enabled_value is not None else True
                ),
            }

    def point_definition_exists(self, point_definition_id: str) -> bool:
        """按全局 Point ID 精确确认定义是否存在。"""
        subject = point_definition_uri(point_definition_id)
        with self._lock:
            if not self._ready:
                raise RuntimeError("asset RDF is not ready")
            return self._graph.value(subject, SB.pointDefinitionId) is not None

    def resolve_sensor_point_ids(
        self,
        location_id: str,
        point_definition_id: str,
        *,
        include_descendants: bool = True,
        include_disabled: bool = False,
    ) -> list[str]:
        location = asset_uri(location_id)
        definition = point_definition_uri(point_definition_id)
        path = "sb:parentAsset*" if include_descendants else "sb:parentAsset?"
        enabled_filter = "" if include_disabled else """
                FILTER NOT EXISTS {
                    ?sensor sb:parentAsset* ?disabledAsset .
                    ?disabledAsset sb:isEnabled false .
                }
            """
        query = f"""
            PREFIX sb: <{SB}>
            SELECT DISTINCT ?pointId
            WHERE {{
                ?point sb:pointDefinition <{definition}> ;
                       sb:belongsToSensor ?sensor ;
                       sb:pointId ?pointId .
                ?sensor {path} <{location}> .
                {enabled_filter}
            }}
            ORDER BY ?pointId
        """
        with self._lock:
            if not self._ready:
                raise RuntimeError("asset RDF is not ready")
            return [str(row.pointId) for row in self._graph.query(query)]

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            self._dirty_event.wait(timeout=self.RETRY_SECONDS)
            self._dirty_event.clear()
            if self._stop_event.is_set():
                return
            with self._lock:
                dirty = self._dirty
            if not dirty:
                continue
            if self._stop_event.wait(self.DEBOUNCE_SECONDS):
                return
            try:
                self.rebuild_now()
            except Exception as exc:
                logger.exception("资产 RDF 后台重建失败，将自动重试 error=%s", exc)

    def _write_atomic(self, graph: Graph) -> None:
        self.save_dir.mkdir(parents=True, exist_ok=True)
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.save_dir,
                prefix=".assets-",
                suffix=".ttl",
                delete=False,
            ) as temp_file:
                temp_path = temp_file.name
            graph.serialize(destination=temp_path, format="turtle")
            os.replace(temp_path, self.output_path)
            temp_path = None
        finally:
            if temp_path is not None:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass


asset_rdf_runtime = AssetRDFRuntime()
