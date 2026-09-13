# 规则管理 API

## 一、说明

需要 `rule` 页面权限。规则选择器引用的资产/测点和控制动作会执行实例权限校验。

配置 `PointIdSelector` 时，前端调用 `GET /api/assets/tree` 和 `GET /api/assets/find/{sensor_id}` 取得实例 `point_id`。配置 `SemanticPointSelector` 时，前端复用 `GET /api/points/list` 取得全局 Point ID，并从 `GET /api/assets/tree` 选择建筑、楼层或房间。系统不提供额外的规则测点接口，用户需要对应资产与 Point 页面权限。

### 规则配置 JSON

新增和编辑接口使用以下结构。新增动作不传 `action_id`，由后端生成并在响应中返回；编辑时已有动作必须原样回传其 `action_id`，因此同一规则可配置多个同类型动作并分别追踪。

```json
{
    "rule_name": "高温告警",
    "description": "指定测点高温或突变告警",
    "selector": {
        "selector_id": "monitor",
        "type": "PointIdSelector",
        "point_id": "实例测点ID"
    },
    "condition": {
        "type": "Comparison",
        "operator": "GreaterThan",
        "left": {
            "type": "PointValue",
            "selector_id": "monitor"
        },
        "right": {
            "type": "ConstantValue",
            "value": 40
        }
    },
    "trigger_policy": {
        "trigger_count": 1,
        "trigger_duration_seconds": 0,
        "recovery_count": 1,
        "recovery_duration_seconds": 0,
        "repeat_policy": "OncePerIncident",
        "repeat_interval_seconds": null,
        "cooldown_seconds": 0,
        "merge_window_seconds": 0
    },
    "actions": [
        {
            "type": "LogAction",
            "params": {
                "level": "WARNING",
                "content": "{{$.point_name}} 在 {{$.time}} 的值为 {{$.value}}"
            }
        }
    ]
}
```

语义选择器可以替换上述 `selector`，固定包含位置下全部后代：

```json
{
    "selector_id": "monitor",
    "type": "SemanticPointSelector",
    "point_definition_id": "全局Point ID",
    "location_id": "建筑、楼层或房间ID",
    "location_type": "floor"
}
```

`location_type` 只允许 `building/floor/room`。规则启用时，后端按精确全局 Point ID 推导启用资产链路下的实例测点，并为每个测点建立互相独立的运行引擎；不会生成额外的规则记录或 TTL。零匹配时规则进入 `compile_failed`，资产 RDF 更新后自动重试。

比较节点的 `operator` 支持 `GreaterThan`、`GreaterThanOrEqual`、`LessThan`、`LessThanOrEqual`、`Equal`、`NotEqual`。逻辑节点使用以下形式，`AND/OR` 至少两个子节点，`NOT` 必须且只能有一个子节点：

```json
{
    "type": "Logical",
    "operator": "AND",
    "children": [
        {
            "type": "Comparison",
            "operator": "GreaterThan",
            "left": {"type": "PointValue", "selector_id": "monitor"},
            "right": {"type": "ConstantValue", "value": 40}
        },
        {
            "type": "Comparison",
            "operator": "LessThan",
            "left": {"type": "PointValue", "selector_id": "monitor"},
            "right": {"type": "ConstantValue", "value": 50}
        }
    ]
}
```

历史操作数作为比较节点的 `left` 或 `right` 使用：

| `type`                       | 参数                                                         | 含义                                 |
| ---------------------------- | ------------------------------------------------------------ | ------------------------------------ |
| `PreviousDifference`         | `selector_id`                                                | 当前值减上一条有效值                 |
| `AbsolutePreviousDifference` | `selector_id`                                                | 当前值与上一条有效值差的绝对值       |
| `SampleLagDifference`        | `selector_id`、`samples >= 1`                                | 当前值减前 N 个样本值                |
| `TimeLagDifference`          | `selector_id`、`duration_seconds > 0`、`tolerance_seconds >= 0` | 当前值减指定时间前容差范围内的参考值 |
| `WindowAverageDifference`    | `selector_id`、`window_seconds > 0`                          | 当前值减当前值之前窗口内的均值       |
| `WindowRange`                | `selector_id`、`window_seconds > 0`                          | 包含当前值的窗口最大值减最小值       |
| `RateOfChange`               | `selector_id`、`time_unit_seconds > 0`，并且只配置 `samples` 或 `duration_seconds + tolerance_seconds` 其中一种参考方式 | 按指定时间单位归一化的变化率         |

