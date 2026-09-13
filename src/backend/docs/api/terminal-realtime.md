# 终端实时数据 API

## 一、说明

本模块使用 WebSocket。鉴权令牌放在客户端的 `subscribe` 消息中，不放在 URL；需要 `data` 或 `data:realtime` 页面权限以及 Terminal 的 R 权限。

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

### 建立连接

- 请求地址：`WS /api/ws/terminals`

- 完整地址示例：

  ```text
  ws://127.0.0.1:27001/api/ws/terminals
  ```

- 说明：

  - JWT 不放在 URL 或请求头中，而是由客户端在每次提交订阅列表时放入 JSON 消息
  - WebSocket 接口不会出现在 FastAPI OpenAPI/Swagger 页面中，请以本文档为准
  - 建立连接本身不会产生数据，客户端必须先发送一条 `subscribe` 消息



### 提交或修改订阅列表

- 客户端消息：

  ```json
  {
      "type": "subscribe",
      "token": "JWT令牌",
      "terminal_ids": [
          "terminal-001",
          "terminal-002"
      ]
  }
  ```

- 参数：

  | 参数名       | 类型      | 必传 | 说明                                       |
  | ------------ | --------- | ---- | ------------------------------------------ |
  | type         | str       | 是   | 固定为 `subscribe`                         |
  | token        | str       | 是   | 当前用户JWT令牌，可带或不带 `Bearer ` 前缀 |
  | terminal_ids | List[str] | 是   | 本连接需要订阅的完整Terminal ID列表        |

- 订阅规则：

  - 每次消息都会重新验证 token、`data` / `data:realtime` 页面权限和资产R权限
  - 本次列表完整替换该连接之前的列表，不是增量添加
  - 重复Terminal ID会去重，并保持第一次出现时的顺序
  - 发送 `"terminal_ids": []` 表示取消当前连接的全部订阅
  - token无效或页面权限不足时，服务端会先清空旧订阅，再返回 `unauthorized`
  - 消息格式错误不会修改连接原有的订阅列表



### 初始快照响应

服务端完成权限过滤后，立即读取Redis中的最新数据并返回：

```json
{
    "type": "snapshot",
    "terminal_ids": [
        "terminal-001"
    ],
    "rejected_terminal_ids": [
        "terminal-002"
    ],
    "missing_terminal_ids": [
        "terminal-003"
    ],
    "data": [
        {
            "terminal_id": "terminal-001",
            "terminal_status": true,
            "sensor_list": [
                {
                    "sensor_id": "sensor-001",
                    "sensor_status": true,
                    "point_list": [
                        {
                            "point_id": "point-001",
                            "value": 23.5,
                            "unit": "℃",
                            "point_description": "设备周围环境温度"
                        }
                    ]
                }
            ],
            "time": "2026-08-12T10:00:00+08:00"
        }
    ]
}
```

字段说明：

| 字段名                | 类型       | 说明                                       |
| --------------------- | ---------- | ------------------------------------------ |
| terminal_ids          | List[str]  | 校验通过并已经生效的订阅列表               |
| rejected_terminal_ids | List[str]  | 不存在、不是Terminal或用户无R权限的ID      |
| missing_terminal_ids  | List[str]  | 权限合法但Redis中尚无最新快照的Terminal ID |
| data                  | List[dict] | 当前能够从Redis读取到的Terminal最新快照    |

`missing_terminal_ids` 中的Terminal仍然处于订阅状态。它之后第一次产生采集数据时，服务端会正常推送 `terminal_update`。

服务端不会向客户端说明某个 rejected ID 是“不存在”还是“无权限”，避免泄露不可见资产信息。



### Terminal实时更新

当订阅中的某个Terminal发生变化时，服务端逐Terminal推送：

```json
{
    "type": "terminal_update",
    "terminal_id": "terminal-001",
    "data": {
        "terminal_id": "terminal-001",
        "terminal_status": true,
        "sensor_list": [
            {
                "sensor_id": "sensor-001",
                "sensor_status": true,
                "point_list": [
                    {
                        "point_id": "point-001",
                        "value": 24.1,
                        "unit": "℃",
                        "point_description": "设备周围环境温度"
                    }
                ]
            }
        ],
        "time": "2026-08-12T10:01:00+08:00"
    }
}
```

- 每个更新消息只包含一个Terminal
- 推送内容是收到通知后重新从Redis读取的最新快照
- Redis只保存最新状态，因此该接口用于实时界面，不保证传递每一个历史采集变化
- 历史测量数据仍以PostgreSQL中的 `measurement` 表为准
- Terminal变为离线时也会更新Redis并产生相同格式的推送，此时 `terminal_status` 为 `false`



### 错误消息

```json
{
    "type": "error",
    "code": "invalid_message",
    "message": "terminal_ids must be a list"
}
```

| code              | 说明                                                |
| ----------------- | --------------------------------------------------- |
| invalid_message   | JSON或字段格式错误，原订阅保持不变                  |
| unauthorized      | token无效或页面权限不足，原订阅会被清空             |
| redis_unavailable | 当前无法读取Redis快照，已经验证通过的新订阅会被保留 |
| internal_error    | 权限查询等服务端操作失败                            |

如果客户端长时间不能消费推送，导致服务端发送队列已满，服务端会使用WebSocket关闭码 `1013` 主动断开，前端应稍后重新连接并再次提交完整订阅列表。
