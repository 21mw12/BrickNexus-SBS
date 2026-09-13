from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

from app.core.middleware.LogRecorder import get_logger


logger = get_logger(__name__)


@dataclass(eq=False)
class SandboxConnection:
    websocket: WebSocket
    sandbox_id: str
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=100))
    subscriptions: tuple[str, ...] = ()
    generation: int = 0
    ready: bool = False
    closed: bool = False
    pending: list[tuple[int, dict]] = field(default_factory=list)
    sender: asyncio.Task | None = None


class SandboxRealtimeService:
    """Per-process sandbox WebSocket subscriptions and filtered fan-out."""

    def __init__(self) -> None:
        self._connections: dict[str, set[SandboxConnection]] = {}
        self._lock = asyncio.Lock()

    async def register(self, websocket: WebSocket, sandbox_id: str) -> SandboxConnection:
        connection = SandboxConnection(websocket, sandbox_id)
        connection.sender = asyncio.create_task(
            self._send(connection),
            name=f"sandbox-websocket-sender-{id(connection)}",
        )
        async with self._lock:
            self._connections.setdefault(sandbox_id, set()).add(connection)
        return connection

    async def unregister(self, connection: SandboxConnection) -> None:
        async with self._lock:
            connection.closed = True
            rows = self._connections.get(connection.sandbox_id)
            if rows is not None:
                rows.discard(connection)
                if not rows:
                    self._connections.pop(connection.sandbox_id, None)
            connection.subscriptions = ()
            connection.pending.clear()
        if connection.sender and connection.sender is not asyncio.current_task():
            connection.sender.cancel()
            try:
                await connection.sender
            except asyncio.CancelledError:
                pass

    async def replace_subscriptions(
        self,
        connection: SandboxConnection,
        point_ids: list[str],
    ) -> int:
        """Atomically replace subscriptions and pause live delivery for snapshot."""
        async with self._lock:
            connection.generation += 1
            connection.subscriptions = tuple(point_ids)
            connection.ready = False
            connection.pending.clear()
            return connection.generation

    async def activate_subscription(
        self,
        connection: SandboxConnection,
        generation: int,
        snapshot_tick: int,
    ) -> None:
        """Resume delivery, dropping ticks already represented by the snapshot."""
        async with self._lock:
            if connection.closed or connection.generation != generation:
                return
            connection.ready = True
            pending = tuple(connection.pending)
            connection.pending.clear()
        for pending_generation, payload in pending:
            if payload.get("type") == "tick" and int(payload.get("tick", -1)) <= snapshot_tick:
                continue
            await self.enqueue(connection, payload, pending_generation)

    async def enqueue(
        self,
        connection: SandboxConnection,
        payload: dict,
        generation: int | None = None,
    ) -> bool:
        if connection.closed:
            return False
        try:
            connection.queue.put_nowait((generation, payload))
            return True
        except asyncio.QueueFull:
            logger.warning(
                "沙盒 WebSocket 客户端消费过慢，关闭连接 sandbox_id=%s",
                connection.sandbox_id,
            )
            asyncio.create_task(self.unregister(connection))
            return False

    @staticmethod
    def _for_connection(connection: SandboxConnection, payload: dict) -> dict:
        if payload.get("type") != "tick":
            return payload
        subscriptions = set(connection.subscriptions)
        return {
            **payload,
            "subscription_version": connection.generation,
            "measurements": [
                item
                for item in payload.get("measurements", [])
                if item.get("point_id") in subscriptions
            ],
        }

    async def publish(self, sandbox_id: str, payload: dict) -> None:
        ready: list[tuple[SandboxConnection, int, dict]] = []
        async with self._lock:
            for connection in tuple(self._connections.get(sandbox_id, ())):
                if connection.closed:
                    continue
                generation = connection.generation
                filtered = self._for_connection(connection, payload)
                if not connection.ready:
                    connection.pending.append((generation, filtered))
                    if len(connection.pending) > 100:
                        connection.pending.pop(0)
                else:
                    ready.append((connection, generation, filtered))
        for connection, generation, filtered in ready:
            await self.enqueue(connection, filtered, generation)

    async def _send(self, connection: SandboxConnection) -> None:
        try:
            while True:
                try:
                    generation, payload = await asyncio.wait_for(
                        connection.queue.get(), timeout=25
                    )
                except asyncio.TimeoutError:
                    generation, payload = None, {"type": "heartbeat"}
                if generation is not None and generation != connection.generation:
                    continue
                # WebSocket.send_json uses stdlib json.dumps directly. Normalize
                # ORM/Pydantic values such as Sandbox.created_at before sending.
                await connection.websocket.send_json(jsonable_encoder(payload))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.info(
                "沙盒 WebSocket 发送结束 sandbox_id=%s error=%s",
                connection.sandbox_id,
                exc,
            )
            await self.unregister(connection)


sandbox_realtime_service = SandboxRealtimeService()