历史不足时条件结果为 `Unknown`，不推动触发或恢复。乱序或重复测量时间不进入规则历史。`Periodic` 必须配置大于 0 的 `repeat_interval_seconds`；其他重复策略必须传 `null` 或省略该字段。`merge_window_seconds` 只作用于 EmailAction；LogAction 和 SensorControlAction 始终逐事件执行。

LogAction 的 `level` 支持 `DEBUG/INFO/WARNING/ERROR/CRITICAL`，内容支持 `{{$.point_name}}`、`{{$.time}}`、`{{$.value}}` 三个占位符。`{{$.time}}` 使用事件证据中的测量时间，输出格式固定为 `YYYY-MM-DD HH:MM:SS`，不包含毫秒和时区。

EmailAction 的 `recipients` 接受 1～50 个合法邮箱地址；`subject` 是最长 200 字符的固定文本，不解析占位符；`content` 最长 10000 字符并支持上述三个占位符。邮件只发送 UTF-8 纯文本，不支持抄送、密送、附件或 HTML。

```json
{
    "type": "EmailAction",
    "params": {
        "recipients": ["ops@example.com"],
        "subject": "高温告警",
        "content": "{{$.point_name}} 在 {{$.time}} 的值为 {{$.value}}"
    }
}
```

SensorControlAction 只引用已保存的 Control，不允许临时覆盖 Topic、Payload、Header、Params 或 Body。前端通过 `POST /api/control/list?page=1&limit=20` 选择 `control_id`。创建或编辑规则时，当前用户必须拥有该 Control 所绑定终端或传感器的 O 权限。

```json
{
    "type": "SensorControlAction",
    "params": {"control_id": "Control ID"}
}
```

含 EmailAction 的规则启用时只校验 SMTP 配置，不连接服务器。Control 或其绑定资产停用不阻止规则编译，但执行时会失败；Control 已删除则规则再次启用时进入 `compile_failed`。外部邮件和控制只尝试一次，任务先进入 `executing`，进程中断后的遗留任务会标记为失败且不会重放。

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

### 规则分页查询

- 请求地址：POST /api/rules/list?page=1&limit=20

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数（可省略或传 `{}`）：

  | 参数名    | 类型     | 必传 | 说明                                       |
  | --------- | -------- | ---- | ------------------------------------------ |
  | rule_name | str      | 否   | 模糊查询规则名                             |
  | status    | str      | 否   | `paused/running/validating/compile_failed` |
  | create_at | datetime | 否   | 传入格式是年月日，查询这天创建的规则       |

- 列表只返回页面展示所需的规则 ID、规则名称、状态、报错和创建时间；规则配置及文件信息请使用“获取规则详情”接口查询。

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
                  "rule_id": "规则UUID",
                  "rule_name": "高温告警",
                  "status": "paused",
                  "error": null,
                  "created_at": "2026-08-18T09:00:00Z"
              }
          ]
      }
  }
  ```



### 获取规则详情

- 请求地址：GET /api/rules/find/{rule_id}

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 说明：后端重新读取 TTL 返回 `config`。`PointIdSelector` 会在顶层 `sensor_id` 返回实例测点所属传感器；`SemanticPointSelector` 的 `sensor_id` 为 `null`，且不返回运行时推导出的测点列表。`sensor_id` 不写入 `config.selector`，前端仍可将 `config` 原样提交给编辑接口。编译失败规则的文件无法解析时，`config` 可能省略。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "rule_id": "规则UUID",
          "rule_name": "高温告警",
          "rule_file_name": "规则UUID.ttl",
          "status": "paused",
          "error": null,
          "created_at": "2026-08-18T09:00:00Z",
          "sensor_id": "传感器ID",
          "config": {
              "rule_name": "高温告警",
              "description": "指定测点高温告警",
              "selector": {"selector_id": "monitor", "type": "PointIdSelector", "point_id": "实例测点ID"},
              "condition": {
                  "type": "Comparison",
                  "operator": "GreaterThan",
                  "left": {"type": "PointValue", "selector_id": "monitor", "value": null, "samples": null, "duration_seconds": null, "tolerance_seconds": null, "window_seconds": null, "time_unit_seconds": null},
                  "right": {"type": "ConstantValue", "selector_id": null, "value": 40.0, "samples": null, "duration_seconds": null, "tolerance_seconds": null, "window_seconds": null, "time_unit_seconds": null},
                  "children": null
              },
              "trigger_policy": {"trigger_count": 1, "trigger_duration_seconds": 0.0, "recovery_count": 1, "recovery_duration_seconds": 0.0, "repeat_policy": "OncePerIncident", "repeat_interval_seconds": null, "cooldown_seconds": 0.0, "merge_window_seconds": 0.0},
              "actions": [{"action_id": "动作UUID", "type": "LogAction", "params": {"level": "WARNING", "content": "{{$.point_name}}={{$.value}}"}}]
          }
      }
  }
  ```



