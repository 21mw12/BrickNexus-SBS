import numpy as np

from app.common.validators import ValidationError
from app.core.algorithm.result import risk_0_100


class IsolationForestDetector:
    def run(self, values: np.ndarray, parameters: dict) -> dict:
        try:
            from sklearn.ensemble import IsolationForest
        except ModuleNotFoundError as exc:
            raise ValidationError("后端运行环境缺少 scikit-learn，无法执行孤立森林") from exc

        contamination = parameters.get("contamination", "auto")
        if contamination != "auto":
            contamination = float(contamination)
            if not 0.001 <= contamination <= 0.5:
                raise ValidationError("contamination must be auto or between 0.001 and 0.5")
        estimators = int(parameters.get("n_estimators", 100))
        if not 50 <= estimators <= 500:
            raise ValidationError("n_estimators must be between 50 and 500")
        model = IsolationForest(contamination=contamination, n_estimators=estimators, random_state=42)
        matrix = np.asarray(values, dtype=float)
        if matrix.ndim != 2 or not matrix.size or not np.isfinite(matrix).all():
            raise ValidationError("孤立森林输入中存在缺失值或非有限数值")
        raw = -model.fit(matrix).score_samples(matrix)
        labels = model.predict(matrix) == -1
        return {
            "raw_scores": [round(float(value), 6) for value in raw],
            "risk_scores": risk_0_100(raw),
            "labels": labels.tolist(),
            "threshold": round(float(-model.offset_), 6),
        }
