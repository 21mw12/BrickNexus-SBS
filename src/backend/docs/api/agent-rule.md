# 规则自然语言配置 API

## 一、说明

规则助手只生成草稿，无数据库写入、TTL 写入或控制动作。最后保存仍使用
`POST /api/rules/add` 或 `POST /api/rules/edit/{rule_id}`。接口需要 `rule`
页面权限。

除特别说明外，HTTP 返回使用统一 JSON 包装：

```json
{"success": true, "code": 200, "message": "请求成功", "data": {}}
```

### 模型配置

规则助手使用[系统设置与大语言模型 API](settings.md)中唯一激活的聊天模型，不再读取代码中的连接常量。
vLLM、DeepSeek 使用 `langchain-openai`，Ollama 使用 `langchain-ollama`。缺少活动配置时返回“模型服务未配置或未激活”，缺少依赖时提示安装依赖。
默认请求总时限90秒，最多6次只读工具查询。最终结构化输出最多修正一次。
模型供应商调用统一由 `app/infra/llm` 完成，临时连续对话由
`app/domain/agent/conversation` 管理；规则模块只提供规则提示词、候选工具和结果校验。

### 表单字段

`form`：

| 字段 | 类型与含义 |
|---|---|
| rule_name / description | 文本，分别最多100/1000字符 |
| selector_id | 选择器标识，默认 monitor |
| selector_type | PointIdSelector / SemanticPointSelector |
| point_id | 实例测点ID，与 sensor_id 对应 |
| point_definition_id | 全局测点定义ID（语义选择器） |
| location_id / location_type | 语义监控位置；类型为空或 building / floor / room |
| logic | single / AND / OR / NOT，仅一层逻辑 |
| trigger_count / recovery_count | 触发、恢复次数 |
| trigger_duration / recovery_duration | 触发、恢复持续秒数 |
| repeat_policy | OncePerIncident / NewMatch / Periodic |
| repeat_interval / cooldown / merge_window | 重复间隔、冷却和合并窗口秒数 |

`comparisons` 每项包含 operator、leftType、constant、samples、duration、tolerance、window、timeUnit、rateReference。
operator 对应现有六种比较运算；leftType 支持 PointValue、PreviousDifference、AbsolutePreviousDifference、SampleLagDifference、TimeLagDifference、WindowAverageDifference、WindowRange、RateOfChange。
constant 为右侧常量；samples 为样本数；duration/tolerance/window/timeUnit 单位均为秒；rateReference 为 samples 或 duration。
数字字段允许空字符串表示待填写，不会在保存时默认为0。条件和任务各最多30项。

`actions`：可选 action_id，type 为 LogAction / EmailAction / SensorControlAction；params 只允许对应动作字段。
日志字段 level/content；邮件字段 recipients/subject/content；控制字段 control_id。缺少内容时可留空，最终保存时校验。

### 查询、权限与合并

- 候选查询只读，按位置/名称/单位筛选；权限过滤后每页最多20条，返回 has_more。
- JWT 不发送模型；工具身份绑定当前请求，不允许模型指定用户或角色。
- 权限沿用角色与用户授权的并集；测点要求传感器 R，控制项要求 R 与 O。
- 语义位置必须具备整个当前子树的读取权限；祖先可见不等于整个子树获授权。
- 当前表单及最终结果均检查对象引用；最终新增、编辑、启用也复用监控对象权限校验。
- 模型内部返回 patch，未涉及字段不变，条件/动作列表若改变则整体替换。外部始终返回完整 form_data。
- Redis 只保存用户消息、AI结构化结果和回复，不保存 JWT、API Key、完整资产树或原始工具结果。
- 历史中的对象不能直接复用；每轮候选查询和最终草稿都重新执行当前用户权限检查。
- 不支持分阶段联动、动态房间控制绑定、房间用途过滤或深层条件；通过 reply 解释，不能擅自替换业务语义。
- 不负责规则运行期间权限撤销的即时处理；语义规则以后新增资产的动态授权需另行设计。

