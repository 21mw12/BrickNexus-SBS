import asyncio
import importlib
import json

import pytest

from app.core.algorithm import algorithm_registry
from app.domain.agent.analysis.context import AnalysisContextBuilder
from app.domain.agent.analysis.prompts import ALGORITHM_PROMPTS, build_system_prompt
from app.domain.agent.analysis.schema import AnalysisAgentRequest, ReportAgentOutput
from app.domain.agent.analysis.service import AnalysisAgentService
from app.domain.agent.analysis.store import AnalysisContextExpiredError, AnalysisSnapshotStore


def _common(analysis_type, algorithm, result):
    return {
        "analysis_type": analysis_type,
        "algorithm": algorithm,
        "mode": "joint" if analysis_type == "clustering" else "per_point",
        "parameters": {"prediction_interval": 0.95},
        "timezone": "Asia/Shanghai",
        "range": {"start_time": "2026-09-01 00:00:00", "actual_end_time": "2026-09-01 01:00:00"},
        "sampling": {"actual_sample_count": 100, "interval_seconds": 36},
        "preprocessing": {"missing_strategy": "interpolate"},
        "quality": {"raw_count": 80, "missing_ratio": 0.2},
        "warnings": [],
        "result": result,
    }


META = {
    "p1": {"point_name": "温度", "point_unit": "℃"},
    "p2": {"point_name": "湿度", "point_unit": "%"},
}


def test_context_builder_summarizes_all_analysis_types_without_full_arrays():
    builder = AnalysisContextBuilder()
    anomaly = builder.build(_common("anomaly", "robust_zscore", {"series": [{
        "point_ids": ["p1"], "times": ["t1", "t2", "t3"],
        "values_by_point": [[20, 80, None]], "labels": [False, True, False],
        "risk_scores": [0, 100, None], "threshold": 3.5,
        "events": [{"start_time": "t2", "end_time": "t2", "sample_count": 1, "max_score": 100}],
    }]}), ["p1"], META)
    assert anomaly["details"]["series"][0]["anomaly_count"] == 1
    assert "values_by_point" not in json.dumps(anomaly)

    clustering = builder.build(_common("clustering", "kmeans", {
        "point_ids": ["p1", "p2"], "labels": [0, 0, 1], "cluster_sizes": [2, 1],
        "cluster_count": 2, "centers": [[20, 40], [25, 60]], "silhouette_score": 0.5,
        "inertia": 2.5, "feature_summaries": [], "candidate_scores": [],
        "pca": {"coordinates": [[0, 0], [1, 1], [2, 2]]},
    }), ["p1", "p2"], META)
    assert len(clustering["details"]["states"]) == 2
    assert "coordinates" not in json.dumps(clustering)

    forecasting = builder.build(_common("forecasting", "moving_average", {"horizon": 20, "points": [{
        "point_id": "p1", "status": "success", "history_values": list(range(100)),
        "forecast_times": [f"t{i}" for i in range(20)], "forecast_values": list(range(100, 120)),
        "lower": list(range(99, 119)), "upper": list(range(101, 121)),
        "metrics": {"mae": 1, "rmse": 1.2, "smape": 3},
    }]}), ["p1"], META)
    point = forecasting["details"]["points"][0]
    assert len(point["representative_forecast"]) <= 12
    assert "history_values" not in json.dumps(forecasting)


def test_every_registered_algorithm_has_interpretation_guidance():
    registered = {item["name"] for specs in algorithm_registry.catalog().values() for item in specs}
    assert registered == set(ALGORITHM_PROMPTS)
    for specs in algorithm_registry.catalog().values():
        for item in specs:
            assert item["label"] in build_system_prompt(item["analysis_type"], item["name"]) or ALGORITHM_PROMPTS[item["name"]]


class FakeRedis:
    def __init__(self): self.values, self.expired = {}, []
    def set(self, key, value, ex=None): self.values[key] = value; return True
    def get(self, key): return self.values.get(key)
    def expire(self, key, seconds): self.expired.append((key, seconds)); return True


def test_snapshot_is_user_isolated_sliding_and_expires(monkeypatch):
    module = importlib.import_module("app.domain.agent.analysis.store")
    backend = FakeRedis()
    monkeypatch.setattr(module, "redis_manager", backend)
    store = AnalysisSnapshotStore()
    created = store.create("u1", {"point_ids": ["p1"]})
    assert store.load("u1", created["analysis_id"])["context"]["point_ids"] == ["p1"]
    assert backend.expired
    with pytest.raises(PermissionError):
        store.load("u2", created["analysis_id"])
    backend.values.clear()
    with pytest.raises(AnalysisContextExpiredError):
        store.load("u1", created["analysis_id"])


def test_agent_rechecks_point_permission_and_returns_structured_report():
    class Store:
        def load(self, user_id, analysis_id):
            assert user_id == "user"
            return {"context": {"point_ids": ["p1"], "analysis_type": "anomaly", "algorithm": {"name": "robust_zscore"}}}

    class Access:
        called = False
        def require_read(self, point_ids, authorization, db):
            self.called = (point_ids, authorization, db) == (["p1"], "token", "db")

    class Model:
        async def respond(self, **kwargs):
            return ReportAgentOutput(report={"overview": "结果概述"})

    access = Access()
    service = AnalysisAgentService(Model(), Store(), lambda _: "user", access)
    result = asyncio.run(service.respond(AnalysisAgentRequest(analysis_id="id"), "token", "db"))
    assert access.called
    assert result["response_type"] == "report"
    assert result["report"]["overview"] == "结果概述"


def test_analytics_api_keeps_numeric_result_when_snapshot_fails(monkeypatch):
    api = importlib.import_module("app.domain.analytics.api.AnalyticsAPI")
    request = type("Request", (), {"point_ids": ["p1"]})()
    monkeypatch.setattr(api.point_data_access_service, "require_read", lambda *_: None)
    monkeypatch.setattr(api.analytics_service, "run", lambda *_: {"analysis_type": "anomaly", "result": {}})
    monkeypatch.setattr(api.SensorPointRepository, "get_metadata_by_point_ids", lambda *_: {})
    monkeypatch.setattr(api, "get_user_id_from_token", lambda _: "user")
    monkeypatch.setattr(api.analysis_snapshot_service, "create", lambda *_: (_ for _ in ()).throw(RuntimeError("redis down")))
    response = api.run_analysis(request, "token", object())
    body = json.loads(response.body)
    assert body["success"] is True
    assert body["data"]["ai_context"]["available"] is False
