"""单进程内、确定顺序的采集事件分发器。"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable, TypeVar

from app.core.middleware.LogRecorder import get_logger

logger = get_logger(__name__)
EventT = TypeVar("EventT")


@dataclass(frozen=True)
class Subscription:
    event_type: type
    handler: Callable
    critical: bool
    priority: int


class CollectionEventBus:
    """关键消费者异常向发布者传播，非关键消费者异常仅记录。"""

    def __init__(self) -> None:
        self._subscriptions: list[Subscription] = []
        self._lock = RLock()

    def subscribe(
        self,
        event_type: type[EventT],
        handler: Callable[[EventT], None],
        *,
        critical: bool,
        priority: int = 100,
    ) -> Subscription:
        subscription = Subscription(event_type, handler, critical, priority)
        with self._lock:
            if subscription not in self._subscriptions:
                self._subscriptions.append(subscription)
                self._subscriptions.sort(key=lambda item: item.priority)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        with self._lock:
            if subscription in self._subscriptions:
                self._subscriptions.remove(subscription)

    def publish(self, event: object) -> None:
        with self._lock:
            subscriptions = tuple(
                item for item in self._subscriptions if isinstance(event, item.event_type)
            )
        for subscription in subscriptions:
            try:
                subscription.handler(event)
            except Exception as exc:
                if subscription.critical:
                    raise
                logger.exception(
                    "非关键采集事件消费者失败 consumer=%s event=%s error=%s",
                    getattr(subscription.handler, "__qualname__", repr(subscription.handler)),
                    type(event).__name__,
                    exc,
                )


collection_event_bus = CollectionEventBus()
