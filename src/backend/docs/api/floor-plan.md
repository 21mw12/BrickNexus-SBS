# 楼层平面图 API

## 一、说明

需要 `asset`、`asset:table` 或 `asset:tree` 页面权限，并校验目标楼层的资产读写权限。坐标均基于原图像素。

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

### 上传或替换楼层平面图

- 请求地址：`POST /api/floor-plans/{floor_id}/image`

- 请求头：

  | 请求头        | 值格式              |
  | ------------- | ------------------- |
  | Authorization | Bearer {JWT令牌}    |
  | Content-Type  | multipart/form-data |

- 路径参数：

  | 参数名   | 类型 | 必传 | 说明       |
  | -------- | ---- | ---- | ---------- |
  | floor_id | str  | 是   | 楼层资产ID |

- 表单参数：

  | 参数名 | 类型 | 必传 | 说明                             |
  | ------ | ---- | ---- | -------------------------------- |
  | image  | file | 是   | PNG、JPEG 或 WebP 图片，最大10MB |

- 说明：

  - 图片保存到服务端 `resources/floorPlan` 目录，数据库只记录系统生成的图片名称
  - 图片类型和原始宽高由服务端读取真实图片内容获得，不使用客户端文件名判断
  - 一个楼层只能保存一张平面图
  - 替换已有平面图后，旧图片会被删除，该楼层原有的全部房间标记也会被清空

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "floor_id": "floor-001",
          "image_name": "550e8400e29b41d4a716446655440000.png",
          "image_width": 1920,
          "image_height": 1080,
          "image_type": "image/png",
          "image_url": "/floor-plans/floor-001/image",
          "regions": []
      }
  }
  ```



### 查询楼层平面图及房间标记

- 请求地址：`GET /api/floor-plans/{floor_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 路径参数：

  | 参数名   | 类型 | 必传 | 说明       |
  | -------- | ---- | ---- | ---------- |
  | floor_id | str  | 是   | 楼层资产ID |

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "floor_id": "floor-001",
          "image_name": "550e8400e29b41d4a716446655440000.png",
          "image_width": 1920,
          "image_height": 1080,
          "image_type": "image/png",
          "image_url": "/floor-plans/floor-001/image",
          "regions": [
              {
                  "room_id": "room-001",
                  "room_name": "101会议室",
                  "x": 120,
                  "y": 80,
                  "width": 360,
                  "height": 240
              }
          ]
      }
  }
  ```



### 获取楼层平面图图片

- 请求地址：`GET /api/floor-plans/{floor_id}/image`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 路径参数：

  | 参数名   | 类型 | 必传 | 说明       |
  | -------- | ---- | ---- | ---------- |
  | floor_id | str  | 是   | 楼层资产ID |

- 返回格式：图片文件流，`Content-Type` 为数据库中记录的 `image/png`、`image/jpeg` 或 `image/webp`



### 批量保存楼层房间标记

- 请求地址：`PUT /api/floor-plans/{floor_id}/regions`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |
  | Content-Type  | application/json |

- 路径参数：

  | 参数名   | 类型 | 必传 | 说明       |
  | -------- | ---- | ---- | ---------- |
  | floor_id | str  | 是   | 楼层资产ID |

- 参数：

  | 参数名  | 类型                  | 必传 | 说明                       |
  | ------- | --------------------- | ---- | -------------------------- |
  | regions | List[FloorRoomRegion] | 是   | 当前楼层的完整房间标记列表 |

  **FloorRoomRegion**：

  | 参数名  | 类型 | 必传 | 说明                                     |
  | ------- | ---- | ---- | ---------------------------------------- |
  | room_id | str  | 是   | 当前楼层下的房间资产ID                   |
  | x       | int  | 是   | 相对于原图的左上X像素坐标，必须大于等于0 |
  | y       | int  | 是   | 相对于原图的左上Y像素坐标，必须大于等于0 |
  | width   | int  | 是   | 矩形宽度，必须大于0                      |
  | height  | int  | 是   | 矩形高度，必须大于0                      |

- 请求示例：

  ```json
  {
      "regions": [
          {
              "room_id": "room-001",
              "x": 120,
              "y": 80,
              "width": 360,
              "height": 240
          },
          {
              "room_id": "room-002",
              "x": 520,
              "y": 80,
              "width": 300,
              "height": 240
          }
      ]
  }
  ```

- 说明：

  - 保存房间标记前，该楼层必须已经上传平面图
  - `regions` 使用批量覆盖语义，本次未提交的旧标记会被删除
  - 传入 `{"regions": []}` 表示清空该楼层全部房间标记
  - 同一个请求中 `room_id` 不允许重复
  - Room 必须直接属于路径参数指定的 Floor
  - 服务端会校验 `x + width <= image_width` 和 `y + height <= image_height`

- 返回格式：同“查询楼层平面图及房间标记”



### 删除楼层平面图

- 请求地址：`DELETE /api/floor-plans/{floor_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 路径参数：

  | 参数名   | 类型 | 必传 | 说明       |
  | -------- | ---- | ---- | ---------- |
  | floor_id | str  | 是   | 楼层资产ID |

- 说明：删除平面图数据库记录、该楼层全部房间标记以及 `resources/floorPlan` 下的实际图片

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": { "ok": true }
  }
  ```
