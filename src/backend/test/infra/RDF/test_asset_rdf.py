"""SQL 资产语义投影与快照运行时测试。"""

from contextlib import nullcontext

import pytest
from rdflib import Graph, Literal
from rdflib.namespace import RDF, RDFS
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.asset.repository.models import (
    Asset,
    AssetSensor,
    AssetTerminal,
    ModelPoint,
    Point,
    SensorModel,
    SensorPoint,
)
from app.infra.DB.SQLConnection import Base, sql_manager
from app.infra.RDF.AssetRDF import (
    BRICK,
    SB,
    AssetRDFProjector,
    AssetRDFRuntime,
    asset_uri,
    model_point_uri,
    point_definition_uri,
    sensor_model_uri,
    sensor_point_uri,
)


def _asset(asset_id, parent_id, asset_type, name, *, enabled=True):
    parent_path = f"/{parent_id}" if parent_id else ""
    return Asset(
        asset_id=asset_id,
        asset_id_parent=parent_id,
        asset_path=f"{parent_path}/{asset_id}",
        asset_type=asset_type,
        name=name,
        is_use=enabled,
    )


@pytest.fixture
def projected_graph():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    tables = [
        Asset.__table__,
        AssetTerminal.__table__,
        AssetSensor.__table__,
        SensorModel.__table__,
        Point.__table__,
        ModelPoint.__table__,
        SensorPoint.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as db:
        db.add_all(
            [
                _asset("building-1", None, "building", "总部 & 研发楼"),
                _asset("floor-3", "building-1", "floor", "三层"),
                _asset("room-301", "floor-3", "room", "301 <实验室>"),
                _asset("terminal-1", "room-301", "terminal", "采集终端"),
                _asset("sensor-1", "terminal-1", "sensor", "温度传感器"),
                _asset("room-disabled", "floor-3", "room", "停用房间", enabled=False),
                _asset("terminal-2", "room-disabled", "terminal", "停用分支终端"),
                _asset("sensor-2", "terminal-2", "sensor", "停用分支传感器"),
                AssetTerminal(asset_id="terminal-1", number="T-1", model="edge", location="301"),
                AssetTerminal(asset_id="terminal-2", number="T-2", model="edge", location="停用房间"),
                AssetSensor(asset_id="sensor-1", model_id="model-temp"),
                AssetSensor(asset_id="sensor-2", model_id="model-temp"),
                SensorModel(
                    model_id="model-temp",
                    sensor_type="temperature",
                    model_name="温度型号",
                    remark="测试型号",
                ),
                Point(
                    point_id="global-temp-c",
                    point_name="温度",
                    point_unit="℃",
                    point_description="摄氏温度",
                ),
                ModelPoint(model_id="model-temp", point_id="global-temp-c"),
                SensorPoint(
                    point_id="instance-temp-1",
                    sensor_id="sensor-1",
                    source_model_id="model-temp",
                    source_point_id="global-temp-c",
                    point_name="温度",
                    point_unit="℃",
                    json_path="$.secret.path",
                ),
                SensorPoint(
                    point_id="instance-temp-2",
                    sensor_id="sensor-2",
                    source_model_id="model-temp",
                    source_point_id="global-temp-c",
                    point_name="温度",
                    point_unit="℃",
                    json_path="$.other.path",
                ),
            ]
        )
        db.commit()
        graph = AssetRDFProjector().build(db)
    engine.dispose()
    return graph


def test_projects_hierarchy_and_point_mapping(projected_graph) -> None:
    graph = projected_graph
    assert (asset_uri("building-1"), RDF.type, BRICK.Building) in graph
    assert (asset_uri("floor-3"), SB.parentAsset, asset_uri("building-1")) in graph
    assert (asset_uri("room-301"), SB.parentAsset, asset_uri("floor-3")) in graph
    assert (asset_uri("terminal-1"), SB.parentAsset, asset_uri("room-301")) in graph
    assert (asset_uri("sensor-1"), SB.parentAsset, asset_uri("terminal-1")) in graph

    model_point = model_point_uri("model-temp", "global-temp-c")
    assert (sensor_model_uri("model-temp"), SB.hasModelPoint, model_point) in graph
    assert (model_point, SB.pointDefinition, point_definition_uri("global-temp-c")) in graph
    assert (sensor_point_uri("instance-temp-1"), SB.instantiatesModelPoint, model_point) in graph
    assert (
        sensor_point_uri("instance-temp-1"),
        SB.pointDefinition,
        point_definition_uri("global-temp-c"),
    ) in graph


def test_semantic_query_uses_exact_global_point_and_filters_disabled_ancestors(
    projected_graph, tmp_path
) -> None:
    runtime = AssetRDFRuntime(tmp_path)
    runtime._graph = projected_graph
    runtime._ready = True

    assert runtime.resolve_sensor_point_ids("floor-3", "global-temp-c") == [
        "instance-temp-1"
    ]
    assert runtime.resolve_sensor_point_ids(
        "building-1", "global-temp-c", include_disabled=True
    ) == ["instance-temp-1", "instance-temp-2"]
    assert runtime.resolve_sensor_point_ids("floor-3", "温度") == []
    assert runtime.describe_asset("floor-3") == {
        "asset_id": "floor-3",
        "asset_type": "floor",
        "name": "三层",
        "is_enabled": True,
    }
    assert runtime.describe_asset("missing") is None
    assert runtime.point_definition_exists("global-temp-c") is True
    assert runtime.point_definition_exists("温度") is False


def test_projection_keeps_labels_but_omits_dynamic_and_sensitive_fields(projected_graph) -> None:
    graph = projected_graph
    assert (asset_uri("building-1"), RDFS.label, Literal("总部 & 研发楼")) in graph
    assert (asset_uri("room-301"), RDFS.label, Literal("301 <实验室>")) in graph
    turtle = projected_graph.serialize(format="turtle")
    assert "$.secret.path" not in turtle
    assert "last_receive_time" not in turtle
    assert "isOnline" not in turtle


def test_empty_database_still_builds_valid_graph() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    tables = [
        Asset.__table__,
        AssetTerminal.__table__,
        AssetSensor.__table__,
        SensorModel.__table__,
        Point.__table__,
        ModelPoint.__table__,
        SensorPoint.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as db:
        graph = AssetRDFProjector().build(db)
    assert len(graph) > 0
    assert (SB.SensorPoint, RDF.type, RDFS.Class) in graph


def test_runtime_atomically_writes_ttl_and_returns_detached_snapshot(
    monkeypatch, tmp_path, projected_graph
) -> None:
    runtime = AssetRDFRuntime(tmp_path)
    monkeypatch.setattr(sql_manager, "get_db", lambda _key: nullcontext(object()))
    monkeypatch.setattr(runtime.projector, "build", lambda _db: projected_graph)

    status = runtime.rebuild_now()

    assert status.ready is True
    assert status.dirty is False
    parsed = Graph().parse(runtime.output_path, format="turtle")
    assert len(parsed) == len(projected_graph)
    snapshot = runtime.get_graph_snapshot()
    snapshot.remove((None, None, None))
    assert runtime.get_status().triple_count == len(projected_graph)


def test_failed_rebuild_preserves_previous_graph_and_can_retry(
    monkeypatch, tmp_path, projected_graph
) -> None:
    runtime = AssetRDFRuntime(tmp_path)
    monkeypatch.setattr(sql_manager, "get_db", lambda _key: nullcontext(object()))
    monkeypatch.setattr(runtime.projector, "build", lambda _db: projected_graph)
    runtime.rebuild_now()
    old_count = runtime.get_status().triple_count

    def fail(_db):
        raise RuntimeError("temporary database failure")

    monkeypatch.setattr(runtime.projector, "build", fail)
    with pytest.raises(RuntimeError, match="temporary database failure"):
        runtime.rebuild_now()
    failed = runtime.get_status()
    assert failed.ready is True
    assert failed.dirty is True
    assert failed.triple_count == old_count
    assert failed.last_error == "temporary database failure"

    monkeypatch.setattr(runtime.projector, "build", lambda _db: projected_graph)
    recovered = runtime.rebuild_now()
    assert recovered.dirty is False
    assert recovered.last_error is None


def test_change_during_rebuild_remains_dirty(monkeypatch, tmp_path, projected_graph) -> None:
    runtime = AssetRDFRuntime(tmp_path)
    monkeypatch.setattr(sql_manager, "get_db", lambda _key: nullcontext(object()))

    def build_and_change(_db):
        runtime.request_rebuild()
        return projected_graph

    monkeypatch.setattr(runtime.projector, "build", build_and_change)
    status = runtime.rebuild_now()
    assert status.ready is True
    assert status.dirty is True
