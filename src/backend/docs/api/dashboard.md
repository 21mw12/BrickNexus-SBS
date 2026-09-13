# 看板 API

## 一、说明

需要有效登录令牌，不额外要求 `dashboard` 页面权限。页面说明按当前用户的页面权限过滤，统计数据按资产可见范围计算。

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

### 获取看板概览

- 请求地址：`GET /api/dashboard/overview`

- 请求头：

  | 请求头 | 值格式 | 必传 | 说明 |
  | ------ | ------ | ---- | ---- |
  | Authorization | Bearer {JWT令牌} | 是 | 当前登录用户令牌 |

- 请求参数：无

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "page": [
              {
                  "key": "asset:tree",
                  "item": "资产树",
                  "description": "按照建筑层级浏览当前用户有权查看的资产结构。",
                  "usage": "通过树形结构逐级展开建筑、楼层、房间、终端和传感器。"
              },
              {
                  "key": "data:realtime",
                  "item": "实时数据",
                  "description": "实时查看授权终端及其传感器测点的最新状态与测量值。",
                  "usage": "选择有权查看的终端并订阅实时数据更新。"
              }
          ],
          "statistics": {
              "user_count": 12,
              "request_count": 6,
              "control_count": 4,
              "rule_count": 8,
              "building": {
                  "enabled_total": 2
              },
              "floor": {
                  "enabled_total": 8
              },
              "room": {
                  "enabled_total": 36
              },
              "terminal": {
                  "enabled_total": 10,
                  "online_count": 9
              },
              "sensor": {
                  "enabled_total": 42,
                  "online_count": 39
              }
          }
      }
  }
  ```

- 字段说明：

  | 字段 | 类型 | 说明 |
  | ---- | ---- | ---- |
  | `page` | array | 当前用户拥有权限的页面说明 |
  | `key` | string | 固定页面编码，例如 `asset:tree` |
  | `item` | string | 页面中文名称 |
  | `description` | string | 页面的功能说明 |
  | `usage` | string | 页面的使用说明 |
  | `statistics` | object | 不受页面权限影响的统计结果 |
  | `enabled_total` | int | 当前类型中已启用且用户可见的资产数量 |
  | `online_count` | int | 已启用、用户可见且当前在线的终端或传感器数量 |
