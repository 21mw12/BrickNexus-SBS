# 数字孪生沙盒 API

## 一、说明

全部接口需要 `sandbox` 页面权限。HTTP 接口使用
`Authorization: Bearer <JWT令牌>`；JSON 请求还需要
`Content-Type: application/json`。沙盒时间从 tick 0 开始，只在运行状态下递增；一个 tick 固定表示30秒虚拟时间。

除文件流和 WebSocket 外，返回使用统一 JSON 包装：

```json
{"success": true, "code": 200, "message": "请求成功", "data": {}}
```

### 配置结构

```json
{
  "speed": 1,
  "terminals": [{
    "name": "虚拟终端",
    "sensors": [{
      "name": "温度传感器",
      "model_id": "sensor-model-id",
      "points": [{
        "id": "virtual-point-id",
        "source_point_id": "model-point-id",
        "name": "温度",
        "unit": "℃",
        "base_value": 24,
        "generator": {"noise": 0.2, "min": 10, "max": 50}
      }]
    }]
  }],
  "sandbox_rule": []
}
```

终端和传感器没有 `state` 或独立采样周期。全部虚拟测点每个 tick 生成一次数据；`speed` 只允许 `1、2、5、10`。

## 二、API

### 沙盒管理

下表接口均使用 `Authorization: Bearer <JWT令牌>`。`sandbox_id`、`sensor_id`
为路径参数；`page` 默认1，`limit` 默认20且范围1～100。

| 方法 | 地址 | 说明 |
|---|---|---|
| GET | `/api/sandbox/list?page=1&limit=20` | 分页列表 |
| GET | `/api/sandbox/find/{sandbox_id}` | 完整详情 |
| POST | `/api/sandbox/add` | 创建，初始暂停且 tick=0 |
| POST | `/api/sandbox/edit/{sandbox_id}` | 编辑名称、描述和拓扑，仅暂停时允许 |
| POST | `/api/sandbox/toggle/{sandbox_id}` | 运行/暂停，返回实际下一 tick 时间 |
| POST | `/api/sandbox/pause/{sandbox_id}` | 幂等暂停；离开沙盒页面时调用 |
| POST | `/api/sandbox/speed/{sandbox_id}` | 请求体 `{"speed": 10}`，返回重新调度后的下一 tick 时间 |
| GET | `/api/sandbox/drop/{sandbox_id}` | 删除暂停沙盒及全部数据 |
| GET | `/api/sandbox/export/{sandbox_id}` | 导出结构 JSON，不含规则和运行数据 |
| POST | `/api/sandbox/import` | multipart：`file、sandbox_name、description` |
| GET | `/api/sandbox/baseline/{sensor_id}` | 真实传感器最近一小时统计基准 |

新增和编辑请求：

```json
{
  "sandbox_name": "演示房间",
  "description": "规则演示",
  "config": {"speed": 1, "terminals": [], "sandbox_rule": []}
}
```

导入时重新生成沙盒 ID，并强制 `state=false、tick=0、speed=1、sandbox_rule=[]`。

成功时列表返回 `data: {"total": 0, "items": []}`，详情和写操作返回完整沙盒对象，删除返回
`data: {"ok": true}`。导出接口返回 `application/json` 文件流。

#### 配置目录

- 请求地址：`GET /api/sandbox/catalog/models`
- 请求头：`Authorization: Bearer <JWT令牌>`。
- 请求参数：无。
- 返回格式：`data` 为可用于沙盒配置的传感器型号数组。

- 请求地址：`GET /api/sandbox/catalog/models/{model_id}/sensors`
- 请求头：`Authorization: Bearer <JWT令牌>`。
- 路径参数：`model_id` 为传感器型号 ID。
- 返回格式：`data` 为该型号下可用于生成沙盒配置的传感器数组。

### 沙盒测量数据

#### 下采样或固定粒度查询

- 请求地址：`POST /api/sandbox/{sandbox_id}/measurements/query`
- 请求头：`Authorization: Bearer <JWT令牌>`、`Content-Type: application/json`
- 路径参数：`sandbox_id` 为沙盒 ID。
- 请求体（LTTB）：

```json
{
  "point_ids": ["virtual-point-id"],
  "start_tick": 0,
  "end_tick": 1001,
  "method": "lttb",
  "sample_count": 500
}
```

固定粒度请求将 `method` 设为 `fixed_interval`，并增加
`interval_ticks`；`aggregation` 支持 `mean`、`min`、`max`、`first`、`last`。
`point_ids` 为1～10项，`sample_count` 为3～5000，且 `end_tick` 必须大于
`start_tick`。

- 返回格式：每个测点包含 `point_id`、`original_count`、`returned_count`、
  `downsampled`、`ticks` 和 `values`。

#### 全量查询

- 请求地址：`POST /api/sandbox/{sandbox_id}/measurements/raw`
- 请求头：`Authorization: Bearer <JWT令牌>`、`Content-Type: application/json`
- 路径参数：`sandbox_id` 为沙盒 ID。
- 请求体：

```json
{"point_ids": ["virtual-point-id"], "start_tick": 0, "end_tick": 1001}
```

- 返回格式：返回全部 `ticks` 和 `values`，不执行采样。

#### CSV 导出

- 请求地址：`GET /api/sandbox/{sandbox_id}/measurements/export`
- 请求头：`Authorization: Bearer <JWT令牌>`。
- 路径参数：`sandbox_id` 为沙盒 ID。
- 查询参数：`point_ids` 可重复传入，且必须属于当前沙盒。
- 返回格式：`text/csv` 文件流，字段为
  `sandbox_id,point_id,tick,value`。

### 故障

