"""
采集运行时生命周期管理。

应用启动时先准备 data 消费者和 Terminal 实时推送，再启动调度器与 collector；
应用关闭时按相反顺序释放，保证 collector 停止前 data 消费者始终可用。
"""

from app.core.middleware.LogRecorder import get_logger
from app.infra.Scheduler.SchedulerManager import SchedulerManager, scheduler
from app.domain.collector.loader.request_loader import request_loader
from app.domain.data.service.CollectionEventConsumer import (
    CollectionDataConsumer,
    collection_data_consumer,
)
from app.domain.data.service.TerminalRealtimeService import (
    TerminalRealtimeService,
    terminal_realtime_service,
)

logger = get_logger(__name__)


class CollectorRuntimeManager:
    """统一控制实时推送、调度器和 Request Loader 的启动与停止。"""

    def __init__(
        self,
        *,
        scheduler_manager: SchedulerManager = scheduler,
        realtime_service: TerminalRealtimeService = terminal_realtime_service,
        data_consumer: CollectionDataConsumer = collection_data_consumer,
    ) -> None:
        self._started = False
        self._realtime_started = False
        self.scheduler = scheduler_manager
        self.realtime_service = realtime_service
        self.data_consumer = data_consumer

    async def start(self) -> None:
        """按实时监听、调度器、Request 的顺序启动整个数据运行时。"""
        if self._started:
            return

        try:
            self.data_consumer.start()
            # 先建立 Redis 更新监听，避免采集任务启动后产生的通知无人接收。
            await self.realtime_service.start()
            self._realtime_started = True
            self.scheduler.start()
            result = request_loader.load_active_requests()
        except Exception:
            # 任一采集组件启动失败时，反向释放已经创建的全部运行时资源。
            try:
                request_loader.stop_all()
            except Exception as cleanup_exc:
                logger.exception("采集启动失败后的资源清理失败 error=%s", cleanup_exc)
            try:
                self.scheduler.shutdown()
            except Exception as cleanup_exc:
                logger.exception("调度器启动失败后的资源清理失败 error=%s", cleanup_exc)
            try:
                self.data_consumer.shutdown()
            except Exception as cleanup_exc:
                logger.exception("data 消费者启动失败后的资源清理失败 error=%s", cleanup_exc)
            try:
                await self.realtime_service.shutdown()
            except Exception as cleanup_exc:
                logger.exception("实时推送启动失败后的资源清理失败 error=%s", cleanup_exc)
            self._realtime_started = False
            raise
        self._started = True
        logger.info("数据运行时启动完成 loaded_requests=%s", result)

    async def shutdown(self) -> None:
        """按 Request、调度器、实时推送监听器的顺序关闭数据运行时。"""
        if not self._started and not self._realtime_started:
            return
        try:
            if self._started:
                try:
                    request_loader.stop_all()
                finally:
                    try:
                        self.scheduler.shutdown()
                    finally:
                        self.data_consumer.shutdown()
        finally:
            self._started = False
            if self._realtime_started:
                try:
                    await self.realtime_service.shutdown()
                finally:
                    self._realtime_started = False
        logger.info("采集与数据运行时已关闭")


collector_runtime = CollectorRuntimeManager()
