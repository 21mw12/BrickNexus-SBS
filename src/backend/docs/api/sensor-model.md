# 传感器型号 API

## 一、说明

传感器型号维护型号基础信息及其测点定义映射。查询需要 `asset`、`asset:model`、
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

### 查询所有传感器型号

- 请求地址：`GET /api/models/list?page=1&limit=20`

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
          "total": 1,
          "items": [
              {
                  "model_id": "e051b585-039f-40a2-95a2-1a07930e3001",
                  "sensor_type": "温湿度",
                  "model_name": "DHT22",
                  "remark": "数字温湿度传感器",
                  "points": [
                      {
                          "point_id": "8f156708-1fe2-4598-9d4e-7db5c41dd001",
                          "point_name": "温度",
                          "point_unit": "℃",
                          "point_description": "设备周围环境温度"
                      }
                  ]
              }
          ]
      }
  }
  ```



### 根据型号ID获取详细信息

- 请求地址：`GET /api/models/find/{model_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：

  | 参数名   | 类型 | 必传 | 说明   |
  | -------- | ---- | ---- | ------ |
  | model_id | str  | 是   | 型号ID |

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "model_id": "e051b585-039f-40a2-95a2-1a07930e3001",
          "sensor_type": "温湿度",
          "model_name": "DHT22",
          "remark": "数字温湿度传感器",
          "points": [
              {
                  "point_id": "8f156708-1fe2-4598-9d4e-7db5c41dd001",
                  "point_name": "温度",
                  "point_unit": "℃",
                  "point_description": "设备周围环境温度"
              }
          ]
      }
  }
  ```



### 新增传感器型号

- 请求地址：`POST /api/models/add`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：

  | 参数名      | 类型                   | 必传 | 说明                     |
  | ----------- | ---------------------- | ---- | ------------------------ |
  | sensor_type | str / null             | 否   | 传感器类型，最长 50 字符 |
  | model_name  | str / null             | 否   | 传感器型号，最长 50 字符 |
  | remark      | str / null             | 否   | 备注，最长 100 字符      |
  | points      | List[ModelPointItem]    | 否   | 型号绑定的全局测点列表   |

  **ModelPointItem**：

  | 参数名   | 类型 | 必传 | 说明                |
  | -------- | ---- | ---- | ------------------- |
  | point_id | str  | 是   | 已存在的全局 Point ID |

- 说明：
  - `model_id` 由系统生成 UUID。
  - `points` 只能选择已有 Point，重复或不存在的 `point_id` 会使整个请求失败。
  - Model 创建后不允许新增、删除或替换测点绑定。

- 请求示例：

  ```json
  {
      "sensor_type": "温湿度",
      "model_name": "DHT22",
      "remark": "数字温湿度传感器",
      "points": [
          {"point_id": "8f156708-1fe2-4598-9d4e-7db5c41dd001"},
          {"point_id": "8f156708-1fe2-4598-9d4e-7db5c41dd002"}
      ]
  }
  ```

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "model_id": "e051b585-039f-40a2-95a2-1a07930e3001",
          "sensor_type": "温湿度",
          "model_name": "DHT22",
          "remark": "数字温湿度传感器",
          "points": [
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



### 修改传感器型号

- 请求地址：`POST /api/models/edit/{model_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：

  | 参数名      | 类型       | 必传 | 说明                               |
  | ----------- | ---------- | ---- | ---------------------------------- |
  | model_id    | str        | 是   | URL 路径中的型号ID                 |
  | sensor_type | str / null | 否   | 传感器类型，最长 50 字符           |
  | model_name  | str / null | 否   | 传感器型号，最长 50 字符           |
  | remark      | str / null | 否   | 备注，最长 100 字符                |

- 说明：只允许修改型号基本信息，不接受 `points` 字段。

- 请求示例：

  ```json
  {
      "sensor_type": "温湿度传感器",
      "model_name": "DHT22",
      "remark": "更新后的备注"
  }
  ```

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "model_id": "e051b585-039f-40a2-95a2-1a07930e3001",
          "sensor_type": "温湿度传感器",
          "model_name": "DHT22",
          "remark": "更新后的备注",
          "points": [
              {
                  "point_id": "8f156708-1fe2-4598-9d4e-7db5c41dd001",
                  "point_name": "温度",
                  "point_unit": "℃",
                  "point_description": "设备周围环境温度"
              }
          ]
      }
  }
  ```



### 删除传感器型号

- 请求地址：`GET /api/models/drop/{model_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：

  | 参数名   | 类型 | 必传 | 说明   |
  | -------- | ---- | ---- | ------ |
  | model_id | str  | 是   | 型号ID |

- 说明：已被 Sensor 或 SensorPoint 引用的 Model 不允许删除。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {"ok": true}
  }
  ```
