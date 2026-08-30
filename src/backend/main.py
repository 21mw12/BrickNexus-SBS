import os

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config.ConfigLoader import config
from app.core.middleware.LogRecorder import get_logger
from app.infra.DB.SQLConnection import sql_manager
from app.domain import *
from app.domain.common.RootInitializer import ensure_root_user
from app.domain.common.PageInitializer import ensure_pages, refresh_page_permission_caches
from app.domain.collector import collector_runtime
from app.infra.RDF import asset_rdf_runtime
from app.domain.rule.service import rule_runtime


logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):

    # ===================== 数据库初始化 =====================
    # 启动兜底：根据已经注册的 ORM 模型自动创建缺失的数据表。
    # create_all 只创建不存在的表，不会修改已有字段、约束或迁移历史数据；
    # 已有数据库的结构升级仍必须通过 Alembic 完成。
    if os.getenv("AUTO_CREATE_TABLES", "true").lower() == "true":
        sql_manager.create_tables("main")
    with sql_manager.get_db("main") as db:
        ensure_pages(db)
        ensure_root_user(db)
    with sql_manager.get_db("main") as db:
        refresh_page_permission_caches(db)
    # ===================== 资产 RDF 投影 =====================
    asset_rdf_runtime.start()
    # ===================== 规则运行时 =====================
    rule_runtime.start()
    # ===================== 数据运行时初始化 =====================
    # RuntimeManager 内部统一启动实时推送监听器和数据采集任务。
    await collector_runtime.start()

    logger.info("SmartBuilding v2.0 启动完成")

    try:
        yield  # FastAPI 应用运行期间
    finally:
        # 即使应用运行期间发生异常，也必须释放完整的数据运行时。
        logger.info("SmartBuilding v2.0 正在关闭...")
        try:
            await collector_runtime.shutdown()
        finally:
            try:
                rule_runtime.shutdown()
            finally:
                asset_rdf_runtime.shutdown()
        logger.info("SmartBuilding v2.0 已关闭")


app = FastAPI( lifespan=lifespan )

# CORS 中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应配置为前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（统一挂载 /api 前缀）
api_router = APIRouter(prefix="/api")
from app.domain.asset.api.AssetAPI import router as asset_router
api_router.include_router(asset_router)
from app.domain.asset.api.SensorModelAPI import router as sensor_model_router
api_router.include_router(sensor_model_router)
from app.domain.asset.api.PointAPI import router as point_router
api_router.include_router(point_router)
from app.domain.channel.api.TerminalRequestAPI import router as terminal_request_router
api_router.include_router(terminal_request_router)
from app.domain.floor_plan.api.FloorPlanAPI import router as floor_plan_router
api_router.include_router(floor_plan_router)
from app.domain.channel.api.RequestAPI import router as request_router
api_router.include_router(request_router)
from app.domain.channel.api.ChannelAPI import router as channel_router
api_router.include_router(channel_router)
from app.domain.channel.api.ControlAPI import router as control_router
api_router.include_router(control_router)
from app.domain.data.api.TerminalRealtimeAPI import router as terminal_realtime_router
api_router.include_router(terminal_realtime_router)
from app.domain.data.api.HistoryAPI import router as history_router
api_router.include_router(history_router)
from app.domain.rule.api.RuleAPI import router as rule_router
api_router.include_router(rule_router)
from app.domain.log.api.LogAPI import router as log_router
api_router.include_router(log_router)
from app.domain.dashboard.api.DashboardAPI import router as dashboard_router
api_router.include_router(dashboard_router)
from app.domain.user.api.UserAPI import router as user_router
api_router.include_router(user_router)
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.server.host, port=config.server.port)
