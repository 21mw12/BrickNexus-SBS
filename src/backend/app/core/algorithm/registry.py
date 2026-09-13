"""Single registry and public metadata for analytics algorithms."""

from dataclasses import asdict, dataclass
from typing import Any

from app.common.validators import ValidationError
from .anomaly import IsolationForestDetector, RobustZScoreDetector
from .clustering import KMeansAnalyzer
from .forecasting import AutoRegressionForecaster, HoltWintersForecaster, LinearTrendForecaster, MovingAverageForecaster


@dataclass(frozen=True)
class AlgorithmSpec:
    analysis_type: str
    name: str
    label: str
    description: str
    factory: type
    modes: tuple[str, ...]
    scaling: str
    minimum_samples: int
    parameters: tuple[dict[str, Any], ...]

    def public(self) -> dict:
        result = asdict(self)
        result.pop("factory")
        result["modes"] = list(self.modes)
        result["parameters"] = list(self.parameters)
        return result


PARAMETER_LABELS = {
    "threshold": "异常阈值", "baseline": "基线类型", "window_size": "窗口大小",
    "direction": "异常方向", "contamination": "预计异常比例", "n_estimators": "决策树数量",
    "cluster_count": "聚类数量", "max_iter": "最大迭代次数", "horizon": "预测步数",
    "backtest_ratio": "回测比例", "prediction_interval": "预测区间", "training_window": "训练窗口",
    "trend": "趋势类型", "seasonal": "季节类型", "seasonal_periods": "季节周期", "lags": "滞后阶数",
}
PARAMETER_DESCRIPTIONS = {
    "threshold": "超过该稳健分数的数据会被标记为异常。数值越大，判定越严格、异常越少。",
    "baseline": "选择用全部数据建立统一基线，或用当前点之前的一段滚动窗口建立局部基线。",
    "window_size": "滚动基线或移动平均使用的历史时间桶数量。窗口越大结果越平滑。",
    "direction": "控制检测偏高、偏低，或同时检测两个方向的异常。",
    "contamination": "预计异常数据占比。选择自动时由模型自行确定，也可输入0.001～0.5。",
    "n_estimators": "孤立森林中决策树的数量。数量越多通常越稳定，但计算时间也会增加。",
    "cluster_count": "希望识别的运行状态数量。选择自动时会比较多种数量并选取轮廓系数最高者。",
    "max_iter": "K-Means寻找聚类中心时允许的最大迭代次数。",
    "horizon": "需要向未来预测的时间桶数量。每一步的时长由查询范围和时间桶数量决定。",
    "backtest_ratio": "从历史数据尾部留作回测的比例，用于计算预测误差和预测区间。",
    "prediction_interval": "预测区间的覆盖水平，例如0.95表示95%预测区间。",
    "training_window": "线性趋势拟合使用的最近历史桶数；自动表示使用全部有效数据。",
    "trend": "是否建模随时间持续上升或下降的加法趋势。",
    "seasonal": "是否建模重复出现的加法季节波动。启用后需要设置季节周期。",
    "seasonal_periods": "一个完整季节包含的时间桶数量，例如小时数据的日周期可设为24。",
    "lags": "自回归模型参考的历史滞后桶数。数值越大可利用更长历史，但需要更多样本。",
}
OPTION_LABELS = {
    "global": "全局基线", "rolling": "滚动基线", "both": "双向异常", "high": "仅检测偏高",
    "low": "仅检测偏低", "none": "不启用", "additive": "加法模式",
}


def _parameter(name, kind, default, **extra):
    options = extra.get("options", [])
    return {
        "name": name,
        "label": PARAMETER_LABELS[name],
        "description": PARAMETER_DESCRIPTIONS[name],
        "type": kind,
        "default": default,
        "option_labels": {value: OPTION_LABELS.get(value, value) for value in options},
        **extra,
    }


class AlgorithmRegistry:
    def __init__(self) -> None:
        forecast_common = (
            _parameter("horizon", "integer", 20, minimum=1, maximum=500),
            _parameter("backtest_ratio", "number", 0.2, minimum=0.1, maximum=0.4),
            _parameter("prediction_interval", "number", 0.95, minimum=0.8, maximum=0.99),
        )
        specs = [
            AlgorithmSpec("anomaly", "robust_zscore", "稳健 Z-Score", "使用中位数和MAD识别明显偏离正常水平的数据，速度快且容易解释。", RobustZScoreDetector, ("per_point",), "none", 20, (
                _parameter("threshold", "number", 3.5, minimum=1, maximum=10),
                _parameter("baseline", "select", "global", options=["global", "rolling"]),
                _parameter("window_size", "integer", 20, minimum=10, maximum=500, visible_when={"baseline": "rolling"}),
                _parameter("direction", "select", "both", options=["both", "high", "low"]),
            )),
            AlgorithmSpec("anomaly", "isolation_forest", "孤立森林", "通过随机树识别容易被单独隔离的数据，适合一般非线性异常和多测点联合状态。", IsolationForestDetector, ("per_point", "joint"), "robust", 20, (
                _parameter("contamination", "text", "auto"),
                _parameter("n_estimators", "integer", 100, minimum=50, maximum=500),
            )),
            AlgorithmSpec("clustering", "kmeans", "K-Means 聚类", "按照多个测点在同一时间桶的组合特征，将运行状态划分为若干组。", KMeansAnalyzer, ("joint",), "standard", 20, (
                _parameter("cluster_count", "text", "auto"),
                _parameter("max_iter", "integer", 300, minimum=100, maximum=1000),
            )),
            AlgorithmSpec("forecasting", "moving_average", "移动平均", "以最近一段数据的平均值作为未来预测，适合稳定、变化缓慢的数据。", MovingAverageForecaster, ("per_point",), "none", 20, forecast_common + (
                _parameter("window_size", "integer", 5, minimum=2, maximum=500),
            )),
            AlgorithmSpec("forecasting", "linear_trend", "线性趋势", "拟合近期数据的线性变化方向并向未来延伸，适合具有近似直线趋势的数据。", LinearTrendForecaster, ("per_point",), "none", 20, forecast_common + (
                _parameter("training_window", "text", "auto"),
            )),
            AlgorithmSpec("forecasting", "holt_winters", "Holt-Winters 指数平滑", "同时描述当前水平、趋势和可选季节周期，适合平滑且具有周期性的序列。", HoltWintersForecaster, ("per_point",), "none", 20, forecast_common + (
                _parameter("trend", "select", "additive", options=["none", "additive"]),
                _parameter("seasonal", "select", "none", options=["none", "additive"]),
                _parameter("seasonal_periods", "integer", 24, minimum=2, maximum=500, visible_when={"seasonal": "additive"}),
            )),
            AlgorithmSpec("forecasting", "autoregression", "自回归", "利用前若干个时间桶的值预测未来，适合具有明显时间依赖的数据。", AutoRegressionForecaster, ("per_point",), "none", 20, forecast_common + (
                _parameter("lags", "integer", 5, minimum=1, maximum=100),
            )),
        ]
        self._specs = {(item.analysis_type, item.name): item for item in specs}

    def resolve(self, analysis_type: str, name: str) -> AlgorithmSpec:
        spec = self._specs.get((analysis_type, name))
        if spec is None:
            raise ValidationError("unsupported analytics algorithm")
        return spec

    def catalog(self) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {"anomaly": [], "clustering": [], "forecasting": []}
        for spec in self._specs.values():
            result[spec.analysis_type].append(spec.public())
        return result


algorithm_registry = AlgorithmRegistry()
