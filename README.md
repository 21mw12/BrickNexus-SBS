# 项目介绍

**BrickNexus** — 基于 Brick + RDF 语义模型的智慧楼宇操作系统

BrickNexus 以 PostgreSQL + TimescaleDB 为数据底座，通过 FastAPI 提供高性能后端服务，Vue3  构建现代化交互界面。系统围绕"资产中心"、"数据监测"、"采控通道"、"规则管理"四大核心引擎，实现了从设备接入、数据采集、语义建模到智能决策与指令下发的全链路闭环。

**核心能力：**

- 🏗️ **语义资产建模** —— 基于 Brick + RDF，SQL 为事实来源，语义图可快照重建
- 📊 **数据监测** —— WebSocket 实时推送 + LTTB 下采样历史查询，毫秒级响应
- 🔌 **采控通道** —— 统一抽象 HTTP/MQTT，请求生命周期全托管
- 📐 **楼层平面图** —— 可视化拖拽标记房间，图片与资产数据联动管理
- ⚙️ **声明式规则引擎** —— RDF 定义监控对象、阈值条件、触发策略与动作，热加载生效
- 🔐 **精细化权限** —— 封闭世界原则 + R-First 鉴权 + 资产路径穿透，即时生效



# 部署流程

1. 复制  `.env.example` 为 `.env` 并填写其中的`SMARTBUILDING_JWT_SECRET` 和 `SMARTBUILDING_FERNET_KEY`。这是 **JWT 密钥** 和 **Fernet key** 不要泄漏，启动后谨慎修改。可使用命令直接生成。

   ```shell
   # 方法一：使用 Python 的 cryptography 库
   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   
   # 方法二：使用 openssl 生成 32 字节随机数并转 base64
   openssl rand -base64 32
   ```

2. 修改 `docker-compose.yaml` 中的前后端版本

3. 启动项目

   ```shell
   docker compose up -d
   ```

> 用于 SQLAlchemy 的数据库迁移
> docker compose run --rm backend alembic upgrade head



# 镜像构建方式

```shell
# 构建后端
docker build -t mw/bricknexus-backend:[版本]  src/backend
# 构建前端
docker build -t mw/bricknexus-frontend:[版本] src/frontend
```



#  调试开发

- **本地启动前端**

  1. 修改 `src/frontend/.env`  

  2. 执行命令下载依赖，启动前端

     ```shell
     cd src/frontend
     npm install
     npm run dev
     ```

  3. 访问 `http://localhost:5173`

- **本地启动后端**

  1. 修改 `src/backend/.env`  

  2. 执行命令启动后端

     ```shell
     python ./main.py
     ```

- **本体启动数据库**（PostgreSQL 和 Redis）

  ```shell
  cd docker
  docker compose up -d postgres redis
  ```