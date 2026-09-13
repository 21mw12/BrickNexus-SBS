# 资产 API

## 一、说明

资产包括 Building、Floor、Room、Terminal 和 Sensor，构成一棵层级树。查询结果按当前用户可见资产过滤；写操作需要对应资产权限。

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

### 获取所有资产（树结构）

- 请求地址：`GET /api/assets/tree`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：无

- 说明：按用户可见权限过滤，无 R 权的分支不展示

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": [
          {
              "asset_id": "c5e7f17f-9d18-4f08-846a-153051e97f7f",
              "name": "测试楼宇A",
              "sub_assets": [
                  {
                      "asset_id": "9c9fc538-67f2-4578-a80a-f1f5fad56e66",
                      "name": "1层",
                      "sub_assets": [
                          {
                              "asset_id": "xxx",
                              "name": "网关-01",
                              "is_online": true,
                              "sub_assets": [
                                  {
                                      "asset_id": "yyy",
                                      "name": "温度传感器-01",
                                      "is_online": false,
                                      "sub_assets": []
                                  }
                              ]
                          }
                      ]
                  }
              ]
          }
      ]
  }
  ```



### 资产分页查询（支持模糊查询）

- 请求地址：`POST /api/assets/form?page=XXX&limit=XXX`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：

  | 参数名     | 类型 | 必传 | 说明                                      |
  | ---------- | ---- | ---- | ----------------------------------------- |
  | name       | str  | 否   | 资产名，模糊搜索                          |
  | is_use     | bool | 否   | 是否在用                                  |
  | is_online  | bool | 否   | 是否在线（仅 terminal / sensor 类型有效，需同时传 asset_type） |
  | asset_type | str  | 否   | 资产类型：building / floor / room / terminal / sensor |

- 说明：SQL 层按用户可见资产 ID 过滤，确保分页正确。`is_online` 仅对 terminal 和 sensor 类型返回

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "total": 16,
          "items": [
              {
                  "id": "cf140a67-2381-49d1-a07f-c0cc8cd371a4",
                  "name": "温度传感器-02",
                  "type": "sensor",
                  "floor_count": 0,
                  "room_count": 0,
                  "terminal_count": 0,
                  "sensor_count": 0,
                  "is_use": true,
                  "is_online": false
              },
              {
                  "id": "aaa-bbb-ccc",
                  "name": "测试楼宇",
                  "type": "building",
                  "floor_count": 3,
                  "room_count": 10,
                  "terminal_count": 5,
                  "sensor_count": 20,
                  "is_use": true
              }
          ]
      }
  }
  ```



### 根据id获取资产详细信息

- 请求地址：`GET /api/assets/find/{asset_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：无

- 说明：需要对该资产有 R（查看）权限

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "asset_id": "8e0140cd-77e9-45af-b113-5505f67d4f0f",
          "asset_id_parent": "f003f521-6f98-4191-937c-5fce5e68a06d",
          "asset_type": "sensor",
          "name": "测试传感器",
          "floor_count": 0,
          "room_count": 0,
          "terminal_count": 0,
          "sensor_count": 0,
          "is_use": true,
          "is_online": false,
          "asset_parent_name": "网关-02",
          "sensor_type": "温湿度传感器",
          "model_name": "DHT-11",
          "last_receive_time": "2026-07-28T10:30:00+08:00",
          "points": [
              {"point_id": "全局测点UUID-1", "point_name": "温度", "point_unit": "°C", "point_description": "设备周围环境温度"},
              {"point_id": "全局测点UUID-2", "point_name": "湿度", "point_unit": "%", "point_description": "设备周围环境湿度"}
          ],
          "sensor_points": [
              {
                  "point_id": "实例测点UUID",
                  "source_model_id": "型号UUID",
                  "source_point_id": "全局测点UUID-1",
                  "point_name": "温度",
                  "point_unit": "°C",
                  "point_description": "设备周围环境温度",
                  "json_path": "$.data.temperature"
              }
          ]
      }
  }
  ```



