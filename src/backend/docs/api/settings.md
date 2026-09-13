# 系统设置 API

## 一、说明

本文记录大语言模型配置接口。全部接口需要
`Authorization: Bearer <JWT令牌>` 和 `settings` 页面权限；包含请求体的接口还需要
`Content-Type: application/json`。

除特别说明外，返回使用统一 JSON 包装：

```json
{"success": true, "code": 200, "message": "请求成功", "data": {}}
```

### 配置结构

第一期仅支持 `model_type=chat`，`service_type` 支持 `vllm`、`ollama`、`deepseek`。

vLLM 和 DeepSeek：

```json
{
  "service_name": "DeepSeek 主模型",
  "service_type": "deepseek",
  "content": {
    "base_url": "https://api.deepseek.com",
    "api_key": "secret",
    "model_name": "deepseek-chat",
    "model_type": "chat",
    "max_tokens": 4096
  }
}
```

Ollama：

```json
{
  "service_name": "本地 Qwen",
  "service_type": "ollama",
  "content": {
    "base_url": "http://127.0.0.1:11434",
    "model_name": "qwen3:8b",
    "model_type": "chat",
    "num_ctx": 8192
  }
}
```

`base_url` 必须是绝对 HTTP(S) 地址，不允许包含用户名、密码、查询参数或片段。`max_tokens` 和 `num_ctx` 必须为正整数。

vLLM、DeepSeek 的 API Key 使用 Fernet 加密入库。查询接口不会返回密钥，只返回：

```json
{"api_key_configured": true}
```

编辑时不传 `content.api_key` 表示保留原密钥。部署环境应通过 `SMARTBUILDING_FERNET_KEY` 配置稳定的 Fernet Key；修改密钥后，已有密文将无法解密。

## 二、API

### 查询配置列表

- 请求地址：`POST /api/settings/llm/list?page=1&limit=20`
- 请求头：`Authorization: Bearer <JWT令牌>`、`Content-Type: application/json`
- 查询参数：`page` 默认1；`limit` 默认20，范围1～100。
- 请求体：可以为空，也可以传：


```json
{
  "service_name": "本地",
  "service_type": "ollama",
  "is_use": true
}
```

- 返回格式：响应中的 `data` 为：

```json
{
  "total": 1,
  "items": [{
    "llm_id": "uuid",
    "service_name": "本地 Qwen",
    "service_type": "ollama",
    "content": {
      "base_url": "http://127.0.0.1:11434",
      "model_name": "qwen3:8b",
      "model_type": "chat",
      "num_ctx": 8192
    },
    "is_use": true,
    "created_at": "2026-09-09T10:00:00Z"
  }]
}
```

结果按已激活优先、配置名称升序、ID升序排列。

### 查询、新增、编辑和删除

- 请求头：`Authorization: Bearer <JWT令牌>`；新增和编辑还需要
  `Content-Type: application/json`。
- 路径参数：`llm_id` 为模型配置 ID。
- 新增和编辑请求体：使用“配置结构”中的格式。
- 返回格式：查询、新增和编辑返回脱敏后的配置；删除成功返回
  `data: {"ok": true}`。

| 方法 | 地址 | 说明 |
|---|---|---|
| GET | `/api/settings/llm/find/{llm_id}` | 查询脱敏后的详情 |
| POST | `/api/settings/llm/add` | 新增配置，始终以未激活状态保存 |
| POST | `/api/settings/llm/edit/{llm_id}` | 完整更新配置；活动配置会先测试新参数 |
| GET | `/api/settings/llm/drop/{llm_id}` | 删除配置；活动配置禁止删除 |

活动配置的新参数无法连通时，编辑操作整体回滚。

### 测试未保存配置

- 请求地址：`POST /api/settings/llm/test`
- 请求头：`Authorization: Bearer <JWT令牌>`、`Content-Type: application/json`
- 请求体：不需要 `service_name`：


```json
{
  "service_type": "ollama",
  "content": {
    "base_url": "http://127.0.0.1:11434",
    "model_name": "qwen3:8b",
    "model_type": "chat",
    "num_ctx": 8192
  }
}
```

### 测试已保存配置

- 请求地址：`POST /api/settings/llm/test/{llm_id}`
- 请求头：`Authorization: Bearer <JWT令牌>`、`Content-Type: application/json`
- 路径参数：`llm_id` 为已保存的模型配置 ID。
- 请求体：为空时测试数据库中的配置；携带请求体时使用请求体覆盖连接参数。

未传 API Key 时复用数据库中的密钥，供编辑弹窗测试尚未保存的参数。

- 返回格式：

```json
{
  "connected": true,
  "latency_ms": 368,
  "service_type": "ollama",
  "model_name": "qwen3:8b",
  "message": "模型连接成功"
}
```

连接成功返回 HTTP 200。连接失败返回 HTTP 502，`data.connected=false`，并带有 `error_code`：`timeout`、`authentication_failed`、`model_not_found`、`dependency_missing` 或 `provider_error`。请求字段不合法返回 HTTP 400/422。错误内容不会包含密钥、请求头和完整供应商响应。测试超时为15秒。

### 激活和停用

- 请求头：`Authorization: Bearer <JWT令牌>`。
- 路径参数：`llm_id` 为已保存的模型配置 ID。
- 请求参数：无请求体。
- 返回格式：返回脱敏后的目标配置；激活失败时以 HTTP 502 返回连通性测试结果。

| 方法 | 地址 | 说明 |
|---|---|---|
| POST | `/api/settings/llm/activate/{llm_id}` | 连通测试成功后原子切换为唯一活动模型 |
| POST | `/api/settings/llm/deactivate/{llm_id}` | 停用指定配置，允许系统没有活动模型 |

激活失败返回502并在 `data` 中携带脱敏后的测试结果，原活动模型保持不变。连接测试只确认聊天接口和指定模型能够返回内容，不评价规则生成质量。