### 错误与前端行为

未登录/页面无权限返回401/403；对象或会话越权返回403；模型未配置或草稿结构无效返回400；连续对话 Redis 不可用返回503；超时/供应商失败返回系统错误。
错误不包含模型密钥或供应商请求头。reply 使用纯文本渲染，不执行HTML。
生成期间表单与保存按钮禁用，关闭弹窗取消请求，旧响应不会应用到新弹窗；支持撤销最近一次AI回填和不清空表单的“新对话”。
浏览器取消请求保证不回填旧响应，服务端可能继续只读计算至完成或90秒超时，不会产生配置写入。

## 二、API

### 生成或修改规则草稿

- 请求地址：`POST /api/agent/rule/generate`
- 请求头：

  | 请求头 | 值格式 | 必传 | 说明 |
  |---|---|---|---|
  | Authorization | Bearer {JWT令牌} | 是 | 当前登录用户令牌 |
  | Content-Type | application/json | 是 | JSON 请求体 |

- 请求体：

```json
{
  "conversation_id": null,
  "message": "阈值改成1000，持续十分钟后发送邮件",
  "current_form": {
    "form": {},
    "sensor_id": "",
    "comparisons": [],
    "actions": []
  }
}
```

`conversation_id` 首次请求为空，后续请求传入上次响应的值；`message` 为1～6000字符。
前端每轮发送当前完整表单，且该表单优先于历史对话。空的 `form` 也合法，由服务补齐编辑器默认字段。

- 返回格式：

```json
{
  "success": true,
  "code": 200,
  "message": "请求成功",
  "data": {
    "conversation_id": "57a6d796-3268-4ef6-9d5f-78e87d517edf",
    "conversation_reset": false,
    "reply": "已设置阈值和持续时间，请补充监控对象及邮件收件人。",
    "form_data": {
      "form": {
        "rule_name": "浓度超标告警", "description": "持续超标时发送邮件",
        "selector_id": "monitor", "selector_type": "PointIdSelector",
        "point_id": "", "point_definition_id": "", "location_id": "", "location_type": "",
        "logic": "single", "trigger_count": 1, "trigger_duration": 600,
        "recovery_count": 1, "recovery_duration": 0,
        "repeat_policy": "OncePerIncident", "repeat_interval": 60, "cooldown": 0, "merge_window": 0
      },
      "sensor_id": "",
      "comparisons": [{
        "operator": "GreaterThan", "leftType": "PointValue", "constant": 1000,
        "samples": 1, "duration": 60, "tolerance": 5, "window": 300,
        "timeUnit": 60, "rateReference": "samples"
      }],
      "actions": [{"type": "EmailAction", "params": {
        "recipients": [], "subject": "浓度超标告警", "content": "{{$.point_name}} 当前值为 {{$.value}}"
      }}]
    }
  }
}
```

若传入的会话已经超过30分钟未使用，服务会新建会话并返回
`conversation_reset=true`。每个会话最多保留最近10轮且上下文最多24,000字符，超出后从最早内容开始裁剪。

### 关闭会话

- 请求地址：`DELETE /api/agent/conversations/{conversation_id}`
- 请求头：

  | 请求头 | 值格式 | 必传 | 说明 |
  |---|---|---|---|
  | Authorization | Bearer {JWT令牌} | 是 | 当前登录用户令牌 |

- 路径参数：

  | 参数名 | 类型 | 必传 | 说明 |
  |---|---|---|---|
  | conversation_id | str | 是 | 当前用户的会话 ID |

关闭规则弹窗、保存成功或点击“新对话”时调用。该接口幂等，只允许删除当前用户自己的会话。
会话只保存在 Redis，不提供历史列表或跨登录恢复。

- 请求参数：无请求体。
- 返回格式：`data` 为 `true`，表示会话已经不存在；重复关闭也返回成功。
