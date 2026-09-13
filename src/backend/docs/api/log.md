# 系统日志 API

## 一、说明

日志接口只提供查询，不提供新增、修改或删除。需要 `logs` 页面权限。

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

### 日志分页查询

- 请求地址：`POST /api/logs/list?page=1&limit=20`
- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |
- URL 查询参数：仅 `page`、`limit`，默认 1、20。
- JSON 请求体（可省略或传 `{}`）：

  | 参数名 | 类型 | 必传 | 说明 |
  | --- | --- | --- | --- |
  | type | str | 否 | `rule_action/rule_operation` |
  | level | str | 否 | `DEBUG/INFO/WARNING/ERROR/CRITICAL` |
  | operator | str | 否 | 操作人昵称快照或 `SYSTEM`，精确匹配 |
  | time | datetime | 否 | 格式为年月日，查询这天的日志        |

- 说明：结果按 `time DESC` 排列。`rule_operation` 为规则管理操作，固定 `INFO`；`rule_action` 为自动日志动作，操作人固定 `SYSTEM`。
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
                  "id": "日志UUID",
                  "type": "rule_action",
                  "level": "WARNING",
                  "operator": "SYSTEM",
                  "content": "温度 在 2026-08-18T09:30:00Z 的值为 42.0",
                  "time": "2026-08-18T09:30:00.050000Z"
              }
          ]
      }
  }
  ```



### 获取日志查询可选项

- 请求地址：`GET /api/logs/options`
- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 说明：`value` 是日志分页查询请求体使用的英文值，`label` 是前端展示的中文名称。操作人和日期不属于固定枚举，不在本接口中返回。
- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "types": [
              {"value": "rule_action", "label": "规则动作日志"},
              {"value": "rule_operation", "label": "规则操作日志"}
          ],
          "levels": [
              {"value": "DEBUG", "label": "调试"},
              {"value": "INFO", "label": "信息"},
              {"value": "WARNING", "label": "警告"},
              {"value": "ERROR", "label": "错误"},
              {"value": "CRITICAL", "label": "严重"}
          ]
      }
  }
  ```