### 获取规则 TTL 内容

- 请求地址：GET /api/rules/ttl/{rule_id}

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：路径参数 `rule_id`。

- 说明：返回用于前端三元组可视化的 Turtle 文本内容，不触发文件下载，也不允许前端直接编辑。结构化编辑仍使用“获取规则详情”返回的 `config`。EmailAction 会生成重复的 `sb:recipient`、`sb:subject`、`sb:content` 三元组；SensorControlAction 会生成 `sb:controlId` 三元组。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "rule_id": "规则UUID",
          "ttl": "@prefix sb: <http://www.zju.edu.cn/ontology#> .\n..."
      }
  }
  ```



### 获取规则配置选项

- 请求地址：GET /api/rules/options

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：无。

- 说明：返回规则编辑器当前支持的静态能力，不返回资产或测点数据。`asset_source` 告知前端复用资产接口取得实例测点。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "schema_version": "1.1",
          "rule_fields": [
              {"name": "rule_name", "label": "规则名称", "type": "text", "required": true, "max_length": 100},
              {"name": "description", "label": "规则描述", "type": "textarea", "required": false, "default": "", "max_length": 1000}
          ],
          "selector_types": [{
              "value": "PointIdSelector",
              "label": "指定实例测点",
              "fields": [
                  {"name": "selector_id", "label": "选择器标识", "type": "text", "required": true, "default": "monitor", "max_length": 100},
                  {"name": "point_id", "label": "监控测点", "type": "asset_sensor_point", "required": true}
              ],
              "asset_source": {
                  "tree_endpoint": "GET /api/assets/tree",
                  "detail_endpoint": "GET /api/assets/find/{asset_id}",
                  "items_field": "sensor_points",
                  "value_field": "point_id"
              }
          }, {
              "value": "SemanticPointSelector",
              "label": "按位置和测点定义匹配",
              "fields": [
                  {"name": "selector_id", "label": "选择器标识", "type": "text", "required": true, "default": "monitor", "max_length": 100},
                  {"name": "point_definition_id", "label": "全局测点定义", "type": "point_definition", "required": true},
                  {"name": "location_id", "label": "所在位置", "type": "asset_location", "required": true},
                  {"name": "location_type", "label": "位置类型", "type": "select", "required": true,
                   "options": [
                       {"value": "building", "label": "建筑"},
                       {"value": "floor", "label": "楼层"},
                       {"value": "room", "label": "房间"}
                   ]}
              ],
              "point_definition_source": {
                  "list_endpoint": "GET /api/points/list?page={page}&limit={limit}",
                  "items_field": "items",
                  "value_field": "point_id",
                  "label_field": "point_name"
              },
              "location_source": {
                  "tree_endpoint": "GET /api/assets/tree",
                  "value_field": "asset_id",
                  "allowed_types": ["building", "floor", "room"],
                  "include_descendants": true
              }
          }],
          "condition_node_types": [
              {"value": "Comparison", "label": "比较条件"},
              {"value": "Logical", "label": "逻辑条件"}
          ],
          "comparison_operators": [
              {"value": "GreaterThan", "label": "大于", "symbol": ">"},
              {"value": "GreaterThanOrEqual", "label": "大于等于", "symbol": ">="},
              {"value": "LessThan", "label": "小于", "symbol": "<"},
              {"value": "LessThanOrEqual", "label": "小于等于", "symbol": "<="},
              {"value": "Equal", "label": "等于", "symbol": "=="},
              {"value": "NotEqual", "label": "不等于", "symbol": "!="}
          ],
          "logical_operators": [
              {"value": "AND", "label": "并且", "min_children": 2},
              {"value": "OR", "label": "或者", "min_children": 2},
              {"value": "NOT", "label": "取反", "min_children": 1, "max_children": 1}
          ],
          "operand_types": [
              {"value": "PointValue", "label": "当前测点值", "fields": [{"name": "selector_id", "type": "selector_ref", "required": true}]},
              {"value": "ConstantValue", "label": "常量", "fields": [{"name": "value", "type": "number", "required": true}]},
              {"value": "PreviousDifference", "label": "与上一样本的差值"},
              {"value": "AbsolutePreviousDifference", "label": "与上一样本的绝对差值"},
              {"value": "SampleLagDifference", "label": "样本间隔差值"},
              {"value": "TimeLagDifference", "label": "时间间隔差值"},
              {"value": "WindowAverageDifference", "label": "窗口均值差值"},
              {"value": "WindowRange", "label": "窗口极差"},
              {"value": "RateOfChange", "label": "变化率"}
          ],
          "trigger_policy": {"fields": [
              {"name": "trigger_count", "type": "integer", "default": 1, "minimum": 1},
              {"name": "trigger_duration_seconds", "type": "number", "default": 0, "minimum": 0},
              {"name": "recovery_count", "type": "integer", "default": 1, "minimum": 1},
              {"name": "recovery_duration_seconds", "type": "number", "default": 0, "minimum": 0},
              {"name": "repeat_policy", "type": "select", "default": "OncePerIncident"},
              {"name": "repeat_interval_seconds", "type": "number", "required_when": {"repeat_policy": "Periodic"}},
              {"name": "cooldown_seconds", "type": "number", "default": 0, "minimum": 0},
              {"name": "merge_window_seconds", "type": "number", "default": 0, "minimum": 0}
          ]},
          "repeat_policies": [
              {"value": "OncePerIncident", "label": "每次异常只触发一次"},
              {"value": "NewMatch", "label": "出现新匹配时触发"},
              {"value": "Periodic", "label": "异常期间周期触发", "required_fields": ["repeat_interval_seconds"]}
          ],
          "action_types": [{
              "value": "LogAction",
              "label": "记录日志",
              "generated_fields": ["action_id"],
              "fields": [
                  {"name": "level", "type": "select", "required": true, "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
                  {"name": "content", "type": "textarea", "required": true, "max_length": 10000}
              ],
              "placeholders": [
                  {"value": "{{$.point_name}}", "label": "测点名称"},
                  {"value": "{{$.time}}", "label": "测量时间（YYYY-MM-DD HH:MM:SS）"},
                  {"value": "{{$.value}}", "label": "测点值"}
              ]
          }, {
              "value": "EmailAction",
              "label": "发送邮件",
              "generated_fields": ["action_id"],
              "fields": [
                  {"name": "recipients", "type": "email_list", "required": true, "min_items": 1, "max_items": 50},
                  {"name": "subject", "type": "text", "required": true, "max_length": 200, "supports_placeholders": false},
                  {"name": "content", "type": "textarea", "required": true, "max_length": 10000}
              ],
              "placeholders": [
                  {"value": "{{$.point_name}}", "label": "测点名称"},
                  {"value": "{{$.time}}", "label": "测量时间（YYYY-MM-DD HH:MM:SS）"},
                  {"value": "{{$.value}}", "label": "测点值"}
              ]
          }, {
              "value": "SensorControlAction",
              "label": "控制传感器",
              "generated_fields": ["action_id"],
              "fields": [
                  {"name": "control_id", "type": "control_ref", "required": true, "max_length": 100}
              ],
              "control_source": {
                  "list_endpoint": "POST /api/control/list?page={page}&limit={limit}",
                  "items_field": "items",
                  "value_field": "control_id",
                  "label_field": "name"
              }
          }]
      }
  }
  ```



