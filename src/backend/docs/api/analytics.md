# 智能分析 API

## 一、说明

智能分析对真实测点历史数据执行一次性异常检测、聚类和趋势预测，不保存模型或结果，
也不会修改原始测量数据。接口需要 `data` 或 `data:analysis` 页面权限，并要求当前用户
对所有测点所属 Sensor 具有 R 权限；任一测点无效或越权时整批失败。

时间按 `time.default_timezone` 解释和返回，查询区间为
`[start_time, actual_end_time)`。开始时间须对齐至00、15、30、45分，查询范围为15分钟至31天；
结束时间超过当前时间时自动裁剪。`sample_count` 为100～1000个固定等宽时间桶，算法不使用
LTTB。桶内支持 `mean、min、max、first、last` 聚合，无数据的桶保留为空。

分析成功后还会尽力创建一份供[智能分析 AI 解读](agent-analysis.md)使用的Redis短期摘要。
该增强能力不可用时不会影响本接口的数值结果。

## 二、算法目录

- 请求地址：`GET /api/analytics/algorithms`
- 请求头：`Authorization: Bearer {JWT令牌}`
- 返回：按 `anomaly、clustering、forecasting` 分组的算法数组。每项包含名称、显示名、
  支持模式、标准化方式、最低样本数以及参数默认值、范围和显示条件。

## 三、执行分析

- 请求地址：`POST /api/analytics/run`
- 请求头：`Authorization: Bearer {JWT令牌}`、`Content-Type: application/json`

请求示例：

```json
{
  "analysis_type": "anomaly",
  "point_ids": ["point-1", "point-2"],
  "start_time": "2026-09-01 00:00:00",
  "end_time": "2026-09-02 00:00:00",
  "sample_count": 500,
  "preprocessing": {
    "aggregation": "mean",
    "missing_strategy": "interpolate",
    "max_gap": 3
  },
  "algorithm": {
    "name": "isolation_forest",
    "mode": "joint",
    "parameters": {"contamination": "auto", "n_estimators": 100}
  }
}
```

缺失处理支持 `drop、interpolate、forward_fill、reject`；插值和前向填充最多跨越
`max_gap` 个连续时间桶。标准化由算法决定：Isolation Forest 使用 Robust Scaling，
K-Means 使用 Standard Scaling，其余算法保持原量纲。

算法可使用填补后的值参与计算，但返回给折线图的历史值始终取固定时间桶中的原始聚合
值。没有原始数据的桶返回 `null`。前端根据测点的典型采样节奏连接正常采集间隔，只在
数据空档明显超过正常节奏时断线；算法使用的填补值不会替代图表中的原始聚合值。

### 算法与参数

| 类型 | 算法 | 模式与主要参数 |
|---|---|---|
| 异常检测 | `robust_zscore` | `per_point`；threshold 1～10、baseline global/rolling、window_size 10～500、direction both/high/low |
| 异常检测 | `isolation_forest` | `per_point/joint`；contamination auto或0.001～0.5、n_estimators 50～500 |
| 聚类 | `kmeans` | `joint`且至少2个有效测点；cluster_count auto或2～10、max_iter 100～1000 |
| 预测 | `moving_average` | window_size 2～500 |
| 预测 | `linear_trend` | training_window auto或有效窗口数 |
| 预测 | `holt_winters` | trend/seasonal 为none或additive，seasonal_periods 2～500 |
| 预测 | `autoregression` | lags 1～100 |

预测算法还支持 `horizon` 1～500、`backtest_ratio` 0.1～0.4、
`prediction_interval` 0.8～0.99。多测点预测逐点独立执行，部分失败时其余结果仍返回；
全部失败时返回400。

统一响应示例：

```json
{
  "success": true,
  "code": 200,
  "message": "请求成功",
  "data": {
    "analysis_type": "anomaly",
    "algorithm": "isolation_forest",
    "mode": "joint",
    "timezone": "Asia/Shanghai",
    "range": {
      "start_time": "2026-09-01 00:00:00",
      "requested_end_time": "2026-09-02 00:00:00",
      "actual_end_time": "2026-09-02 00:00:00",
      "was_clipped": false
    },
    "sampling": {
      "requested_sample_count": 500,
      "actual_sample_count": 500,
      "interval_seconds": 172.8,
      "aggregation": "mean"
    },
    "preprocessing": {"missing_strategy": "interpolate", "max_gap": 3, "scaling": "robust"},
    "quality": {"raw_count": 2000, "bucket_count": 500, "missing_ratio": 0.02},
    "warnings": [],
    "ai_context": {
      "available": true,
      "analysis_id": "57a6d796-3268-4ef6-9d5f-78e87d517edf",
      "expires_at": "2026-09-13T08:30:00+00:00",
      "reason_code": null
    },
    "result": {}
  }
}
```

异常结果包含时间、原始聚合值、原始异常分数、0～100风险分、标签和连续异常事件。
聚类结果包含状态标签、原量纲中心、状态数量、轮廓系数、Inertia及PCA二维坐标。
预测结果包含历史、回测、未来预测、预测上下界以及MAE、RMSE、sMAPE。

`warnings` 使用稳定的 `code`，包括 `HIGH_MISSING_RATIO`、
`INSUFFICIENT_POINT_SAMPLES`、`CONSTANT_POINTS_EXCLUDED`、
`LOW_SILHOUETTE_SCORE` 和 `POINT_FORECAST_FAILED`。

`ai_context` 不属于算法结果。Redis摘要创建成功时可使用 `analysis_id` 请求AI解读；失败时
`available=false`、`analysis_id=null`，并返回稳定原因码 `AI_CONTEXT_UNAVAILABLE`。

参数或数据不可分析返回400，未登录返回401，页面或测点权限不足返回403，未处理异常返回500。
