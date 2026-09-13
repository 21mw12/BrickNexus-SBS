# 采控通道 API

## 一、说明

Channel 保存 MQTT 或 HTTP 连接配置，供采集请求与控制任务引用。接口需要 `channel` 或
`channel:requests` 页面权限。凭据等敏感字段应由部署环境妥善保护。

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

### MQTT 通道

#### MQTT 通道分页查询

- 请求地址：`POST /api/channel/mqtt/list?page=XXX&limit=XXX`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 请求体参数：

  | 参数名      | 类型 | 必传 | 说明 |
  | ----------- | ---- | ---- | ---- |
  | broker_host | str  | 否   | MQTT Broker 地址，模糊匹配 |
  | username    | str  | 否   | 用户名，模糊匹配 |

- 说明：请求体可以省略或传 `{}`。结果按创建时间倒序排列。响应永远不会返回密码明文或数据库密文。

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
                  "channel_mqtt_id": "mqtt-channel-uuid",
                  "broker_host": "mqtt.example.com",
                  "broker_port": 1883,
                  "created_at": "2026-08-25T10:00:00Z"
              }
          ]
      }
  }
  ```



#### 查询 MQTT 通道详情

- 请求地址：`GET /api/channel/mqtt/find/{channel_mqtt_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 说明：`password_configured=true` 仅表示已经配置密码，不代表密码内容。接口不返回密码。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
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
  ```



#### 新增 MQTT 通道

- 请求地址：`POST /api/channel/mqtt/add`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- JSON 请求体参数：

  | 参数名         | 类型 | 必传 | 默认值 | 说明 |
  | -------------- | ---- | ---- | ------ | ---- |
  | broker_host    | str  | 是   | —      | Broker 主机名或 IP，最长 30 字符，不包含端口 |
  | broker_port    | int  | 否   | 1883   | Broker 端口，范围 1～65535 |
  | username       | str  | 否   | null   | MQTT 用户名，最长 20 字符 |
  | password       | str  | 否   | null   | MQTT 密码；后端使用 Fernet 加密保存 |
  | qos            | int  | 否   | 1      | MQTT QoS，只允许 0、1、2 |
  | connect_timeout| int  | 否   | 20     | 连接超时秒数，必须大于 0 |
  | data_timeout   | int  | 否   | 120    | 最长无数据等待秒数，必须大于 0 |

- 说明：`channel_mqtt_id` 和全局唯一 `client_id` 由后端生成，前端不能指定。MQTT 密码使用后端代码中的固定 Fernet 密钥加密，不依赖环境变量；修改固定密钥会导致已有密码无法解密。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
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
  ```



#### 修改 MQTT 通道

- 请求地址：`POST /api/channel/mqtt/edit/{channel_mqtt_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 请求体参数：

  | 参数名          | 类型       | 必传 | 说明 |
  | --------------- | ---------- | ---- | ---- |
  | broker_host     | str        | 否   | 新 Broker 地址 |
  | broker_port     | int        | 否   | 新端口，范围 1～65535 |
  | username        | str / null | 否   | 新用户名；`null` 表示清除 |
  | password        | str / null | 否   | 不提交表示保留旧密码；`null` 表示清除；字符串表示重新加密保存 |
  | qos             | int        | 否   | 0、1、2 |
  | connect_timeout | int        | 否   | 连接超时秒数，必须大于 0 |
  | data_timeout    | int        | 否   | 无数据超时秒数，必须大于 0 |

- 说明：所有字段均可选。只要该通道存在启用中的 Request 或 Control，就禁止修改；必须先停用相关配置。`client_id` 不允许编辑。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "channel_mqtt_id": "mqtt-channel-uuid",
          "broker_host": "mqtt.example.com",
          "broker_port": 1883,
          "client_id": "smartbuilding-后端生成UUID",
          "username": "collector",
          "password_configured": true,
          "qos": 2,
          "connect_timeout": 20,
          "data_timeout": 180,
          "created_at": "2026-08-25T10:00:00Z"
      }
  }
  ```



#### 删除 MQTT 通道

- 请求地址：`GET /api/channel/mqtt/drop/{channel_mqtt_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 说明：通道只要被任意 Request 或 Control 引用就禁止删除，不区分引用对象是否启用。应先删除或改绑引用配置。

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



### HTTP 通道

#### HTTP 通道分页查询

- 请求地址：`POST /api/channel/http/list?page=XXX&limit=XXX`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 请求体参数：

  | 参数名  | 类型 | 必传 | 说明 |
  | ------- | ---- | ---- | ---- |
  | base_url| str  | 否   | HTTP 基础地址，模糊匹配 |

- 说明：请求体可以省略或传 `{}`。结果按创建时间倒序排列。

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
                  "channel_http_id": "http-channel-uuid",
                  "base_url": "https://api.example.com",
                  "created_at": "2026-08-25T10:00:00Z"
              }
          ]
      }
  }
  ```



#### 查询 HTTP 通道详情

- 请求地址：`GET /api/channel/http/find/{channel_http_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：无

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "channel_http_id": "http-channel-uuid",
          "base_url": "https://api.example.com",
          "default_headers": {
              "Authorization": "Bearer public-token"
          },
          "default_timeout": 20,
          "created_at": "2026-08-25T10:00:00Z"
      }
  }
  ```



#### 新增 HTTP 通道

- 请求地址：`POST /api/channel/http/add`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- JSON 请求体参数：

  | 参数名          | 类型             | 必传 | 默认值 | 说明 |
  | --------------- | ---------------- | ---- | ------ | ---- |
  | base_url        | str              | 是   | —      | 完整 HTTP/HTTPS 基础地址，最长 200 字符 |
  | default_headers | object / null    | 否   | null   | 公共请求头；键和值都必须是字符串 |
  | default_timeout | int              | 否   | 20     | HTTP 超时秒数，必须大于 0 |

- 请求体示例：

  ```json
  {
      "base_url": "https://api.example.com",
      "default_headers": {
          "Authorization": "Bearer public-token",
          "X-System": "SmartBuilding"
      },
      "default_timeout": 20
  }
  ```

- 说明：`base_url` 必须包含 `http://` 或 `https://`。保存时移除末尾 `/`。公共 Header 会与 Request/Control 的独享 Header 合并，独享值覆盖同名公共值。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "channel_http_id": "http-channel-uuid",
          "base_url": "https://api.example.com",
          "default_headers": {
              "Authorization": "Bearer public-token",
              "X-System": "SmartBuilding"
          },
          "default_timeout": 20,
          "created_at": "2026-08-25T10:00:00Z"
      }
  }
  ```



#### 修改 HTTP 通道

- 请求地址：`POST /api/channel/http/edit/{channel_http_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 请求体参数：

  | 参数名          | 类型          | 必传 | 说明 |
  | --------------- | ------------- | ---- | ---- |
  | base_url        | str           | 否   | 新的完整 HTTP/HTTPS 基础地址 |
  | default_headers | object / null | 否   | 新公共 Header；`null` 表示清空为 `{}` |
  | default_timeout | int           | 否   | 新超时秒数，必须大于 0 |

- 请求体示例：

  ```json
  {
      "default_headers": {
          "Authorization": "Bearer new-token"
      },
      "default_timeout": 30
  }
  ```

- 说明：所有字段均可选。该通道存在启用中的 Request 或 Control 时禁止修改，必须先停用相关配置。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "channel_http_id": "http-channel-uuid",
          "base_url": "https://api.example.com",
          "default_headers": {
              "Authorization": "Bearer new-token"
          },
          "default_timeout": 30,
          "created_at": "2026-08-25T10:00:00Z"
      }
  }
  ```



#### 删除 HTTP 通道

- 请求地址：`GET /api/channel/http/drop/{channel_http_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 说明：通道被任意 Request 或 Control 引用时禁止删除。应先删除或改绑引用配置。

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



### 获取通道配置选项

- 请求地址：`GET /api/channel/options`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：无

- 说明：`label` 用于前端中文展示，`value` 是创建 Request/Control 时实际提交的英文值。拥有 `channel`、`channel:requests`、`channel:controls` 任一页面权限即可访问。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "types": [
              {"label": "MQTT", "value": "mqtt"},
              {"label": "HTTP", "value": "http"}
          ],
          "qos": [
              {"label": "QoS 0", "value": 0},
              {"label": "QoS 1", "value": 1},
              {"label": "QoS 2", "value": 2}
          ],
          "http_methods": [
              {"label": "GET", "value": "GET"},
              {"label": "POST", "value": "POST"}
          ]
      }
  }
  ```
