"""Terminal 最新数据 WebSocket 订阅和 Redis Pub/Sub 分发。"""

import asyncio
import inspect
import json
from dataclasses import dataclass, field
from typing import Any

import redis.asyncio as async_redis
from fastapi import WebSocket
from sqlalchemy import select

from app.common.validators import ValidationError
from app.core.config.ConfigLoader import config
from app.core.middleware.LogRecorder import get_logger
from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.repository.models.AssetTerminal import AssetTerminal
from app.domain.common.PermissionChecker import (
    check_page_permission,
    get_viewable_asset_ids,
)
from app.domain.data.storage.redis_storage import RedisStorage
from app.infra.DB.SQLConnection import sql_manager

logger = get_logger(__name__)


@dataclass(eq=False)
class TerminalConnection:
    """保存一条 WebSocket 连接的订阅状态和唯一发送队列。"""

    websocket: WebSocket
    send_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=100))
    subscriptions: set[str] = field(default_factory=set)
    pending_terminal_ids: set[str] = field(default_factory=set)
    generation: int = 0
    ready: bool = True
    closed: bool = False
    sender_task: asyncio.Task | None = None


class TerminalRealtimeService:
    """每个应用进程维护一个 Redis 监听器，并向本进程连接分发更新。"""

    UPDATE_CHANNEL = RedisStorage.UPDATE_CHANNEL
    PAGE_CODES = ("data", "data:realtime", "data:sensors")

    def __init__(self) -> None:
        self.connections: set[TerminalConnection] = set()
        self.terminal_connections: dict[str, set[TerminalConnection]] = {}
        self._lock = asyncio.Lock()
        self._listener_task: asyncio.Task | None = None
        self._data_client = None
        self._stopping = False

    @property
    def started(self) -> bool:
        """返回当前进程的 Redis 监听任务是否已经启动。"""
        return self._listener_task is not None and not self._listener_task.done()

    async def start(self) -> None:
        """启动进程级 Redis Pub/Sub 监听任务，重复调用不会重复创建。"""
        if self.started:
            return
        self._stopping = False
        self._data_client = self._create_redis_client()
        self._listener_task = asyncio.create_task(
            self._listen_updates(),
            name="terminal-realtime-redis-listener",
        )
        logger.info("Terminal WebSocket Redis 监听器已启动 channel=%s", self.UPDATE_CHANNEL)

    async def shutdown(self) -> None:
        """停止 Redis 监听器并关闭当前进程中的全部 WebSocket 连接。"""
        self._stopping = True
        listener_task = self._listener_task
        self._listener_task = None
        if listener_task is not None:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            connections = tuple(self.connections)
        for connection in connections:
            await self.disconnect(connection, code=1001)

        if self._data_client is not None:
            await self._close_async_resource(self._data_client)
            self._data_client = None
        logger.info("Terminal WebSocket 实时服务已停止")

    async def register(self, websocket: WebSocket) -> TerminalConnection:
        """登记连接并为它创建唯一发送协程。"""
        connection = TerminalConnection(websocket=websocket)
        connection.sender_task = asyncio.create_task(
            self._sender_loop(connection),
            name=f"terminal-websocket-sender-{id(connection)}",
        )
        async with self._lock:
            self.connections.add(connection)
        return connection

    async def disconnect(self, connection: TerminalConnection, code: int = 1000) -> None:
        """注销订阅索引、取消发送任务并关闭 WebSocket。"""
        await self._remove_connection(connection)

        sender_task = connection.sender_task
        current_task = asyncio.current_task()
        if sender_task is not None and sender_task is not current_task and not sender_task.done():
            sender_task.cancel()
            try:
                await sender_task
            except asyncio.CancelledError:
                pass

        try:
            await connection.websocket.close(code=code)
        except Exception:
            # 客户端通常已经先断开，此时重复 close 不需要影响资源释放。
            pass

    async def replace_subscriptions(
        self,
        connection: TerminalConnection,
        terminal_ids: list[str],
    ) -> int:
        """原子替换连接的完整订阅列表，并暂停实时消息直到初始快照入队。"""
        async with self._lock:
            for terminal_id in connection.subscriptions:
                subscribers = self.terminal_connections.get(terminal_id)
                if subscribers is not None:
                    subscribers.discard(connection)
                    if not subscribers:
                        self.terminal_connections.pop(terminal_id, None)

            connection.generation += 1
            connection.ready = False
            connection.pending_terminal_ids.clear()
            connection.subscriptions = set(terminal_ids)
            for terminal_id in terminal_ids:
                self.terminal_connections.setdefault(terminal_id, set()).add(connection)
            return connection.generation

    async def activate_subscription(
        self,
        connection: TerminalConnection,
        generation: int,
    ) -> None:
        """初始快照入队后启用实时推送，并补发切换期间发生的更新。"""
        async with self._lock:
            if connection.closed or generation != connection.generation:
                return
            connection.ready = True
            pending_terminal_ids = tuple(connection.pending_terminal_ids)
            connection.pending_terminal_ids.clear()

        for terminal_id in pending_terminal_ids:
            snapshot = await self.get_snapshot(terminal_id)
            if snapshot is not None:
                await self.enqueue(
                    connection,
                    {
                        "type": "terminal_update",
                        "terminal_id": terminal_id,
                        "data": snapshot,
                    },
                    generation=generation,
                )

    async def clear_subscriptions(self, connection: TerminalConnection) -> int:
        """清除连接当前全部订阅，供鉴权失败和客户端取消订阅使用。"""
        generation = await self.replace_subscriptions(connection, [])
        await self.activate_subscription(connection, generation)
        return generation

    async def enqueue(
        self,
        connection: TerminalConnection,
        payload: dict,
        generation: int | None = None,
    ) -> bool:
        """将消息交给唯一发送协程；慢客户端队列满时主动关闭。"""
        if connection.closed:
            return False
        try:
            connection.send_queue.put_nowait((generation, payload))
            return True
        except asyncio.QueueFull:
            logger.warning("Terminal WebSocket 客户端消费过慢，关闭连接")
            asyncio.create_task(self.disconnect(connection, code=1013))
            return False

    async def filter_authorized_terminal_ids(
        self,
        token: str,
        terminal_ids: list[str],
    ) -> tuple[list[str], list[str]]:
        """在线程池中验证页面和资产权限，并按输入顺序拆分合法与拒绝 ID。"""
        return await asyncio.to_thread(
            self._filter_authorized_terminal_ids_sync,
            token,
            terminal_ids,
        )

    @classmethod
    def _filter_authorized_terminal_ids_sync(
        cls,
        token: str,
        terminal_ids: list[str],
    ) -> tuple[list[str], list[str]]:
        """同步权限查询实现，每次客户端替换列表时执行一次。"""
        if not token:
            raise ValidationError("token is required")
        if not check_page_permission(token, list(cls.PAGE_CODES)):
            raise ValidationError("permission denied")

        with sql_manager.get_db("main") as db:
            viewable = get_viewable_asset_ids(token, db)
            real_terminal_ids: set[str] = set()
            if terminal_ids:
                stmt = (
                    select(Asset.asset_id)
                    .join(AssetTerminal, AssetTerminal.asset_id == Asset.asset_id)
                    .where(
                        Asset.asset_type == "terminal",
                        Asset.asset_id.in_(terminal_ids),
                    )
                )
                real_terminal_ids = set(db.execute(stmt).scalars().all())

        accepted = [
            terminal_id
            for terminal_id in terminal_ids
            if terminal_id in real_terminal_ids
            and (viewable is None or terminal_id in viewable)
        ]
        accepted_set = set(accepted)
        rejected = [terminal_id for terminal_id in terminal_ids if terminal_id not in accepted_set]
        return accepted, rejected

    async def get_snapshot(self, terminal_id: str) -> dict | None:
        """读取一个 Terminal 最新快照，无缓存或缓存损坏时返回 None。"""
        client = self._ensure_data_client()
        raw = await client.get(RedisStorage.key(terminal_id))
        return self._decode_snapshot(raw)

    async def get_snapshots(self, terminal_ids: list[str]) -> tuple[list[dict], list[str]]:
        """使用 MGET 一次读取初始订阅的全部快照，并返回无缓存 ID。"""
        if not terminal_ids:
            return [], []
        client = self._ensure_data_client()
        raw_values = await client.mget([RedisStorage.key(item) for item in terminal_ids])
        snapshots: list[dict] = []
        missing_terminal_ids: list[str] = []
        for terminal_id, raw in zip(terminal_ids, raw_values):
            snapshot = self._decode_snapshot(raw)
            if snapshot is None:
                missing_terminal_ids.append(terminal_id)
            else:
                snapshots.append(snapshot)
        return snapshots, missing_terminal_ids

    async def handle_terminal_update(self, terminal_id: str) -> None:
        """读取更新后的最新快照，并逐连接、逐 Terminal 推送。"""
        async with self._lock:
            subscribers = tuple(self.terminal_connections.get(terminal_id, ()))
            ready_connections: list[tuple[TerminalConnection, int]] = []
            for connection in subscribers:
                if connection.closed:
                    continue
                if not connection.ready:
                    connection.pending_terminal_ids.add(terminal_id)
                else:
                    ready_connections.append((connection, connection.generation))

        if not ready_connections:
            return
        snapshot = await self.get_snapshot(terminal_id)
        if snapshot is None:
            return
        for connection, generation in ready_connections:
            await self.enqueue(
                connection,
                {
                    "type": "terminal_update",
                    "terminal_id": terminal_id,
                    "data": snapshot,
                },
                generation=generation,
            )

    async def _sender_loop(self, connection: TerminalConnection) -> None:
        """串行发送该连接的所有消息，并丢弃旧订阅世代的待发送更新。"""
        try:
            while True:
                generation, payload = await connection.send_queue.get()
                if generation is not None and generation != connection.generation:
                    continue
                await connection.websocket.send_json(payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.info("Terminal WebSocket 发送结束 error=%s", exc)
            await self._remove_connection(connection)
            try:
                await connection.websocket.close(code=1011)
            except Exception:
                pass

    async def _remove_connection(self, connection: TerminalConnection) -> None:
        """只修改进程内索引；可由接收协程和发送协程安全地重复调用。"""
        async with self._lock:
            connection.closed = True
            self.connections.discard(connection)
            for terminal_id in connection.subscriptions:
                subscribers = self.terminal_connections.get(terminal_id)
                if subscribers is not None:
                    subscribers.discard(connection)
                    if not subscribers:
                        self.terminal_connections.pop(terminal_id, None)
            connection.subscriptions.clear()
            connection.pending_terminal_ids.clear()

    async def _listen_updates(self) -> None:
        """持续监听 Redis 通知；异常后按上限5秒退避并重新连接。"""
        retry_delay = 1.0
        while not self._stopping:
            client = None
            pubsub = None
            try:
                client = self._create_redis_client()
                pubsub = client.pubsub(ignore_subscribe_messages=True)
                await pubsub.subscribe(self.UPDATE_CHANNEL)
                retry_delay = 1.0
                logger.info("Terminal Redis Pub/Sub 订阅成功 channel=%s", self.UPDATE_CHANNEL)

                while not self._stopping:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    if not message or message.get("type") != "message":
                        continue
                    terminal_id = message.get("data")
                    if isinstance(terminal_id, bytes):
                        terminal_id = terminal_id.decode("utf-8")
                    if isinstance(terminal_id, str) and terminal_id:
                        await self.handle_terminal_update(terminal_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not self._stopping:
                    logger.exception(
                        "Terminal Redis Pub/Sub 异常，等待重连 delay=%s error=%s",
                        retry_delay,
                        exc,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 5.0)
            finally:
                if pubsub is not None:
                    await self._close_async_resource(pubsub)
                if client is not None:
                    await self._close_async_resource(client)

    def _ensure_data_client(self):
        """测试或非标准生命周期调用时按需创建异步 Redis 数据客户端。"""
        if self._data_client is None:
            self._data_client = self._create_redis_client()
        return self._data_client

    @staticmethod
    def _create_redis_client():
        """使用项目现有 Redis 配置创建独立异步客户端。"""
        redis_config = config.redis
        return async_redis.Redis(
            host=redis_config.host,
            port=redis_config.port,
            db=redis_config.db,
            username=redis_config.username or None,
            password=redis_config.password or None,
            decode_responses=redis_config.decode_responses,
            max_connections=redis_config.max_connections,
            socket_timeout=redis_config.socket_timeout,
            health_check_interval=redis_config.health_check_interval,
            ssl=redis_config.ssl,
        )

    @staticmethod
    async def _close_async_resource(resource) -> None:
        """兼容 redis-py 不同版本提供的 aclose/close 方法。"""
        close_method = getattr(resource, "aclose", None) or getattr(resource, "close", None)
        if close_method is None:
            return
        try:
            result = close_method()
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            # 连接本身已经异常时，关闭动作也可能失败；不能因此终止重连循环。
            logger.warning("异步 Redis 资源关闭失败 error=%s", exc)

    @staticmethod
    def _decode_snapshot(raw: Any) -> dict | None:
        """将 Redis 字符串安全解析成 Terminal 快照。"""
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            snapshot = json.loads(raw)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        return snapshot if isinstance(snapshot, dict) else None


terminal_realtime_service = TerminalRealtimeService()
