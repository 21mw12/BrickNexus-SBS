"""将完整数值分析结果压缩为适合大模型解释的确定性摘要。"""

import json
import math
from statistics import mean, median
from typing import Any

from app.core.algorithm import algorithm_registry
from . import config


def _number(value: Any, digits: int = 6) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return round(result, digits) if math.isfinite(result) else None


def _numbers(values) -> list[float]:
    result = []
    for value in values or []:
        normalized = _number(value)
        if normalized is not None:
            result.append(normalized)
    return result


def _series_summary(values) -> dict[str, Any]:
    valid = _numbers(values)
    if not valid:
        return {"valid_count": 0}
    first, last = valid[0], valid[-1]
    change = last - first
    return {
        "valid_count": len(valid),
        "minimum": min(valid),
        "maximum": max(valid),
        "mean": round(mean(valid), 6),
        "median": round(median(valid), 6),
        "first": first,
        "last": last,
        "change": round(change, 6),
        "change_percent": round(change / abs(first) * 100, 4) if first else None,
    }


def _representative_indexes(length: int, limit: int = config.MAX_REPRESENTATIVE_POINTS) -> list[int]:
    if length <= limit:
        return list(range(length))
    return sorted({round(index * (length - 1) / (limit - 1)) for index in range(limit)})


def _point(meta: dict[str, dict], point_id: str) -> dict[str, str]:
    value = meta.get(point_id, {})
    return {
        "point_id": point_id,
        "point_name": str(value.get("point_name") or point_id),
        "point_unit": str(value.get("point_unit") or ""),
    }


