# 依赖下载

参考 `requirements.txt`



# 配置说明

默认读取项目根目录的 `config.yaml`，并自动加载同目录的 `.env`。
系统环境变量优先于 `.env`，`.env` 中的数据库和 Redis 配置优先于
`config.yaml`。

如需覆盖路径，可通过系统环境变量设置：

- SMARTBUILDING_CONFIG_PATH
- SMARTBUILDING_LOG_DIR
- SMARTBUILDING_RDF_DIR
- DB_TYPE、DB_HOST、DB_PORT、DB_USER、DB_NAME、DB_PASSWORD
- REDIS_HOST、REDIS_PORT、REDIS_DB、REDIS_PASSWORD
- AUTO_CREATE_TABLES

说明：

- 上述变量支持绝对路径和相对路径。
- 相对路径会按项目根目录解析，不受运行目录影响。
- 测试环境可以单独设置环境变量覆盖这些值。



# 项目结构

- domain：业务模块（再用文件夹区分不同业务，可包含以下文件夹）
  - api：对前端或其他服务开放的接口
  - service：业务逻辑
  - repository：数据访问
    - model：对应数据bc
  - entity：业务对象
  - schema：请求/响应
- infra（Infrastructure）：基础设施
- core：底层核心功能支持
  - config：配置加载
  - middleware：中间件
  - utils：工具类
- common：全局共享定义
- resources：资源文件夹
- log：日志文件夹



| 一级模块 | 二级模块   | 职责                                | 举例                                                    |
| -------- | ---------- | ----------------------------------- | ------------------------------------------------------- |
| domain   |            | 业务模块（这个系统是干嘛的）        |                                                         |
|          | api        | 接口                                |                                                         |
|          | service    | 业务逻辑（一个service一个业务能力） | query、alter、save、remove                              |
|          | repository | 数据访问（拿数据 / 存数据）         | select、update、create、delete                          |
|          | entity     | 业务对象                            |                                                         |
|          | schema     | 接口结构校验                        |                                                         |
| infra    |            | 外部依赖实现（怎么与其他服务连接）  | 数据库连接、MQTT客户端、Redis、定时任务、三方API封装    |
| core     |            | 运行支撑能力                        |                                                         |
|          | config     | 配置加载                            |                                                         |
|          | middleware | 中间件                              | 日志记录、鉴权（token校验）、请求耗时统计、全局异常处理 |
|          | utils      | 通用工具                            | UUID生成、时间处理、Excel解析、HTTP请求封装             |
| common   |            | 全局共享定义（一种标准）            |                                                         |
|          | constants  | 常量                                |                                                         |
|          | enums      | 枚举                                |                                                         |
|          | response   | 响应                                |                                                         |
