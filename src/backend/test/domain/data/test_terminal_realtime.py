"""Terminal WebSocket 实时订阅服务测试。"""

import asyncio
import importlib
import json
from contextlib import nullcontext

from fastapi import WebSocketDisconnect

from app.common.validators import ValidationError
from app.domain.data.api.TerminalRealtimeAPI import terminal_realtime_websocket
from app.domain.data.service.TerminalRealtimeService import (
    TerminalRealtimeService,
    terminal_realtime_service,
)
from app.infra.DB.SQLConnection import sql_manager


class _FakeWebSocket:
    def __init__(self) -> None:
        self.messages = []
        self.close_codes = []

    async def send_json(self, payload) -> None:
        self.messages.append(payload)

    async def close(self, code=1000) -> None:
        self.close_codes.append(code)


class _ScriptedWebSocket(_FakeWebSocket):
    """依次提供客户端消息，并等待上一条服务端响应完成后再发送下一条。"""

    def __init__(self, inbound_messages) -> None:
        super().__init__()
        self.inbound_messages = inbound_messages
        self.index = 0
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def receive_json(self):
        if self.index > 0:
            while len(self.messages) < self.index:
                await asyncio.sleep(0)
        if self.index >= len(self.inbound_messages):
            raise WebSocketDisconnect()
        payload = self.inbound_messages[self.index]
        self.index += 1
        return payload


class _FakeRedis:
    def __init__(self, snapshots=None) -> None:
        self.snapshots = snapshots or {}
        self.closed = False

    async def get(self, key):
        return self.snapshots.get(key)

    async def mget(self, keys):
        return [self.snapshots.get(key) for key in keys]

    async def aclose(self):
        self.closed = True


def test_subscription_replace_update_and_disconnect_cleanup() -> None:
    """订阅替换后只接收新 Terminal，断开后清空全部反向索引。"""

    async def scenario():
        service = TerminalRealtimeService()
        service._data_client = _FakeRedis(
            {
                "terminal:latest:terminal-1": json.dumps({"terminal_id": "terminal-1", "value": 1}),
                "terminal:latest:terminal-2": json.dumps({"terminal_id": "terminal-2", "value": 2}),
            }
        )
        websocket = _FakeWebSocket()
        connection = await service.register(websocket)

        generation = await service.replace_subscriptions(connection, ["terminal-1"])
        await service.enqueue(
            connection,
            {"type": "snapshot", "terminal_ids": ["terminal-1"]},
            generation=generation,
        )
        await service.activate_subscription(connection, generation)
        await service.handle_terminal_update("terminal-1")
        await asyncio.sleep(0)

        assert websocket.messages[-1] == {
            "type": "terminal_update",
            "terminal_id": "terminal-1",
            "data": {"terminal_id": "terminal-1", "value": 1},
        }

        generation = await service.replace_subscriptions(connection, ["terminal-2"])
        await service.enqueue(
            connection,
            {"type": "snapshot", "terminal_ids": ["terminal-2"]},
            generation=generation,
        )
        await service.activate_subscription(connection, generation)
        message_count = len(websocket.messages)
        await service.handle_terminal_update("terminal-1")
        await asyncio.sleep(0)
        assert len(websocket.messages) == message_count + 1  # 新 snapshot 由发送协程处理

        await service.handle_terminal_update("terminal-2")
        await asyncio.sleep(0)
        assert websocket.messages[-1]["terminal_id"] == "terminal-2"

        await service.disconnect(connection)
        assert service.connections == set()
        assert service.terminal_connections == {}

    asyncio.run(scenario())


def test_initial_snapshots_report_missing_cache() -> None:
    """合法但尚无 Redis 快照的 Terminal 仍保留订阅并返回 missing。"""

    async def scenario():
        service = TerminalRealtimeService()
        service._data_client = _FakeRedis(
            {
                "terminal:latest:terminal-1": json.dumps({"terminal_id": "terminal-1"}),
            }
        )
        snapshots, missing = await service.get_snapshots(["terminal-1", "terminal-2"])
        assert snapshots == [{"terminal_id": "terminal-1"}]
        assert missing == ["terminal-2"]

    asyncio.run(scenario())


def test_permission_filter_keeps_only_visible_real_terminals(monkeypatch) -> None:
    """页面校验后，只保留同时是真实Terminal且位于用户可见集合中的ID。"""
    realtime_module = importlib.import_module(
        "app.domain.data.service.TerminalRealtimeService"
    )

    class _Result:
        def scalars(self):
            return self

        def all(self):
            return ["terminal-1", "terminal-2"]

    class _Db:
        def execute(self, statement):
            return _Result()

    monkeypatch.setattr(realtime_module, "check_page_permission", lambda token, pages: True)
    monkeypatch.setattr(
        realtime_module,
        "get_viewable_asset_ids",
        lambda token, db: {"terminal-1"},
    )
    monkeypatch.setattr(sql_manager, "get_db", lambda key: nullcontext(_Db()))

    accepted, rejected = TerminalRealtimeService._filter_authorized_terminal_ids_sync(
        "valid-token",
        ["terminal-1", "terminal-2", "not-a-terminal"],
    )

    assert accepted == ["terminal-1"]
    assert rejected == ["terminal-2", "not-a-terminal"]