### 新增规则

- 请求地址：`POST /api/rules/add`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |
  | Content-Type  | application/json |

- 参数：请求体为**“规则配置 JSON”**；新增动作可省略 `action_id`。

- 说明：单测点选择器校验实例 Point 和启用资产链路；语义选择器校验全局 Point、位置 ID 和位置类型，但创建时允许暂时零匹配。随后生成 `resources/rdf/rule/<rule_id>.ttl`，规则初始状态为 `paused`，并在同一 SQL 事务写入当前用户昵称快照的操作日志。

- 返回格式：与“获取规则详情”相同，其中包含后端生成的 `rule_id` 和 `action_id`。



### 编辑规则

- 请求地址：`POST /api/rules/edit/{rule_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |
  | Content-Type  | application/json |

- 参数：路径参数 `rule_id`；请求体为完整规则配置。已有动作应回传 `action_id`，新动作可省略。

- 说明：仅允许编辑非 `running` 规则。校验或落库失败时保留旧 TTL 和旧配置；成功后状态为 `paused`。

- 返回格式：与“获取规则详情”相同。



### 启动或暂停规则

- 请求地址：`POST /api/rules/toggle/{rule_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 说明：`running` 切换为 `paused`；其他状态重新读取 TTL，并校验 Point、资产链路、EmailAction 的 SMTP 配置和 SensorControlAction 引用的 Control 后切换为 `running`。编译失败时状态为 `compile_failed`，`error` 保存原因。Control 或其绑定资产的停用状态只在动作执行时校验。

- 返回格式：与“获取规则详情”相同。



### 删除规则

- 请求地址：`GET /api/rules/drop/{rule_id}`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 说明：仅允许删除非 `running` 规则。删除规则会级联删除对应事件和任务，但不会删除业务日志。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {"ok": true}
  }
  ```



### 规则事件分页查询

- 请求地址：`POST /api/rules/events?page=1&limit=20`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 请求体（可省略或传 `{}`）：

  | 参数名     | 类型     | 必传 | 说明                               |
  | ---------- | -------- | ---- | ---------------------------------- |
  | rule_id    | str      | 否   | 根据来源规则 ID 查询               |
  | event_type | str      | 否   | `triggered/recovered`              |
  | event_time | datetime | 否   | 输入年月日格式，查询当天的规则事件 |

- 列表只返回事件 ID、来源规则 ID、触发状态、触发证据和事件时间。需要规则名称或配置时，使用来源规则 ID 调用“获取规则详情”接口。

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
                  "event_id": "事件UUID",
                  "rule_id": "规则UUID",
                  "event_type": "triggered",
                  "evidence": {
                      "point_id": "实例测点ID",
                      "point_name": "温度",
                      "unit": "℃",
                      "sensor_id": "传感器ID",
                      "point_definition_id": "全局Point ID",
                      "asset_path": [{"asset_id": "传感器ID", "asset_type": "sensor", "name": "温度传感器"}],
                      "value": 42.0,
                      "measurement_time": "2026-08-18T09:30:00Z",
                      "condition": {"type": "Comparison", "operator": "GreaterThan", "result": true},
                      "reason": "initial",
                      "rule_fingerprint": "TTL的SHA-256"
                  },
                  "event_time": "2026-08-18T09:30:00Z"
              }
          ]
      }
  }
  ```