### 新增资产

- 请求地址：`POST /api/assets/add`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数（按 asset_type 区分）：

  **通用字段**：

  | 参数名          | 类型 | 必传 | 说明                                      |
  | --------------- | ---- | ---- | ----------------------------------------- |
  | asset_type      | str  | 是   | 资产类型：building / floor / room / terminal / sensor |
  | name            | str  | 是   | 资产名                                    |
  | is_use          | bool | 是   | 是否在用                                  |
  | asset_id_parent | str  | 否   | 父资产ID（building 不需要，其他类型必传） |

  **building**：

  | 参数名  | 类型 | 必传 | 说明     |
  | ------- | ---- | ---- | -------- |
  | number  | str  | 否   | 楼宇编号 |
  | address | str  | 否   | 地址     |

  **floor**：

  | 参数名 | 类型 | 必传 | 说明   |
  | ------ | ---- | ---- | ------ |
  | level  | str  | 否   | 楼层号 |

  **room**：

  | 参数名       | 类型 | 必传 | 说明     |
  | ------------ | ---- | ---- | -------- |
  | number       | str  | 否   | 房号     |
  | room_purpose | str  | 否   | 用途     |
  | max_current  | str  | 否   | 最大电流 |
  | manager_name | str  | 否   | 管理员   |

  **terminal**：

  | 参数名             | 类型 | 必传 | 说明       |
  | ------------------ | ---- | ---- | ---------- |
  | request_id         | str  | 否   | 数据请求ID |
  | number             | str  | 否   | 编号       |
  | model              | str  | 否   | 型号       |
  | location           | str  | 否   | 安装位置   |
  | iot_number         | str  | 否   | 物联网卡号 |
  | iot_activate_human | str  | 否   | 激活人     |

  **sensor**：

  | 参数名   | 类型 | 必传 | 说明         |
  | -------- | ---- | ---- | ------------ |
  | model_id | str  | 否   | 传感器型号ID |

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "asset_id": "10ef7c09-2e19-4a82-aca4-1f7f46ddcdd5",
          "asset_id_parent": null,
          "asset_type": "building",
          "name": "测试楼",
          "floor_count": 0,
          "room_count": 0,
          "terminal_count": 0,
          "sensor_count": 0,
          "is_use": true,
          "number": "B1",
          "address": null
      }
  }
  ```



### 修改资产

- 请求地址：`POST /api/assets/edit/{asset_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数（所有字段均可选，不传则不修改）：

  **通用字段**：

  | 参数名     | 类型 | 必传 | 说明                                      |
  | ---------- | ---- | ---- | ----------------------------------------- |
  | asset_type | str  | 是   | 资产类型（必传，用于区分类型）            |
  | name       | str  | 否   | 资产名                                    |
  | is_use     | bool | 否   | 是否在用                                  |
  | is_use_all | bool | 否   | 启用时是否同时启用所有子资产，默认 false   |

  **building**：`number`（str，否），`address`（str，否）

  **floor**：`level`（str，否）

  **room**：`number`（str，否），`room_purpose`（str，否），`max_current`（str，否），`manager_name`（str，否）

  **terminal**：`request_id`（str，否），`number`（str，否），`model`（str，否），`location`（str，否），`iot_number`（str，否），`iot_activate_human`（str，否）

  **sensor**：无（传感器型号创建后不可修改，其他通用字段同其他类型）

- 返回格式：同查询单个资产



### 删除资产

- 请求地址：`GET /api/assets/drop/{asset_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：无

- 说明：
  - 仅需根节点 D（删除）权限，子节点级联删除无需额外检查
  - 级联清理所有子资产的 role_asset 和 user_asset 权限记录

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": { "ok": true }
  }
  ```



### 导出资产

- 请求地址：`GET /api/assets/excel`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：无

- 说明：导出当前用户可见的全部资产

- 返回格式：Excel 文件流下载
