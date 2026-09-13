# 后端 API 文档

接口文档按后端路由模块拆分，每个文件均由“说明”和“API”两部分组成。业务接口统一挂载在
`/api` 下；实际域名、端口和协议由部署环境决定。

## 文档索引

| 模块 | 文档 | 路由前缀 |
|---|---|---|
| 看板 | [dashboard.md](dashboard.md) | `/api/dashboard` |
| 资产 | [asset.md](asset.md) | `/api/assets` |
| 测点定义 | [point.md](point.md) | `/api/points` |
| 传感器型号 | [sensor-model.md](sensor-model.md) | `/api/models` |
| 楼层平面图 | [floor-plan.md](floor-plan.md) | `/api/floor-plans` |
| 终端采集请求绑定 | [terminal-request.md](terminal-request.md) | `/api/terminal_request` |
| 采控通道 | [channel.md](channel.md) | `/api/channel` |
| 采集请求 | [request.md](request.md) | `/api/request` |
| 设备控制 | [control.md](control.md) | `/api/control` |
| 终端实时数据 | [terminal-realtime.md](terminal-realtime.md) | `/api/ws/terminals` |
| 历史数据 | [history.md](history.md) | `/api/history` |
| 智能分析 | [analytics.md](analytics.md) | `/api/analytics` |
| 智能分析 AI 解读 | [agent-analysis.md](agent-analysis.md) | `/api/agent/analysis` |
| 规则管理 | [rule.md](rule.md) | `/api/rules` |
| 规则自然语言配置 | [agent-rule.md](agent-rule.md) | `/api/agent` |
| 数字孪生沙盒 | [sandbox.md](sandbox.md) | `/api/sandbox`、`/api/ws/sandboxes` |
| 用户、角色与页面 | [user.md](user.md) | `/api/user` |
| 系统日志 | [log.md](log.md) | `/api/logs` |
| 系统设置 | [settings.md](settings.md) | `/api/settings` |

## 公共约定

除登录、文件流和 WebSocket 接口外，请求通常需要：

```http
Authorization: Bearer <JWT令牌>
```

JSON 请求还需要 `Content-Type: application/json`。普通 HTTP 接口使用统一返回结构：

```json
{
  "success": true,
  "code": 200,
  "message": "请求成功",
  "data": {}
}
```

分页接口通常使用 `page` 和 `limit` 查询参数，分页结果为
`{"total": 0, "items": []}`。权限由页面权限和资产实例权限共同决定，具体要求见各模块说明。

资产实例权限字符含义：`C` 创建、`R` 查看、`U` 修改、`D` 删除、`O` 操作；
`O` 只适用于 Terminal 和 Sensor。未携带或携带无效令牌通常返回 HTTP 401，页面或实例权限不足
返回 HTTP 403，业务参数错误返回 HTTP 400，未被业务层处理的错误返回 HTTP 500。

## 维护规则

- 接口地址必须写完整 `/api` 前缀，并与 `src/backend/main.py` 中注册的路由一致。
- 每个路由模块只维护一份正文，跨模块内容使用相对链接引用。
- 新增或修改接口时，同步更新请求头、路径/查询/请求体参数以及返回格式。
- 文件下载和 WebSocket 不使用统一 JSON 返回时，必须单独注明媒体类型或消息格式。
