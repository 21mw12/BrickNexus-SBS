# 采集请求 API

## 一、说明

Request 描述通过 MQTT 或 HTTP 获取设备数据的方式。接口需要 `channel` 或 `channel:requests` 页面权限。启用前建议先执行连通性测试。

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

### Request 分页查询

- 请求地址：`POST /api/request/list?page=XXX&limit=XXX`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 请求体参数：

  | 参数名   | 类型 | 必传 | 说明 |
  | -------- | ---- | ---- | ---- |
  | name     | str  | 否   | Request 名称，模糊匹配 |
  | type     | str  | 否   | 精确匹配 `mqtt` 或 `http` |
  | status   | bool | 否   | 是否启用 |

- 说明：请求体可以省略或传 `{}`。结果按创建时间倒序排列。分页列表只返回展示字段；完整配置和脱敏 `channel` 对象通过详情接口获取。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "total": 2,
          "items": [
              {
                  "request_id": "http-request-uuid",
                  "name": "三楼温度采集",
                  "type": "http",
                  "status": true,
                  "created_at": "2026-08-25T10:10:00Z"
              },
              {
                  "request_id": "mqtt-request-uuid",
                  "name": "一号楼 MQTT 采集",
                  "type": "mqtt",
                  "status": false,
                  "created_at": "2026-08-25T10:05:00Z"
              }
          ]
      }
  }
  ```



### 查询 Request 详情

- 请求地址：`GET /api/request/find/{request_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 说明：返回完整 Request 配置以及脱敏通道。前端编辑时使用这些字段，不需要自行查询通道密码。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "request_id": "http-request-uuid",
          "name": "三楼温度采集",
          "type": "http",
          "channel_id": "http-channel-uuid",
          "interval_seconds": 60,
          "time_json_path": "$.time",
          "time_format": "yyyy-MM-dd hh:mm:ss",
          "status": false,
          "created_at": "2026-08-25T10:10:00Z",
          "mqtt_topic": null,
          "http_method": "GET",
          "http_path": "/measurements",
          "http_header": {},
          "http_params": {"floor": 3},
          "http_body": null,
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



### 新增 Request

- 请求地址：`POST /api/request/add`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 请求体参数：

  | 参数名          | 类型       | 必传 | 默认值 | 说明 |
  | --------------- | ---------- | ---- | ------ | ---- |
  | name            | str        | 是   | —      | Request 名称，最长 20 字符，全局唯一 |
  | type            | str        | 是   | —      | `mqtt` 或 `http` |
  | channel_id      | str        | 是   | —      | 与 `type` 对应的通道 ID |
  | interval_seconds| int        | 否   | 60     | HTTP 请求间隔或 MQTT SQL 入库周期，必须大于 0 |
  | time_json_path  | str / null | 否   | null   | 响应中测量时间的 JSONPath，最长 200 字符 |
  | time_format     | str / null | 否   | null   | 时间格式，最长 50 字符；小写 `hh` 表示 24 小时制 |

- MQTT 专用参数：

  | 参数名     | 类型 | 必传 | 说明 |
  | ---------- | ---- | ---- | ---- |
  | mqtt_topic | str  | 是   | 订阅主题，最长 30 字符 |

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
      "name": "一号楼 MQTT 采集",
      "type": "mqtt",
      "channel_id": "mqtt-channel-uuid",
      "interval_seconds": 60,
      "time_json_path": "$.time",
      "time_format": "yyyy-MM-dd hh:mm:ss",
      "mqtt_topic": "building/one/measurements"
  }
  ```

- HTTP 请求体示例：

  ```json
  {
      "name": "三楼温度采集",
      "type": "http",
      "channel_id": "http-channel-uuid",
      "interval_seconds": 60,
      "time_json_path": "$.time",
      "time_format": "yyyy-MM-dd hh:mm:ss",
      "http_method": "GET",
      "http_path": "/measurements",
      "http_header": {},
      "http_params": {"floor": 3},
      "http_body": null
  }
  ```

- 说明：新建后固定 `status=false`，只能通过 toggle 启用。MQTT 和 HTTP 字段不得混用。同一 MQTT 通道下 `mqtt_topic` 唯一；同一 HTTP 通道下 `http_path` 唯一。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "request_id": "http-request-uuid",
          "name": "三楼温度采集",
          "type": "http",
          "channel_id": "http-channel-uuid",
          "interval_seconds": 60,
          "time_json_path": "$.time",
          "time_format": "yyyy-MM-dd hh:mm:ss",
          "status": false,
          "created_at": "2026-08-25T10:10:00Z",
          "mqtt_topic": null,
          "http_method": "GET",
          "http_path": "/measurements",
          "http_header": {},
          "http_params": {"floor": 3},
          "http_body": null,
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



### 修改 Request

- 请求地址：`POST /api/request/edit/{request_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 请求体参数：

  | 参数名 | 类型 | 必传 | 说明 |
  | ------ | ---- | ---- | ---- |
  | name | str | 否 | 新名称，最长 20 字符且不可重复 |
  | type | str | 否 | `mqtt` 或 `http`；切换类型时必须同时提供新协议必填字段 |
  | channel_id | str | 否 | 新通道 ID，必须与最终 `type` 一致 |
  | interval_seconds | int | 否 | 新周期，必须大于 0 |
  | time_json_path | str / null | 否 | 新时间 JSONPath；`null` 表示清除 |
  | time_format | str / null | 否 | 新时间格式；`null` 表示清除 |
  | mqtt_topic | str | MQTT 否 | MQTT 主题 |
  | http_method | str | HTTP 否 | `GET` 或 `POST` |
  | http_path | str | HTTP 否 | HTTP 路径 |
  | http_header | object / null | HTTP 否 | 独享 Header |
  | http_params | object / null | HTTP GET 否 | GET 参数 |
  | http_body | object / null | HTTP POST 否 | POST 请求体 |

- 说明：只有 `status=false` 的 Request 可以编辑。协议字段仍执行与新增相同的互斥、通道类型和唯一性校验。状态不能由本接口修改。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "request_id": "http-request-uuid",
          "name": "三楼温度采集",
          "type": "http",
          "channel_id": "http-channel-uuid",
          "interval_seconds": 120,
          "time_json_path": "$.time",
          "time_format": "yyyy-MM-dd hh:mm:ss",
          "status": false,
          "created_at": "2026-08-25T10:10:00Z",
          "mqtt_topic": null,
          "http_method": "GET",
          "http_path": "/measurements",
          "http_header": {},
          "http_params": {"floor": 3, "enabled": true},
          "http_body": null,
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



### 测试 Request 连通性

- 请求地址：`POST /api/request/test/{request_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 请求体参数：

  | 参数名  | 类型  | 必传 | 默认值 | 说明 |
  | ------- | ----- | ---- | ------ | ---- |
  | timeout | float | 否   | 10.0   | 本次连通性测试超时秒数 |

- 说明：API 类型按已保存配置立即请求完整 URL；MQTT 类型使用独立测试客户端连接并订阅已保存 Topic，在超时前等待一条消息。该接口不写 Measurement、不更新 Redis，也不改变 Request 状态。

- API 成功响应：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "ok": true,
          "data": {
              "time": "2026-08-25 10:30:00",
              "temperature": 25.3
          },
          "message": null
      }
  }
  ```

- MQTT 连接成功但超时未收到数据的响应：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "ok": true,
          "data": null,
          "message": "connected; no message received before timeout"
      }
  }
  ```



### 启用或停用 Request

- 请求地址：`POST /api/request/toggle/{request_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 请求体：无

- 说明：`false → true` 时重新校验通道并启动采集；`true → false` 时停止采集。API 按 `interval_seconds` 调度。MQTT 每条消息仍更新状态、Redis、WebSocket 和规则事件，SQL 仅保存每个 `interval_seconds` 周期内最后一批，默认 60 秒。同一 MQTT 通道的多个 Request 共享一个客户端，最后一个 Request 停止后才断开连接。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "request_id": "http-request-uuid",
          "name": "三楼温度采集",
          "type": "http",
          "channel_id": "http-channel-uuid",
          "interval_seconds": 60,
          "time_json_path": "$.time",
          "time_format": "yyyy-MM-dd hh:mm:ss",
          "status": true,
          "created_at": "2026-08-25T10:10:00Z",
          "mqtt_topic": null,
          "http_method": "GET",
          "http_path": "/measurements",
          "http_header": {},
          "http_params": {"floor": 3},
          "http_body": null,
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



### 删除 Request

- 请求地址：`GET /api/request/drop/{request_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 说明：只有 `status=false` 的 Request 可以删除。删除前会将所有引用该 Request 的 `assets_terminal.request_id` 清空。

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
