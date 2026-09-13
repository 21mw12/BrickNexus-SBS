import numpy as np

from app.common.validators import ValidationError


class KMeansAnalyzer:
    def run(self, values: np.ndarray, parameters: dict) -> dict:
        try:
            from sklearn.cluster import KMeans
            from sklearn.decomposition import PCA
            from sklearn.metrics import silhouette_score
        except ModuleNotFoundError as exc:
            raise ValidationError("后端运行环境缺少 scikit-learn，无法执行 K-Means 聚类") from exc

        matrix = np.asarray(values, dtype=float)
        if matrix.ndim != 2 or not matrix.size or not np.isfinite(matrix).all():
            raise ValidationError("K-Means 输入中存在缺失值或非有限数值")
        if matrix.shape[0] < 20 or matrix.shape[1] < 2:
            raise ValidationError("K-Means requires at least 20 samples and 2 usable points")
        max_iter = int(parameters.get("max_iter", 300))
        if not 100 <= max_iter <= 1000:
            raise ValidationError("max_iter must be between 100 and 1000")
        requested = parameters.get("cluster_count", "auto")
        distinct_count = len(np.unique(matrix, axis=0))
        if distinct_count < 2:
            raise ValidationError("K-Means requires at least two distinct samples")
        candidates = range(2, min(8, len(matrix) - 1, distinct_count) + 1) if requested == "auto" else [int(requested)]
        scores: list[dict] = []
        best = None
        for clusters in candidates:
            if not 2 <= clusters <= 10 or clusters >= len(matrix):
                raise ValidationError("cluster_count must be between 2 and 10 and smaller than sample count")
            if clusters > distinct_count:
                raise ValidationError("聚类数量不能超过有效样本状态数量")
            model = KMeans(n_clusters=clusters, max_iter=max_iter, n_init=10, random_state=42).fit(matrix)
            if len(np.unique(model.labels_)) < 2:
                if requested == "auto":
                    continue
                raise ValidationError("数据无法形成两个以上的有效聚类")
            score = float(silhouette_score(matrix, model.labels_))
            scores.append({"cluster_count": clusters, "silhouette_score": round(score, 6), "inertia": round(float(model.inertia_), 6)})
            if best is None or score > best[0]:
                best = (score, model)
        if best is None:
            raise ValidationError("数据特征过于相似，无法形成有效聚类")
        model = best[1]
        pca = PCA(n_components=2, random_state=42).fit(matrix)
        coordinates = pca.transform(matrix)
        return {
            "cluster_count": int(model.n_clusters),
            "labels": [int(value) for value in model.labels_],
            "centers": model.cluster_centers_.tolist(),
            "silhouette_score": round(float(best[0]), 6),
            "inertia": round(float(model.inertia_), 6),
            "candidate_scores": scores,
            "pca": {
                "coordinates": coordinates.tolist(),
                "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
                "total_explained_variance": round(float(np.sum(pca.explained_variance_ratio_)), 6),
            },
        }
