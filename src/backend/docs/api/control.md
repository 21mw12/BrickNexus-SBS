# 设备控制 API

## 一、说明

Control 描述通过 MQTT 或 HTTP 下发控制命令的方式。接口需要 `channel` 或 `channel:controls` 页面权限；立即执行还需目标资产的操作权限。

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

### Control 分页查询

- 请求地址：`POST /api/control/list?page=XXX&limit=XXX`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 请求体参数：

  | 参数名     | 类型 | 必传 | 说明 |
  | ---------- | ---- | ---- | ---- |
  | name       | str  | 否   | Control 名称，模糊匹配 |
  | type       | str  | 否   | 精确匹配 `mqtt` 或 `http` |
  | status     | bool | 否   | 是否启用 |
  | asset_type | str  | 否   | `terminal` 或 `sensor`，筛选绑定资产类型 |
  | asset_id   | str  | 否   | 精确匹配绑定资产 ID |

- 说明：请求体可以省略或传 `{}`。需要 `channel` 或 `channel:controls` 页面权限。结果按当前用户具有 R 权限的终端或传感器过滤，再进行分页。指定 `asset_id` 时，如果当前用户没有该资产的 R 权限，接口明确返回 403，不再以 `total=0` 隐藏权限问题。分页列表只返回展示字段，完整配置通过详情接口获取。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "total": 1,
          "items": [
              {
                  "control_id": "control-uuid",
                  "name": "打开三楼风机",
                  "type": "mqtt",
                  "asset_type": "terminal",
                  "asset_name": "三楼风机控制终端",
                  "status": true,
                  "created_at": "2026-08-25T10:20:00Z"
              }
          ]
      }
  }
  ```



### 查询 Control 详情

- 请求地址：`GET /api/control/find/{control_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 说明：需要 `channel` 或 `channel:controls` 页面权限，同时需要绑定资产的 R 权限。返回完整控制配置、资产摘要和脱敏通道。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "control_id": "control-uuid",
          "name": "开启空调",
          "type": "http",
          "channel_id": "http-channel-uuid",
          "asset_type": "sensor",
          "asset_id": "sensor-uuid",
          "status": false,
          "created_at": "2026-08-25T10:20:00Z",
          "mqtt_topic": null,
          "mqtt_retained": null,
          "mqtt_payload": null,
          "http_method": "POST",
          "http_path": "/air-conditioner/switch",
          "http_header": {"X-Control": "manual"},
          "http_params": null,
          "http_body": {"enabled": true},
          "asset": {
              "asset_id": "sensor-uuid",
              "asset_type": "sensor",
              "name": "三楼空调控制器",
              "is_use": true
          },
          "channel": {
              "channel_http_id": "http-channel-uuid",
              "base_url": "https://api.example.com",
              "default_headers": {},
              "default_timeout": 20,
              "created_at": "2026-08-25T10:00:00Z"
          }
      }
  }
  ```



### 新增 Control

- 请求地址：`POST /api/control/add`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 公共 JSON 请求体参数：

  | 参数名    | 类型 | 必传 | 说明 |
  | --------- | ---- | ---- | ---- |
  | name      | str  | 是   | Control 名称，最长 30 字符，全局唯一 |
  | type      | str  | 是   | `mqtt` 或 `http` |
  | channel_id| str  | 是   | 与 `type` 对应的通道 ID |
  | asset_type| str  | 是   | 被控资产类型：`terminal` 或 `sensor` |
  | asset_id  | str  | 是   | 被控终端或传感器的资产 ID |

- MQTT 专用参数：

  | 参数名        | 类型 | 必传 | 默认值 | 说明 |
  | ------------- | ---- | ---- | ------ | ---- |
  | mqtt_topic    | str  | 是   | —      | 发布主题，最长 30 字符 |
  | mqtt_retained | bool | 否   | false  | 是否发送保留消息 |
  | mqtt_payload  | str  | 是   | —      | 原始非空文本，可以是 JSON 字符串或普通文本 |

- HTTP 专用参数：

  | 参数名    | 类型          | 必传 | 说明 |
  | --------- | ------------- | ---- | ---- |
  | http_method| str           | 是   | `GET` 或 `POST` |
  | http_path  | str           | 是   | 与通道 `base_url` 拼接的路径，最长 100 字符 |
  | http_header| object / null | 否   | 独享 Header，值覆盖同名公共 Header |
  | http_params| object / null | GET 否 | GET 查询参数；POST 时必须为空 |
  | http_body  | object / null | POST 否 | POST JSON 请求体；GET 时必须为空 |

- MQTT 请求体示例：

  ```json
  {
      "name": "打开三楼风机",
      "type": "mqtt",
      "channel_id": "mqtt-channel-uuid",
      "asset_type": "terminal",
      "asset_id": "terminal-uuid",
      "mqtt_topic": "building/3f/fan/control",
      "mqtt_retained": false,
      "mqtt_payload": "{\"enabled\":true}"
  }
  ```

- HTTP 请求体示例：

  ```json
  {
      "name": "开启空调",
      "type": "http",
      "channel_id": "http-channel-uuid",
      "asset_type": "sensor",
      "asset_id": "sensor-uuid",
      "http_method": "POST",
      "http_path": "/air-conditioner/switch",
      "http_header": {"X-Control": "manual"},
      "http_params": null,
      "http_body": {"enabled": true}
  }
  ```

- 说明：需要绑定终端或传感器的 O 权限。新建后固定 `status=false`。此时允许资产暂未启用，但启用 Control 时会重新校验资产存在、类型与 `asset_type` 一致且 `is_use=true`。MQTT 与 HTTP 字段不得混用。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "control_id": "control-uuid",
          "name": "打开三楼风机",
          "type": "mqtt",
          "channel_id": "mqtt-channel-uuid",
          "asset_type": "terminal",
          "asset_id": "terminal-uuid",
          "status": false,
          "created_at": "2026-08-25T10:20:00Z",
          "mqtt_topic": "building/3f/fan/control",
          "mqtt_retained": false,
          "mqtt_payload": "{\"enabled\":true}",
          "http_method": null,
          "http_path": null,
          "http_header": null,
          "http_params": null,
          "http_body": null,
          "asset": {
              "asset_id": "terminal-uuid",
              "asset_type": "terminal",
              "name": "三楼风机控制终端",
              "is_use": true
          },
          "channel": {
              "channel_mqtt_id": "mqtt-channel-uuid",
              "broker_host": "mqtt.example.com",
              "broker_port": 1883,
              "client_id": "smartbuilding-后端生成UUID",
              "username": "collector",
              "password_configured": true,
              "qos": 1,
              "connect_timeout": 20,
              "data_timeout": 120,
              "created_at": "2026-08-25T10:00:00Z"
          }
      }
  }
  ```