### 行动任务分页查询

- 请求地址：`POST /api/rules/tasks?page=1&limit=20`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- URL 查询参数：仅 `page`、`limit`，默认 1、20。

- JSON 请求体（可省略或传 `{}`）：

  | 参数名         | 类型     | 必传 | 说明                                     |
  | -------------- | -------- | ---- | ---------------------------------------- |
  | rule_id        | str      | 否   | 根据来源规则 ID 查询                     |
  | event_id       | str      | 否   | 根据来源事件 ID 查询                     |
  | action_type    | str      | 否   | `LogAction/EmailAction/SensorControlAction` |
  | status         | str      | 否   | `pending/executing/succeeded/failed`     |
  | create_time    | datetime | 否   | 输入年月日格式，查询当天创建的行动任务   |
  | completed_time | datetime | 否   | 输入年月日格式，查询当天完成的的行动任务 |

- 列表只返回任务 ID、来源规则 ID、行动类型、是否已经执行、当前状态、报错、创建时间和完成时间；不返回来源事件 ID、动作定义 ID 和动作参数。需要规则名称或配置时，使用来源规则 ID 调用“获取规则详情”接口。

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
                  "task_id": "任务UUID",
                  "rule_id": "规则UUID",
                  "action_type": "LogAction",
                  "is_executed": true,
                  "status": "succeeded",
                  "error": null,
                  "created_at": "2026-08-18T09:30:00Z",
                  "completed_at": "2026-08-18T09:30:00.050000Z"
              }
          ]
      }
  }
  ```
