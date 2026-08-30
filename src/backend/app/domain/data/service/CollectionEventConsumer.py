"""采集事件的关键 data 消费者。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock

from app.core.middleware.LogRecorder import get_logger
from app.domain.collector.event import (
    CollectionRequestStartedEvent,
    CollectionRequestStoppedEvent,
    CollectionStatusEvent,
    MeasurementBatchEvent,
    request_data_from_event,
)
from app.domain.collector.event_bus import CollectionEventBus, collection_event_bus
from app.domain.data.storage.redis_storage import redis_storage
from app.domain.data.storage.sql_storage import sql_storage
from app.domain.data.storage.status_storage import status_storage
from app.infra.Scheduler.SchedulerManager import scheduler

logger = get_logger(__name__)


class MeasurementPersistenceRuntime:
    """保留 MQTT 固定周期最后一批数据，并在到期时写入 SQL。"""

    TASK_ID = "data:measurement-persistence"

    def __init__(self) -> None:
        self._requests: dict[str, dict] = {}
        self._lock = RLock()
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        scheduler.add_task(self.TASK_ID, self.flush_due, interval_seconds=1)
        self._started = True

    def shutdown(self) -> None:
        scheduler.remove_task(self.TASK_ID)
        with self._lock:
            self._requests.clear()
        self._started = False

    def register(self, event: CollectionRequestStartedEvent) -> None:
        interval = event.storage_interval_seconds
        with self._lock:
            self._requests[event.request_id] = {
                "storage_interval": interval,
                "next_storage_at": (
                    event.started_at + timedelta(seconds=interval)
                    if interval is not None
                    else None
                ),
                "pending_measurements": None,
            }

    def unregister(self, request_id: str) -> None:
        # 保持原语义：Request 停止时未到期批次直接丢弃。
        with self._lock:
            self._requests.pop(request_id, None)

    def persist_or_buffer(self, event: MeasurementBatchEvent, rows: list[dict]) -> None:
        with self._lock:
            state = self._requests.get(event.request_id)
            interval = event.storage_interval_seconds
            if state is None:
                state = {
                    "storage_interval": interval,
                    "next_storage_at": (
                        datetime.now(timezone.utc) + timedelta(seconds=interval)
                        if interval is not None
                        else None
                    ),
                    "pending_measurements": None,
                }
                self._requests[event.request_id] = state
            if state["storage_interval"] is not None:
                state["pending_measurements"] = [dict(row) for row in rows]
                return
        sql_storage.save(rows)

    def flush_due(self) -> None:
        now = datetime.now(timezone.utc)
        due: list[tuple[str, list[dict]]] = []
        with self._lock:
            for request_id, state in self._requests.items():
                interval = state["storage_interval"]
                next_at = state["next_storage_at"]
                if interval is None or next_at is None or now < next_at:
                    continue
                elapsed = (now - next_at).total_seconds()
                periods = int(elapsed // interval) + 1
                state["next_storage_at"] = next_at + timedelta(seconds=periods * interval)
                rows = state["pending_measurements"]
                state["pending_measurements"] = None
                if rows:
                    due.append((request_id, rows))

        for request_id, rows in due:
            try:
                sql_storage.save(rows)
            except Exception as exc:
                logger.exception(
                    "MQTT 周期数据写入失败 request_id=%s error=%s",
                    request_id,
                    exc,
                )
                with self._lock:
                    state = self._requests.get(request_id)
                    if state is not None and state["pending_measurements"] is None:
                        state["pending_measurements"] = rows
                        state["next_storage_at"] = min(state["next_storage_at"], now)


class CollectionDataConsumer:
    """先完成状态、SQL、Redis存储，再允许后续规则消费者执行。"""

    def __init__(
        self,
        bus: CollectionEventBus = collection_event_bus,
        persistence: MeasurementPersistenceRuntime | None = None,
    ) -> None:
        self.bus = bus
        self.persistence = persistence or MeasurementPersistenceRuntime()
        self._subscriptions = []

    def start(self) -> None:
        if self._subscriptions:
            return
        self._subscriptions = [
            self.bus.subscribe(MeasurementBatchEvent, self.consume_measurements, critical=True, priority=0),
            self.bus.subscribe(CollectionStatusEvent, self.consume_status, critical=True, priority=0),
            self.bus.subscribe(CollectionRequestStartedEvent, self.persistence.register, critical=True, priority=0),
            self.bus.subscribe(
                CollectionRequestStoppedEvent,
                lambda event: self.persistence.unregister(event.request_id),
                critical=True,
                priority=0,
            ),
        ]
        self.persistence.start()

    def shutdown(self) -> None:
        for subscription in self._subscriptions:
            self.bus.unsubscribe(subscription)
        self._subscriptions.clear()
        self.persistence.shutdown()

    def consume_measurements(self, event: MeasurementBatchEvent) -> None:
        request_data = request_data_from_event(event)
        sensor_statuses = dict(event.sensor_statuses)
        rows = [
            {
                "point_id": item.point_id,
                "sensor_id": item.sensor_id,
                "terminal_id": item.terminal_id,
                "value": item.value,
                "time": event.occurred_at,
            }
            for item in event.measurements
        ]
        status_storage.update_online_statuses(
            list(event.terminal_ids),
            sensor_statuses,
            event.occurred_at,
        )
        self.persistence.persist_or_buffer(event, rows)
        redis_storage.save(
            request_data,
            rows,
            sensor_statuses,
            terminal_status=True,
            measurement_time=event.occurred_at,
        )

    def consume_status(self, event: CollectionStatusEvent) -> None:
        request_data = request_data_from_event(event)
        sensor_statuses = dict(event.sensor_statuses)
        if event.terminal_online:
            status_storage.update_online_statuses(
                list(event.terminal_ids),
                sensor_statuses,
                event.occurred_at,
            )
            redis_storage.save(
                request_data,
                measurements=[],
                sensor_statuses=sensor_statuses,
                terminal_status=True,
                measurement_time=event.occurred_at,
            )
        else:
            status_storage.set_all_offline(request_data, event.occurred_at)


collection_data_consumer = CollectionDataConsumer()
