# 智能分析 AI 解读 API

## 一、说明

智能分析 Agent 只解释已经完成的数值分析结果，不重新扫描历史数据、不运行算法、不修改测量数据，
也不执行设备控制。它使用系统设置中唯一激活的聊天模型，并复用公共 Agent 会话服务保存30分钟短会话。

执行 `POST /api/analytics/run` 后，服务端会把精简分析摘要临时写入 Redis，并在
`ai_context.analysis_id` 中返回引用。摘要按用户隔离，不包含 JWT、模型密钥、完整原始时序数组或
PCA坐标。Redis不可用不会导致数值分析失败，只会令 `ai_context.available=false`。

接口需要 `data` 或 `data:analysis` 页面权限。每次生成和追问都会重新校验当前用户对摘要内全部测点
所属 Sensor 的 R 权限；权限在分析后被撤销时不能继续解读。

## 二、提示词和输出约束

系统提示词由公共安全规则、异常/聚类/预测类型规则和当前算法注意事项组合生成。AI必须区分直接结果、
合理推断和待验证假设，不得把相关性描述为因果关系，不得把异常风险分解释为概率。质量警告会作为
解释上下文的一部分，建议只限人工核查方向。

首次解读返回结构化报告，包括总体概述、关键发现、可以推导的内容、注意事项、建议核查和分析局限。
关键发现与推断包含证据和 `high / medium / low` 置信度。后续追问返回纯文本回答，前端不得使用未经
净化的 HTML 渲染。

## 三、生成解读或追问

- 请求地址：`POST /api/agent/analysis/respond`
- 请求头：`Authorization: Bearer {JWT令牌}`、`Content-Type: application/json`
- 模型请求超时：120秒

首次生成：

```json
{
  "analysis_id": "57a6d796-3268-4ef6-9d5f-78e87d517edf",
  "conversation_id": null,
  "message": null
}
```

首次成功响应：

```json
{
  "success": true,
  "code": 200,
  "message": "请求成功",
  "data": {
    "conversation_id": "a7b86052-51cd-468c-96e7-fac535a95d0c",
    "conversation_reset": false,
    "response_type": "report",
    "report": {
      "overview": "本次分析识别出少量高风险时间桶。",
      "findings": [{
        "title": "异常集中出现",
        "statement": "异常主要集中在一个连续区间。",
        "evidence": ["共3个异常桶，其中连续区间包含2个"],
        "confidence": "high"
      }],
      "inferences": [],
      "cautions": ["异常风险是本次结果内的相对分数，不是概率"],
      "recommended_checks": ["核对异常区间附近的采集和设备运行记录"],
      "limitations": ["当前摘要不包含设备工况和维修记录"]
    },
    "reply": null
  }
}
```

后续追问必须同时传入上次返回的会话ID和1～2000字符的问题：

```json
{
  "analysis_id": "57a6d796-3268-4ef6-9d5f-78e87d517edf",
  "conversation_id": "a7b86052-51cd-468c-96e7-fac535a95d0c",
  "message": "为什么这个时间段容易被判断为异常？"
}
```

追问成功时 `response_type=answer`、`report=null`，回答位于 `reply`。会话超过30分钟后会根据仍然
有效的分析摘要重新建立，并返回 `conversation_reset=true`。分析摘要同样采用30分钟滑动过期；摘要
已过期时必须重新执行数值分析。

## 四、错误

| HTTP状态 | 场景 |
|---|---|
| 400 | 请求结构错误、没有激活的模型配置、缺少算法解释规则 |
| 401 | 未登录或登录会话失效 |
| 403 | 页面权限不足、测点权限被撤销、访问其他用户的摘要 |
| 410 | 分析摘要已经过期，响应数据包含 `ANALYSIS_CONTEXT_EXPIRED` |
| 503 | Redis摘要或连续对话服务不可用 |
| 500 | 模型供应商调用失败或请求超时 |