def test_realtime_service_start_and_shutdown_release_background_task(monkeypatch) -> None:
    """应用生命周期关闭后，监听任务和异步Redis数据客户端都被释放。"""

    async def scenario():
        service = TerminalRealtimeService()
        redis_client = _FakeRedis()
        waiting = asyncio.Event()

        async def fake_listener():
            await waiting.wait()

        monkeypatch.setattr(service, "_create_redis_client", lambda: redis_client)
        monkeypatch.setattr(service, "_listen_updates", fake_listener)

        await service.start()
        assert service.started is True
        listener_task = service._listener_task

        await service.shutdown()
        assert service.started is False
        assert listener_task.done() is True
        assert redis_client.closed is True

    asyncio.run(scenario())


def test_update_during_snapshot_wait_is_pushed_after_snapshot() -> None:
    """切换订阅期间发生的通知会暂存，并在初始快照之后补发。"""

    async def scenario():
        service = TerminalRealtimeService()
        service._data_client = _FakeRedis(
            {"terminal:latest:terminal-1": json.dumps({"terminal_id": "terminal-1"})}
        )
        websocket = _FakeWebSocket()
        connection = await service.register(websocket)
        generation = await service.replace_subscriptions(connection, ["terminal-1"])

        await service.handle_terminal_update("terminal-1")
        await service.enqueue(connection, {"type": "snapshot"}, generation=generation)
        await service.activate_subscription(connection, generation)
        await asyncio.sleep(0)

        assert [message["type"] for message in websocket.messages] == [
            "snapshot",
            "terminal_update",
        ]
        await service.disconnect(connection)

    asyncio.run(scenario())


def test_websocket_protocol_filters_ids_and_replaces_subscription(monkeypatch) -> None:
    """接口立即返回快照，重复 subscribe 使用完整列表替换语义。"""

    async def filter_ids(token, terminal_ids):
        assert token == "valid-token"
        return [item for item in terminal_ids if item != "rejected"], [
            item for item in terminal_ids if item == "rejected"
        ]

    async def get_snapshots(terminal_ids):
        snapshots = [
            {"terminal_id": item, "terminal_status": True, "sensor_list": [], "time": "now"}
            for item in terminal_ids
            if item != "terminal-missing"
        ]
        missing = [item for item in terminal_ids if item == "terminal-missing"]
        return snapshots, missing

    monkeypatch.setattr(terminal_realtime_service, "filter_authorized_terminal_ids", filter_ids)
    monkeypatch.setattr(terminal_realtime_service, "get_snapshots", get_snapshots)
    async def scenario():
        websocket = _ScriptedWebSocket(
            [
            {
                "type": "subscribe",
                "token": "valid-token",
                "terminal_ids": ["terminal-1", "rejected", "terminal-missing", "terminal-1"],
            },
            {"type": "subscribe", "token": "valid-token", "terminal_ids": []},
            ]
        )
        await terminal_realtime_websocket(websocket)

        assert websocket.accepted is True
        response = websocket.messages[0]
        assert response["type"] == "snapshot"
        assert response["terminal_ids"] == ["terminal-1", "terminal-missing"]
        assert response["rejected_terminal_ids"] == ["rejected"]
        assert response["missing_terminal_ids"] == ["terminal-missing"]
        response = websocket.messages[1]
        assert response["terminal_ids"] == []

        assert terminal_realtime_service.connections == set()
        assert terminal_realtime_service.terminal_connections == {}

    asyncio.run(scenario())


def test_invalid_token_clears_existing_subscription(monkeypatch) -> None:
    """重新提交列表时 token 失效，旧订阅必须立即清除。"""

    async def filter_ids(token, terminal_ids):
        if token == "expired":
            raise ValidationError("unauthorized")
        return terminal_ids, []

    async def get_snapshots(terminal_ids):
        return [], terminal_ids

    monkeypatch.setattr(terminal_realtime_service, "filter_authorized_terminal_ids", filter_ids)
    monkeypatch.setattr(terminal_realtime_service, "get_snapshots", get_snapshots)
    async def scenario():
        websocket = _ScriptedWebSocket(
            [
                {"type": "subscribe", "token": "valid", "terminal_ids": ["terminal-1"]},
                {"type": "subscribe", "token": "expired", "terminal_ids": ["terminal-2"]},
            ]
        )
        await terminal_realtime_websocket(websocket)

        assert websocket.messages[0]["terminal_ids"] == ["terminal-1"]
        response = websocket.messages[1]
        assert response["type"] == "error"
        assert response["code"] == "unauthorized"

        assert terminal_realtime_service.terminal_connections == {}

    asyncio.run(scenario())