class AnalysisContextBuilder:
    @staticmethod
    def _anomaly(result: dict, metadata: dict) -> dict:
        output, total_events = [], 0
        for series in result.get("series", []):
            labels = list(series.get("labels") or [])
            risks = list(series.get("risk_scores") or [])
            times = list(series.get("times") or [])
            point_ids = list(series.get("point_ids") or [])
            values_by_point = list(series.get("values_by_point") or [])
            assessed = _numbers(risks)
            item = {
                "points": [_point(metadata, point_id) for point_id in point_ids],
                "assessed_count": len(assessed),
                "anomaly_count": sum(bool(value) for value in labels),
                "anomaly_ratio": round(sum(bool(value) for value in labels) / len(assessed), 6) if assessed else 0,
                "highest_risk": max(assessed) if assessed else None,
                "threshold": _number(series.get("threshold")),
                "point_statistics": [
                    {**_point(metadata, point_id), **_series_summary(values_by_point[index] if index < len(values_by_point) else [])}
                    for index, point_id in enumerate(point_ids)
                ],
            }
            candidates = []
            for index, label in enumerate(labels):
                if not label:
                    continue
                candidates.append({
                    "time": times[index] if index < len(times) else None,
                    "risk": _number(risks[index]) if index < len(risks) else None,
                    "values": [
                        {
                            **_point(metadata, point_id),
                            "value": _number(values_by_point[column][index]) if column < len(values_by_point) and index < len(values_by_point[column]) else None,
                        }
                        for column, point_id in enumerate(point_ids)
                    ],
                })
            item["representative_anomalies"] = sorted(candidates, key=lambda row: row.get("risk") or 0, reverse=True)[:10]
            event_limit = min(config.MAX_EVENTS_PER_SERIES, config.MAX_EVENTS_TOTAL - total_events)
            item["events"] = list(series.get("events") or [])[:max(0, event_limit)]
            total_events += len(item["events"])
            output.append(item)
        return {"series": output}

    @staticmethod
    def _clustering(result: dict, metadata: dict) -> dict:
        point_ids = list(result.get("point_ids") or [])
        labels = list(result.get("labels") or [])
        sizes = list(result.get("cluster_sizes") or [])
        centers = []
        for cluster, center in enumerate(result.get("centers") or []):
            size = int(sizes[cluster]) if cluster < len(sizes) else 0
            centers.append({
                "state": cluster + 1,
                "sample_count": size,
                "sample_ratio": round(size / len(labels), 6) if labels else 0,
                "center": [
                    {**_point(metadata, point_id), "value": _number(center[index]) if index < len(center) else None}
                    for index, point_id in enumerate(point_ids)
                ],
                "highlights": next((item.get("highlights", []) for item in result.get("feature_summaries", []) if item.get("cluster") == cluster), []),
            })
        return {
            "cluster_count": result.get("cluster_count"),
            "silhouette_score": _number(result.get("silhouette_score")),
            "inertia": _number(result.get("inertia")),
            "states": centers,
            "candidate_scores": list(result.get("candidate_scores") or [])[:8],
        }

    @staticmethod
    def _forecasting(result: dict, metadata: dict, interval_level: Any) -> dict:
        points = []
        for point in result.get("points", []):
            point_id = str(point.get("point_id", ""))
            base = _point(metadata, point_id)
            if point.get("status") != "success":
                points.append({**base, "status": "failed", "message": str(point.get("message") or "预测失败")[:500]})
                continue
            values = list(point.get("forecast_values") or [])
            times = list(point.get("forecast_times") or [])
            lower, upper = point.get("lower"), point.get("upper")
            samples = []
            for index in _representative_indexes(len(values)):
                samples.append({
                    "time": times[index] if index < len(times) else None,
                    "value": _number(values[index]),
                    "lower": _number(lower[index]) if lower and index < len(lower) else None,
                    "upper": _number(upper[index]) if upper and index < len(upper) else None,
                })
            widths = [float(high) - float(low) for low, high in zip(lower or [], upper or []) if _number(low) is not None and _number(high) is not None]
            points.append({
                **base,
                "status": "success",
                "history": _series_summary(point.get("history_values") or []),
                "forecast": _series_summary(values),
                "metrics": {key: _number(value) for key, value in (point.get("metrics") or {}).items()},
                "forecast_range": {"start_time": times[0] if times else None, "end_time": times[-1] if times else None},
                "prediction_interval": {
                    "level": _number(interval_level),
                    "available": bool(lower and upper),
                    "average_width": round(mean(widths), 6) if widths else None,
                },
                "representative_forecast": samples,
            })
        return {"horizon": result.get("horizon"), "points": points}

    def build(self, analytics_result: dict, point_ids: list[str], metadata: dict[str, dict]) -> dict:
        analysis_type = analytics_result["analysis_type"]
        algorithm = analytics_result["algorithm"]
        spec = algorithm_registry.resolve(analysis_type, algorithm)
        common = {
            "analysis_type": analysis_type,
            "algorithm": {"name": algorithm, "label": spec.label},
            "mode": analytics_result.get("mode"),
            "parameters": analytics_result.get("parameters", {}),
            "timezone": analytics_result.get("timezone"),
            "range": analytics_result.get("range", {}),
            "sampling": analytics_result.get("sampling", {}),
            "preprocessing": analytics_result.get("preprocessing", {}),
            "quality": analytics_result.get("quality", {}),
            "warnings": analytics_result.get("warnings", []),
            "points": [_point(metadata, point_id) for point_id in point_ids],
            "point_ids": point_ids,
        }
        raw_result = analytics_result.get("result", {})
        if analysis_type == "anomaly":
            details = self._anomaly(raw_result, metadata)
        elif analysis_type == "clustering":
            details = self._clustering(raw_result, metadata)
        else:
            details = self._forecasting(raw_result, metadata, analytics_result.get("parameters", {}).get("prediction_interval", 0.95))
        context = {**common, "details": details}
        if len(json.dumps(context, ensure_ascii=False, separators=(",", ":"))) > config.MAX_CONTEXT_CHARS:
            raise ValueError("分析摘要超过AI上下文保护上限")
        return context


analysis_context_builder = AnalysisContextBuilder()