### 修改 Control

- 请求地址：`POST /api/control/edit/{control_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 请求体参数：

  | 参数名 | 类型 | 必传 | 说明 |
  | ------ | ---- | ---- | ---- |
  | name | str | 否 | 新名称，最长 30 字符且不可重复 |
  | type | str | 否 | `mqtt` 或 `http`；切换类型时必须提供新协议必填字段 |
  | channel_id | str | 否 | 新通道 ID，必须与最终 `type` 一致 |
  | asset_type | str | 否 | 新资产类型：`terminal` 或 `sensor` |
  | asset_id | str | 否 | 新终端或传感器 ID |
  | mqtt_topic | str | MQTT 否 | MQTT 发布主题 |
  | mqtt_retained | bool | MQTT 否 | 是否发送保留消息 |
  | mqtt_payload | str | MQTT 否 | 保存的原始发送内容 |
  | http_method | str | HTTP 否 | `GET` 或 `POST` |
  | http_path | str | HTTP 否 | HTTP 路径 |
  | http_header | object / null | HTTP 否 | 独享 Header |
  | http_params | object / null | HTTP GET 否 | GET 参数 |
  | http_body | object / null | HTTP POST 否 | POST 请求体 |

- 说明：只有 `status=false` 的 Control 可以修改，需要原绑定资产 O 权限；更换 `asset_type` 或 `asset_id` 时还需要新绑定资产 O 权限。两个字段可以单独提交，但组合后的资产类型和 ID 必须匹配。状态不能由本接口修改。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "control_id": "control-uuid",
          "name": "打开三楼风机",
          "type": "mqtt",
          "channel_id": "mqtt-channel-uuid",
          "asset_type": "terminal",
          "asset_id": "terminal-uuid",
          "status": false,
          "created_at": "2026-08-25T10:20:00Z",
          "mqtt_topic": "building/3f/fan/control",
          "mqtt_retained": true,
          "mqtt_payload": "{\"enabled\":false}",
          "http_method": null,
          "http_path": null,
          "http_header": null,
          "http_params": null,
          "http_body": null,
          "asset": {
              "asset_id": "terminal-uuid",
              "asset_type": "terminal",
              "name": "三楼风机控制终端",
              "is_use": true
          },
          "channel": {
              "channel_mqtt_id": "mqtt-channel-uuid",
              "broker_host": "mqtt.example.com",
              "broker_port": 1883,
              "client_id": "smartbuilding-后端生成UUID",
              "username": "collector",
              "password_configured": true,
              "qos": 1,
              "connect_timeout": 20,
              "data_timeout": 120,
              "created_at": "2026-08-25T10:00:00Z"
          }
      }
  }
  ```



### 启用或停用 Control

- 请求地址：`POST /api/control/toggle/{control_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 请求体：无

- 说明：需要绑定资产 O 权限。`false → true` 时重新校验终端或传感器存在、类型正确、`is_use=true` 且通道类型匹配；`true → false` 时直接停用。启用 Control 不会自动执行控制。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "ok": true
      }
  }
  ```



### 删除 Control

- 请求地址：`GET /api/control/drop/{control_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 说明：需要绑定终端或传感器的 O 权限。只有 `status=false` 的 Control 可以删除。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "ok": true
      }
  }
  ```



### 立即执行 Control

- 请求地址：`POST /api/control/execute/{control_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 请求体：无。本阶段不允许临时覆盖已保存的 payload、params 或 body。

- 说明：需要绑定终端或传感器的 O 权限，且 Control 必须为 `status=true`。执行前再次校验资产存在、类型匹配且启用。MQTT 使用一次性随机客户端，按通道 QoS 发布已保存的 `mqtt_payload` 和 retained；HTTP 使用通道超时及合并后的 Header，GET 使用 params，POST 使用 body。本阶段不保存执行历史。

- MQTT 执行成功响应：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "success": true,
          "executed_at": "2026-08-25T10:30:00Z",
          "result": {
              "protocol": "mqtt",
              "message_id": 12,
              "published": true
          }
      }
  }
  ```

- HTTP 执行成功响应：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "success": true,
          "executed_at": "2026-08-25T10:30:00Z",
          "result": {
              "protocol": "http",
              "response": {
                  "accepted": true
              }
          }
      }
  }
  ```
