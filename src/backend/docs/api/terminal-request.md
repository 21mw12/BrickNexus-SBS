# 终端采集请求绑定 API

## 一、说明

该模块配置 Terminal 与采集 Request 的树形绑定关系，需要 `channel` 或
`channel:requests` 页面权限。读取和编辑均会校验终端资产权限。

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

### 查询终端测点树

- 请求地址：`GET /api/terminal_request/tree/{terminal_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：无

- 返回格式：返回终端 → 传感器 → 测点的树形结构

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "terminal_id": "xxx",
          "terminal_name": "网关-01",
          "request_id": "yyy",
          "last_receive_time": "2026-07-28T10:30:00+08:00",
          "time_json_path": "$.timestamp",
          "time_format": "yyyy-MM-dd hh:mm:ss",
          "sensors": [
              {
                  "sensor_id": "zzz",
                  "sensor_name": "温湿度传感器-01",
                  "points": [
                      {
                          "point_id": "aaa",
                          "source_model_id": "型号UUID",
                          "source_point_id": "全局测点UUID",
                          "point_name": "温度",
                          "point_unit": "°C",
                          "point_description": "设备周围环境温度",
                          "json_path": "$.data.temperature"
                      },
                      {
                          "point_id": "bbb",
                          "source_model_id": "型号UUID",
                          "source_point_id": "全局测点UUID",
                          "point_name": "湿度",
                          "point_unit": "%",
                          "point_description": "设备周围环境湿度",
                          "json_path": "$.data.humidity"
                      }
                  ]
              }
          ]
      }
  }
  ```



### 编辑终端测点树

- 请求地址：`POST /api/terminal_request/edit/{terminal_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数（全部可选）：

  | 参数名     | 类型            | 必传 | 说明        |
  | ---------- | --------------- | ---- | ----------- |
  | request_id | str             | 否   | 终端请求ID   |
  | points     | List[PointEdit] | 否   | 测点编辑列表 |

  **PointEdit**：

  | 参数名    | 类型 | 必传 | 说明              |
  | --------- | ---- | ---- | ----------------- |
  | point_id  | str  | 否   | 测点ID            |
  | json_path | str  | 否   | JSON 数据提取路径 |

- 请求示例：

  ```json
  {
      "request_id": "新的请求ID",
      "points": [
         {"point_id": "测点ID", "json_path": "$.data.temp"},
         {"point_id": "测点ID2", "json_path": "$.data.humi"}
      ]
  }
  ```

- 返回格式：同查询终端测点树