- 请求地址：`POST /api/sandbox/{sandbox_id}/faults/inject`
- 请求头：`Authorization: Bearer <JWT令牌>`、`Content-Type: application/json`
- 路径参数：`sandbox_id` 为沙盒 ID。
- 请求体：

```json
{
  "fault_type": "drift",
  "point_id": "virtual-point-id",
  "duration_ticks": 20,
  "parameters": {"offset_per_tick": 0.1}
}
```

| `fault_type` | 参数 |
|---|---|
| `offset` | `offset` |
| `drift` | `offset_per_tick` |
| `spike` | `value`，可选 `mode=set/add` |
| `stuck` | 无，自动使用最近值 |
| `noise` | `noise` |

`duration_ticks=null` 表示持续到手动停止。故障从目标测点的下一个采样 tick 生效。

- `POST /api/sandbox/{sandbox_id}/faults/{event_id}/stop`：手动停止。
- `GET /api/sandbox/{sandbox_id}/faults/active`：活动故障。
- `POST /api/sandbox/{sandbox_id}/events?page=1&limit=20`：事件列表，可传 `{"event_type":"rule_triggered"}`。

以上接口均使用通用 Authorization 请求头。停止接口的路径参数为 `sandbox_id、event_id`；
活动故障接口无请求体；事件列表的 JSON 请求体可省略。返回格式分别为故障事件、活动故障数组，
以及 `{"total": 0, "items": []}` 分页对象。

### 独立规则

| 方法 | 地址 |
|---|---|
| GET | `/api/sandbox/{sandbox_id}/rules/list` |
| GET | `/api/sandbox/{sandbox_id}/rules/find/{rule_id}` |
| POST | `/api/sandbox/{sandbox_id}/rules/add` |
| POST | `/api/sandbox/{sandbox_id}/rules/edit/{rule_id}` |
| POST | `/api/sandbox/{sandbox_id}/rules/toggle/{rule_id}` |
| GET | `/api/sandbox/{sandbox_id}/rules/drop/{rule_id}` |
| GET | `/api/sandbox/{sandbox_id}/rules/ttl/{rule_id}` |

新增和编辑使用生产规则相同的 `RuleConfig`，但 selector 只能是当前沙盒虚拟测点的 `PointIdSelector`。TTL 位于 `resources/rdf/sandbox_rule/{sandbox_id}/{rule_id}.ttl`。

接口均使用通用 Authorization 请求头。`sandbox_id` 和 `rule_id` 为路径参数；新增和编辑使用
`RuleConfig` JSON 请求体，其余接口无请求体。列表返回规则数组，详情和写操作返回规则对象，
删除返回 `data: {"ok": true}`，TTL 接口返回 `data: {"rule_id": "...", "ttl": "..."}`。

规则结果写入 `rule_triggered、rule_recovered、virtual_action` 事件。所有动作仅提示，永远不会创建生产 ActionTask 或真实执行邮件、HTTP、MQTT、设备控制。

### WebSocket

连接：`WS /api/ws/sandboxes/{sandbox_id}`

连接成功或显示测点发生变化后，发送完整订阅列表：

```json
{
  "type": "subscribe",
  "token": "登录 token",
  "point_ids": ["virtual-point-1", "virtual-point-2"],
  "history_limit": 100
}
```

`point_ids` 会去重且最多10个，允许空数组取消全部曲线订阅。测点必须属于当前沙盒；`history_limit` 取值1～500，工作台默认读取最近100条。每次订阅完整替换当前连接的旧订阅。

订阅成功后返回快照：

```json
{
  "type": "snapshot",
  "subscription_version": 2,
  "sandbox": {
    "sandbox_id": "sandbox-id",
    "sandbox_name": "演示房间",
    "state": true,
    "tick": 120,
    "config": {"speed": 10, "terminals": [], "sandbox_rule": []}
  },
  "point_ids": ["virtual-point-1"],
  "rejected_point_ids": [],
  "series": [{
    "point_id": "virtual-point-1",
    "measurements": [{"tick": 119, "value": 23.8}, {"tick": 120, "value": 24.1}]
  }],
  "active_faults": [],
  "server_time": "2026-09-04T10:00:00Z",
  "next_tick_at": "2026-09-04T10:00:03Z",
  "tick_interval_seconds": 3
}
```

后续实时 tick 只包含本连接已订阅的测点：

```json
{
  "type": "tick",
  "sandbox_id": "sandbox-id",
  "tick": 121,
  "subscription_version": 2,
  "measurements": [{"point_id": "virtual-point-1", "tick": 121, "value": 24.2}],
  "server_time": "2026-09-04T10:00:03Z",
  "next_tick_at": "2026-09-04T10:00:06Z",
  "tick_interval_seconds": 3
}
```

消息类型：

- `snapshot`：当前沙盒、订阅测点最近数据和活动故障。
- `sandbox_state`：运行状态变化。
- `sandbox_speed`：倍速变化。
- `tick`：新 tick 和本连接订阅的测量列表。
- `fault_event`：故障开始、结束或到期事件。
- `rule_event`：规则触发、恢复和模拟动作事件。
- `error`：包括 `invalid_message`、`unauthorized`、`sandbox_not_found`、`internal_error` 和 `tick_failed`。
- `heartbeat`：空闲连接心跳。

`snapshot`、`tick` 使用 `subscription_version` 防止更换订阅时旧消息覆盖新曲线。状态、倍速和 tick 消息都携带 `server_time、next_tick_at、tick_interval_seconds`，前端应以这些字段显示倒计时，不应自行增加虚拟 tick。

工作台只在沙盒运行时保持 WebSocket 连接。暂停、切换沙盒或离开页面时应关闭连接；离开页面前调用幂等暂停接口，浏览器关闭/刷新场景使用带 `keepalive` 的暂停请求。
