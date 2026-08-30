"""Terminal 最新数据 WebSocket API。"""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.common.validators import ValidationError
from app.core.middleware.LogRecorder import get_logger
from app.domain.data.service.TerminalRealtimeService import terminal_realtime_service

logger = get_logger(__name__)

router = APIRouter(tags=["terminal-realtime"])


def _parse_subscribe_message(payload) -> tuple[str, list[str]]:
    """校验客户端订阅消息，并对 Terminal ID 去重且保持原顺序。"""
    if not isinstance(payload, dict):
        raise ValidationError("message must be a JSON object")
    if payload.get("type") != "subscribe":
        raise ValidationError("message type must be subscribe")

    token = payload.get("token")
    if not isinstance(token, str) or not token.strip():
        raise ValidationError("token must be a non-empty string")

    terminal_ids = payload.get("terminal_ids")
    if not isinstance(terminal_ids, list):
        raise ValidationError("terminal_ids must be a list")

    normalized: list[str] = []
    seen: set[str] = set()
    for terminal_id in terminal_ids:
        if not isinstance(terminal_id, str) or not terminal_id.strip():
            raise ValidationError("each terminal_id must be a non-empty string")
        terminal_id = terminal_id.strip()
        if terminal_id not in seen:
            seen.add(terminal_id)
            normalized.append(terminal_id)
    return token.strip(), normalized


@router.websocket("/ws/terminals")
async def terminal_realtime_websocket(websocket: WebSocket):
    """接收完整订阅列表，立即返回快照，并持续推送订阅 Terminal 更新。"""
    await websocket.accept()
    connection = await terminal_realtime_service.register(websocket)

    try:
        while True:
            try:
                payload = await websocket.receive_json()
                token, requested_terminal_ids = _parse_subscribe_message(payload)
            except WebSocketDisconnect:
                raise
            except (ValidationError, json.JSONDecodeError) as exc:
                await terminal_realtime_service.enqueue(
                    connection,
                    {
                        "type": "error",
                        "code": "invalid_message",
                        "message": str(exc),
                    },
                )
                continue

            try:
                accepted, rejected = (
                    await terminal_realtime_service.filter_authorized_terminal_ids(
                        token,
                        requested_terminal_ids,
                    )
                )
            except ValidationError as exc:
                # token 或页面权限失效时必须先清除旧订阅，防止继续接收数据。
                await terminal_realtime_service.clear_subscriptions(connection)
                await terminal_realtime_service.enqueue(
                    connection,
                    {
                        "type": "error",
                        "code": "unauthorized",
                        "message": str(exc),
                    },
                    generation=connection.generation,
                )
                continue
            except Exception as exc:
                logger.exception("Terminal WebSocket 权限查询失败 error=%s", exc)
                await terminal_realtime_service.enqueue(
                    connection,
                    {
                        "type": "error",
                        "code": "internal_error",
                        "message": "subscription validation failed",
                    },
                )
                continue

            # 先登记新订阅但暂停实时推送，确保 snapshot 一定排在新订阅更新之前。
            generation = await terminal_realtime_service.replace_subscriptions(
                connection,
                accepted,
            )
            try:
                snapshots, missing_terminal_ids = await terminal_realtime_service.get_snapshots(
                    accepted
                )
            except Exception as exc:
                logger.exception("Terminal WebSocket 初始快照读取失败 error=%s", exc)
                await terminal_realtime_service.activate_subscription(connection, generation)
                await terminal_realtime_service.enqueue(
                    connection,
                    {
                        "type": "error",
                        "code": "redis_unavailable",
                        "message": "terminal snapshot cache is unavailable",
                    },
                    generation=generation,
                )
                continue

            queued = await terminal_realtime_service.enqueue(
                connection,
                {
                    "type": "snapshot",
                    "terminal_ids": accepted,
                    "rejected_terminal_ids": rejected,
                    "missing_terminal_ids": missing_terminal_ids,
                    "data": snapshots,
                },
                generation=generation,
            )
            if queued:
                await terminal_realtime_service.activate_subscription(connection, generation)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("Terminal WebSocket 接收异常 error=%s", exc)
    finally:
        await terminal_realtime_service.disconnect(connection)
