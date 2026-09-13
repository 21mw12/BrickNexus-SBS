# 历史数据 API

## 一、说明

最多同时查询 10 个测点。需要 `data` 或 `data:history` 页面权限，并对每个测点所属 Sensor 具有 R 权限；任一测点无效或越权时整批失败。时间按 `time.default_timezone` 解释和返回。

除文件流和 WebSocket 外，接口使用统一 JSON 包装：

```json
{
  "success": true,
  "code": 200,
  "message": "请求成功",
  "data": {}
}
```

接口地址均包含应用统一前缀 `/api`。需要登录的 HTTP 接口使用
`Authorization: Bearer <JWT令牌>`；JSON 请求使用
`Content-Type: application/json`。各接口另有说明时，以接口说明为准。

## 二、API

### 多测点历史数据查询

- 请求地址：`POST /api/history/query`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 权限：需要 `data` 或 `data:history` 页面权限，并且对所有测点所属 Sensor 都具有 R 权限。任一测点无效或无权限时整批失败；权限错误不会返回具体测点 ID。

- 请求体：

  ```json
  {
      "point_ids": ["point-001", "point-002"],
      "start_time": "2026-08-01 00:00:00",
      "end_time": "2026-08-20 00:00:00",
      "sample_count": 500
  }
  ```

  | 参数         | 类型      | 必传 | 说明                                                   |
  | ------------ | --------- | ---- | ------------------------------------------------------ |
  | point_ids    | list[str] | 是   | 列表长度 1～10；重复 ID 去重并保持首次出现顺序         |
  | start_time   | str       | 是   | `yyyy-MM-dd HH:mm:ss`；分钟必须为 00/15/30/45，秒为 00 |
  | end_time     | str       | 是   | `yyyy-MM-dd HH:mm:ss`，无需按 15 分钟对齐              |
  | sample_count | int       | 是   | 每个测点的目标采样数量，范围 100～1000                 |

- 时间统一按配置项 `time.default_timezone` 解释和返回，当前为 `Asia/Shanghai`。请求时间范围为 15 分钟至 31 天，查询区间为 `[start_time, actual_end_time)`。终止时间超过当前时间时会截断到当前时间；截断后即使实际范围不足 15 分钟也正常查询。

- 每个测点独立下采样。原始数量不超过 `sample_count` 时返回全部数据；超过时使用 LTTB 返回恰好 `sample_count` 个点，并保留首尾数据。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "timezone": "Asia/Shanghai",
          "start_time": "2026-08-01 00:00:00",
          "requested_end_time": "2026-08-20 00:00:00",
          "actual_end_time": "2026-08-13 15:30:25",
          "sample_count": 500,
          "points": [
              {
                  "point_id": "point-001",
                  "original_count": 2860,
                  "returned_count": 500,
                  "downsampled": true,
                  "times": ["2026-08-01 00:00:00", "2026-08-01 00:15:00"],
                  "values": [23.5, 24.1],
                  "normalized_values": [0.0, 100.0]
              },
              {
                  "point_id": "point-002",
                  "original_count": 0,
                  "returned_count": 0,
                  "downsampled": false,
                  "times": [],
                  "values": [],
                  "normalized_values": []
              }
          ]
      }
  }
  ```

`normalized_values` 按每个测点自身的返回值范围映射到0～100；缺失值保持
`null`，常量序列的有效值为50。

### 历史热力图与相关性

- 请求地址：`POST /api/history/heatmap`
- 请求头：

  | 请求头 | 值格式 | 必传 | 说明 |
  |---|---|---|---|
  | Authorization | Bearer {JWT令牌} | 是 | 当前登录用户令牌 |
  | Content-Type | application/json | 是 | JSON 请求体 |

- 请求体：与 `/api/history/query` 相同。`point_ids` 为1～10项，
  `sample_count` 为100～1000。

  ```json
  {
    "point_ids": ["point-1", "point-2"],
    "start_time": "2026-09-01 00:00:00",
    "end_time": "2026-09-02 00:00:00",
    "sample_count": 500
  }
  ```

服务端将实际查询范围平均划分为时间桶，每个桶使用算术平均值聚合；没有数据的桶保留为
`null`。所有测点都无数据的全局空桶也会保留，热力图以灰色格子表示缺失。折线图默认
根据每个测点的典型采样节奏判断：短于约3倍正常采样间隔的空桶跨越连接，明显过长的
空档断线；用户也可切换为“空桶即断开”或“始终连接”。相关性按测点对剔除任一方为 `null`
的时间桶；有效配对少于3个或任一序列方差为0时，系数返回 `null`。

- 返回格式：

  ```json
  {
    "success": true,
    "code": 200,
    "message": "请求成功",
    "data": {
      "timezone": "Asia/Shanghai",
      "start_time": "2026-09-01 00:00:00",
      "requested_end_time": "2026-09-02 00:00:00",
      "actual_end_time": "2026-09-02 00:00:00",
      "sample_count": 480,
      "requested_sample_count": 500,
      "interval_seconds": 172.8,
      "times": ["2026-09-01 00:00:00"],
      "value_range": {"min": 10.0, "max": 50.0},
      "points": [{
        "point_id": "point-1",
        "original_count": 1200,
        "non_null_count": 498,
        "values": [23.1, null],
        "normalized_values": [42.3, null]
      }],
      "correlations": {
        "pearson": [[1.0, 0.82], [0.82, 1.0]],
        "spearman": [[1.0, 0.79], [0.79, 1.0]],
        "pair_counts": [[498, 476], [476, 490]]
      }
    }
  }
  ```

数组和矩阵顺序与请求中的 `point_ids` 一致。`normalized_values` 按测点自身范围映射到
0～100；缺失值保持 `null`，常量序列的有效值为50。

### 查询全量原始历史数据

- 请求地址：`POST /api/history/raw`
- 请求头：

  | 请求头 | 值格式 | 必传 | 说明 |
  |---|---|---|---|
  | Authorization | Bearer {JWT令牌} | 是 | 当前登录用户令牌 |
  | Content-Type | application/json | 是 | JSON 请求体 |

- 请求体：不包含 `sample_count`；时间范围最大31天，结束时间超过当前时间时自动裁剪。

  ```json
  {
    "point_ids": ["point-id"],
    "start_time": "2026-09-01 00:00:00",
    "end_time": "2026-09-01 01:00:00"
  }
  ```

- 返回格式：返回全部原始点，不执行下采样。

  ```json
  {
    "success": true,
    "code": 200,
    "message": "请求成功",
    "data": {
      "points": [{
        "point_id": "point-id",
        "count": 120,
        "times": ["2026-09-01 00:00:00"],
        "values": [23.5]
      }]
    }
  }
  ```
