# 测点定义 API

## 一、说明

Point 是全局测点定义，可被传感器型号引用。查询需要 `asset`、`asset:model`、
`asset:tree` 或 `asset:table` 页面权限；写操作需要 `asset` 或 `asset:model`。

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

### 查询所有测点

- 请求地址：`GET /api/points/list?page=1&limit=20`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：

  | 参数名 | 类型 | 必传 | 说明              |
  | ------ | ---- | ---- | ----------------- |
  | page   | int  | 否   | 页码，默认值为 1  |
  | limit  | int  | 否   | 每页数量，默认 20 |

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
                  "point_id": "8f156708-1fe2-4598-9d4e-7db5c41dd001",
                  "point_name": "温度",
                  "point_unit": "℃",
                  "point_description": "设备周围环境温度"
              },
              {
                  "point_id": "8f156708-1fe2-4598-9d4e-7db5c41dd002",
                  "point_name": "湿度",
                  "point_unit": "%",
                  "point_description": null
              }
          ]
      }
  }
  ```



### 根据测点ID获取详细信息

- 请求地址：`GET /api/points/find/{point_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：

  | 参数名   | 类型 | 必传 | 说明   |
  | -------- | ---- | ---- | ------ |
  | point_id | str  | 是   | 测点ID |

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "point_id": "8f156708-1fe2-4598-9d4e-7db5c41dd001",
          "point_name": "温度",
          "point_unit": "℃",
          "point_description": "设备周围环境温度"
      }
  }
  ```



### 新增测点

- 请求地址：`POST /api/points/add`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：

  | 参数名            | 类型       | 必传 | 说明                                      |
  | ----------------- | ---------- | ---- | ----------------------------------------- |
  | point_name        | str        | 是   | 测点名称，长度 1～20                      |
  | point_unit        | str        | 是   | 测点单位，最长 10 字符；空字符串表示无单位 |
  | point_description | str / null | 否   | 测点描述，最长 200 字符，默认值为 `null` |

- 说明：去除名称和单位首尾空白后，`point_name + point_unit` 必须唯一。无量纲或状态类测点使用空字符串 `""` 表示无单位。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "point_id": "8f156708-1fe2-4598-9d4e-7db5c41dd001",
          "point_name": "温度",
          "point_unit": "℃",
          "point_description": "设备周围环境温度"
      }
  }
  ```



### 修改测点描述

- 请求地址：`POST /api/points/edit/{point_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：

  | 参数名            | 类型       | 必传 | 说明                                   |
  | ----------------- | ---------- | ---- | -------------------------------------- |
  | point_description | str / null | 是   | 测点描述，最长 200 字符；`null` 为清空 |

- 说明：测点名称和单位创建后不可修改。SensorPoint 不保存描述副本，查询和采集时根据 `source_point_id` 读取 Point 描述。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "point_id": "8f156708-1fe2-4598-9d4e-7db5c41dd001",
          "point_name": "温度",
          "point_unit": "℃",
          "point_description": "设备周围环境温度"
      }
  }
  ```



### 删除测点

- 请求地址：`GET /api/points/drop/{point_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：

  | 参数名   | 类型 | 必传 | 说明   |
  | -------- | ---- | ---- | ------ |
  | point_id | str  | 是   | 测点ID |

- 说明：已被任一 Model 使用的 Point 不允许删除。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {"ok": true}
  }
  ```
