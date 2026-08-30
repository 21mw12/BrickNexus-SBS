"""采集运行时启动顺序测试。"""

import asyncio

from app.domain.collector import RuntimeManager as runtime_module
from app.domain.collector.RuntimeManager import CollectorRuntimeManager


class _FakeScheduler:
    def __init__(self, calls: list[str] | None = None) -> None:
        self.started = False
        self.stopped = False
        self.calls = calls

    def start(self) -> None:
        self.started = True
        if self.calls is not None:
            self.calls.append("scheduler_start")

    def shutdown(self) -> None:
        self.stopped = True
        if self.calls is not None:
            self.calls.append("scheduler_shutdown")


class _FakeRealtimeService:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    async def start(self) -> None:
        self.calls.append("realtime_start")

    async def shutdown(self) -> None:
        self.calls.append("realtime_shutdown")


class _FakeDataConsumer:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def start(self) -> None:
        self.calls.append("data_start")

    def shutdown(self) -> None:
        self.calls.append("data_shutdown")


def test_runtime_starts_scheduler_before_loading_requests(monkeypatch) -> None:
    calls = []
    scheduler = _FakeScheduler(calls)

    def load_active_requests():
        assert scheduler.started is True
        calls.append("load")
        return {"http": [], "mqtt": []}

    monkeypatch.setattr(runtime_module.request_loader, "load_active_requests", load_active_requests)
    monkeypatch.setattr(runtime_module.request_loader, "stop_all", lambda: calls.append("stop_all"))
    runtime = CollectorRuntimeManager(
        scheduler_manager=scheduler,
        realtime_service=_FakeRealtimeService(calls),
        data_consumer=_FakeDataConsumer(calls),
    )

    asyncio.run(runtime.start())
    asyncio.run(runtime.shutdown())

    assert calls == [
        "data_start",
        "realtime_start",
        "scheduler_start",
        "load",
        "stop_all",
        "scheduler_shutdown",
        "data_shutdown",
        "realtime_shutdown",
    ]
    assert scheduler.stopped is True


def test_runtime_closes_scheduler_when_request_loading_fails(monkeypatch) -> None:
    calls = []
    scheduler = _FakeScheduler(calls)
    stopped = []
    monkeypatch.setattr(
        runtime_module.request_loader,
        "load_active_requests",
        lambda: (_ for _ in ()).throw(RuntimeError("load failed")),
    )
    monkeypatch.setattr(runtime_module.request_loader, "stop_all", lambda: stopped.append(True))
    runtime = CollectorRuntimeManager(
        scheduler_manager=scheduler,
        realtime_service=_FakeRealtimeService(calls),
        data_consumer=_FakeDataConsumer(calls),
    )

    try:
        asyncio.run(runtime.start())
    except RuntimeError as exc:
        assert str(exc) == "load failed"
    else:
        raise AssertionError("RuntimeError was not raised")

    assert scheduler.stopped is True
    assert stopped == [True]
    assert calls == [
        "data_start",
        "realtime_start",
        "scheduler_start",
        "scheduler_shutdown",
        "data_shutdown",
        "realtime_shutdown",
    ]
