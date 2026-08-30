"""读取活动 Request，并按 HTTP/MQTT 类型分开加载。"""

from datetime import datetime, timezone

from app.core.middleware.LogRecorder import get_logger
from app.domain.collector.event import (
    CollectionRequestStartedEvent,
    CollectionRequestStoppedEvent,
)
from app.domain.collector.event_bus import collection_event_bus
from app.domain.collector.storage.request_state_storage import request_state_storage
from app.domain.channel.repository.RequestRepository import RequestRepository
from app.domain.channel.service.ChannelResolver import ChannelResolver
from app.infra.DB.SQLConnection import sql_manager

from .http_request_loader import HttpRequestLoader
from .mqtt_request_loader import MqttRequestLoader

logger = get_logger(__name__)


class RequestLoader:
    """使用项目默认数据库加载全部启用的 Request。"""

    def __init__(self) -> None:
        self.http_loader = HttpRequestLoader()
        self.mqtt_loader = MqttRequestLoader()

    def load_active_requests(self) -> dict:
        """查询 ``is_active=true`` 的 Request，按类型加载并返回普通字典。"""
        with sql_manager.get_db("main") as db:
            requests = RequestRepository().select(
                db,
                filters={"status": True},
                order_by="request_id",
            )
            resolved_requests = []
            for request in requests:
                try:
                    # Legacy-shaped in-memory objects are still accepted by isolated
                    # loader callers; persisted rows always use the normalized channel.
                    resolved_requests.append(
                        ChannelResolver.resolve_request(db, request)
                        if hasattr(request, "channel_id")
                        else request
                    )
                except Exception as exc:
                    logger.exception("Request 通道解析失败 request_id=%s error=%s", request.request_id, exc)
                    try:
                        request_state_storage.deactivate(request.request_id)
                    except Exception:
                        logger.exception("Request 通道解析失败后的停用写入失败 request_id=%s", request.request_id)

        result = {
            "http": [],
            "mqtt": [],
        }
        for request in resolved_requests:
            if request.request_type not in result:
                logger.warning(
                    "跳过不支持的 Request 类型 request_id=%s request_type=%s",
                    request.request_id,
                    request.request_type,
                )
                continue

            try:
                self.start(request)
                result[request.request_type].append(request.request_id)
            except Exception as exc:
                # 单条配置错误不能阻止其他 Request 和整个 Web 服务启动。
                try:
                    self.stop(request.request_type, request.request_id)
                except Exception as stop_exc:
                    logger.exception(
                        "Request 启动失败后的资源清理失败 request_id=%s error=%s",
                        request.request_id,
                        stop_exc,
                    )
                try:
                    request_state_storage.deactivate(request.request_id)
                except Exception as state_exc:
                    logger.exception(
                        "Request 停用状态写入失败 request_id=%s error=%s",
                        request.request_id,
                        state_exc,
                    )
                logger.exception(
                    "Request 启动加载失败 request_id=%s request_type=%s error=%s",
                    request.request_id,
                    request.request_type,
                    exc,
                )

        return result

    def start(self, request) -> dict:
        """根据 Request 类型启动一个任务，并返回其解析结构。"""
        if request.request_type == "http":
            storage_interval = None
            protocol_loader = self.http_loader
        elif request.request_type == "mqtt":
            storage_interval = (getattr(request, "request_info", None) or {}).get(
                "storage_interval_seconds"
            )
            protocol_loader = self.mqtt_loader
        else:
            raise ValueError(f"unsupported request type: {request.request_type}")

        # 先让 data 创建周期状态，再开放调度/网络接收，避免 MQTT 首条消息
        # 早于 RequestStartedEvent 而被后续注册操作覆盖。
        collection_event_bus.publish(
            CollectionRequestStartedEvent(
                request_id=request.request_id,
                request_type=request.request_type,
                started_at=datetime.now(timezone.utc),
                storage_interval_seconds=(
                    float(storage_interval) if storage_interval is not None else None
                ),
            )
        )
        try:
            return protocol_loader.start(request)
        except Exception:
            collection_event_bus.publish(
                CollectionRequestStoppedEvent(request_id=request.request_id)
            )
            raise

    def stop(self, request_type: str, request_id: str) -> None:
        """根据 Request 类型调用对应 Loader 的停止方法。"""
        if request_type == "http":
            self.http_loader.stop(request_id)
        elif request_type == "mqtt":
            self.mqtt_loader.stop(request_id)
        else:
            raise ValueError(f"unsupported request type: {request_type}")

    def stop_all(self) -> None:
        """停止两个 Loader 中当前登记的全部 Request。"""
        self.http_loader.stop_all()
        self.mqtt_loader.stop_all()

    def update_point_descriptions(self, descriptions: dict[str, str | None]) -> int:
        """同时刷新 HTTP 和 MQTT 已加载的测点说明缓存。"""
        return self.http_loader.update_point_descriptions(
            descriptions
        ) + self.mqtt_loader.update_point_descriptions(descriptions)


request_loader = RequestLoader()
