"""HTTP Request 加载、定时调度、解析和采集事件发布。"""

import random
from datetime import datetime

from app.core.middleware.LogRecorder import get_logger
from app.core.utils.HTTPRequestor import HttpUtil
from app.domain.channel.repository.models.Request import Request
from app.infra.Scheduler.SchedulerManager import scheduler

from ..event import (
    CollectionRequestStoppedEvent,
    CollectionStatusEvent,
    MeasurementBatchEvent,
    MeasurementValue,
    PointParseError,
    points_from_request_data,
)
from ..event_bus import collection_event_bus
from ..parser.data_parser import data_parser
from ..parser.time_parser import time_parser
from ..storage.request_state_storage import request_state_storage
from .request_data_loader import request_data_loader

logger = get_logger(__name__)


class HttpRequestLoader:
    """为每个 HTTP Request 创建一个按配置周期执行的定时任务。"""

    def __init__(self) -> None:
        # requests 保存后续解析响应时需要的终端和测点结构。
        self.requests: dict[str, dict] = {}
        # request_info 保存 HTTP 请求需要的 method、url、headers 等配置。
        self.request_info: dict[str, dict] = {}
        # JSONPath 在 Request 启动时预编译，定时响应到达后直接执行匹配。
        self.json_paths: dict[str, dict[str, object | None]] = {}
        # HTTP 连续失败次数只属于当前进程，成功一次后清零。
        self.failure_counts: dict[str, int] = {}

    @staticmethod
    def task_id(request_id: str) -> str:
        return f"collector:http:{request_id}"

    def start(self, request: Request) -> dict:
        """
        加载数据结构，并根据 interval_seconds 注册 HTTP 定时任务。
        返回 request_data 供后续解析响应使用。
        """
        # 1. 检查 request_info 中的 interval_seconds 是否有效
        request_id = request.request_id
        info = dict(request.request_info or {})
        interval_seconds = info.get("interval_seconds", 60)
        if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, (int, float)):
            raise ValueError("interval_seconds must be a number")
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than 0")

        # 2. 加载 request_data
        request_data = request_data_loader.load(request_id)
        self.requests[request_id] = request_data
        self.request_info[request_id] = info
        self.json_paths[request_id] = data_parser.compile_json_paths(request_data["point_list"])
        self.failure_counts[request_id] = 0

        # 3. 首次执行增加随机偏移，避免应用启动后全部 HTTP 请求同时发起。
        initial_delay = random.uniform(0, interval_seconds)
        scheduler.add_task(
            self.task_id(request_id),
            lambda request_id=request_id: self.execute_request(request_id),
            interval_seconds=interval_seconds,
            initial_delay_seconds=initial_delay,
        )

        logger.info(
            "HTTP Request 定时任务已创建 request_id=%s interval_seconds=%s",
            request_id,
            interval_seconds,
        )
        return request_data

    def update_point_descriptions(self, descriptions: dict[str, str | None]) -> int:
        """刷新已加载 HTTP Request 的实例测点说明。"""
        updated = 0
        for request_data in self.requests.values():
            for point in request_data["point_list"]:
                if point["point_id"] in descriptions:
                    point["point_description"] = descriptions[point["point_id"]]
                    updated += 1
        return updated

    def execute_request(self, request_id: str) -> None:
        """ 定时任务到期后发送 HTTP 请求，成功响应交给解析占位方法。 """
        # 1. 获取 request_info 和 request_data
        info = self.request_info.get(request_id)
        request_data = self.requests.get(request_id)
        if info is None or request_data is None:
            logger.warning("HTTP Request 未加载 request_id=%s", request_id)
            return

        # 2. 发送 HTTP 请求
        method = str(info.get("method", "GET")).upper()
        url = info.get("url")
        if method not in {"GET", "POST"}:
            logger.error("HTTP Request method 不支持 request_id=%s method=%s", request_id, method)
            self._record_failure(request_id, request_data)
            return
        if not isinstance(url, str) or not url:
            logger.error("HTTP Request 缺少 url request_id=%s", request_id)
            self._record_failure(request_id, request_data)
            return
        try:
            success, response_data = HttpUtil._request(
                method=method,
                url=url,
                headers=info.get("headers"),
                params=info.get("params"),
                json=info.get("body") if method == "POST" else None,
                timeout=info.get("timeout_seconds", 20),
                return_json=True,
            )
        except Exception as exc:
            logger.exception("HTTP Request 请求异常 request_id=%s error=%s", request_id, exc)
            self._record_failure(request_id, request_data)
            return
        if not success:
            logger.warning("HTTP Request 请求失败 request_id=%s error=%s", request_id, response_data)
            self._record_failure(request_id, request_data)
            return
        logger.info("HTTP Request 请求成功 request_id=%s response=%s", request_id, response_data)

        # 3. HTTP、解析和关键 data 消费者全部完成后，才把本次执行视为成功。
        try:
            measurement_time = time_parser.parse(
                response_data,
                request_data["time_json_path"],
                request_data["time_parse"],
            )
            self.parse_response(request_id, response_data, request_data, measurement_time)
        except Exception as exc:
            logger.exception("HTTP Request 数据处理失败 request_id=%s error=%s", request_id, exc)
            self._record_failure(request_id, request_data)
            return

        self.failure_counts[request_id] = 0

    def parse_response(self, request_id: str, response_data, request_data: dict, measurement_time: datetime) -> dict:
        """
        按 Point JSONPath 解析数值，并批量更新 Terminal/Sensor 在线状态。
        :param request_id: HTTP Request ID
        :param response_data: HTTP 响应 JSON 数据
        :param request_data: 解析所需的终端和测点结构
        :param measurement_time: 采集时间
        :return: 解析结果，包括 measurements、sensor_statuses 和 measurement_time
        """
        # 1. 解析响应数据
        parsed_data = data_parser.parse(
            response_data,
            request_data["point_list"],
            self.json_paths.get(request_id, {}),
        )
        measurements = parsed_data["measurements"]
        sensor_statuses = parsed_data["sensor_statuses"]
        for error in parsed_data["errors"]:
            logger.warning(
                "HTTP Point 解析失败 request_id=%s point_id=%s error=%s",
                request_id,
                error["point_id"],
                error["error"],
            )

        # 配置了 Point 但全部解析失败时，整个 Request 本次执行判定为失败。
        if request_data["point_list"] and not measurements:
            raise ValueError("all points failed to parse")

        # 2. 发布不可变采集事件；data 是关键消费者，失败会传播到调用方。
        for measurement in measurements:
            measurement["time"] = measurement_time
        collection_event_bus.publish(
            MeasurementBatchEvent(
                request_id=request_id,
                request_type="http",
                occurred_at=measurement_time,
                terminal_ids=tuple(request_data["terminal_list"]),
                points=points_from_request_data(request_data),
                measurements=tuple(
                    MeasurementValue(
                        point_id=item["point_id"],
                        sensor_id=item["sensor_id"],
                        terminal_id=item["terminal_id"],
                        value=item["value"],
                    )
                    for item in measurements
                ),
                sensor_statuses=tuple(sorted(sensor_statuses.items())),
                parse_errors=tuple(
                    PointParseError(point_id=item["point_id"], error=item["error"])
                    for item in parsed_data["errors"]
                ),
            )
        )

        return {
            "measurements": measurements,
            "sensor_statuses": sensor_statuses,
            "measurement_time": measurement_time,
        }

    def stop(self, request_id: str) -> None:
        """移除一个 HTTP Request 的定时任务和内存配置。"""
        existed = request_id in self.requests
        scheduler.remove_task(self.task_id(request_id))
        self.requests.pop(request_id, None)
        self.request_info.pop(request_id, None)
        self.json_paths.pop(request_id, None)
        self.failure_counts.pop(request_id, None)
        if existed:
            collection_event_bus.publish(CollectionRequestStoppedEvent(request_id=request_id))

    def stop_all(self) -> None:
        """移除全部 HTTP Request 定时任务。"""
        for request_id in tuple(self.requests):
            self.stop(request_id)

    def _record_failure(self, request_id: str, request_data: dict) -> None:
        """HTTP 失败时立即设离线；连续三次完整请求失败后自动停用。"""
        failure_count = self.failure_counts.get(request_id, 0) + 1
        self.failure_counts[request_id] = failure_count
        try:
            now = datetime.now(time_parser.default_timezone)
            sensor_ids = {point["sensor_id"] for point in request_data["point_list"]}
            collection_event_bus.publish(
                CollectionStatusEvent(
                    request_id=request_id,
                    occurred_at=now,
                    terminal_ids=tuple(request_data["terminal_list"]),
                    points=points_from_request_data(request_data),
                    sensor_statuses=tuple((sensor_id, False) for sensor_id in sorted(sensor_ids)),
                    terminal_online=False,
                )
            )
        except Exception as exc:
            logger.exception("HTTP 离线状态更新失败 request_id=%s error=%s", request_id, exc)

        if failure_count >= 3:
            logger.error(
                "HTTP Request 连续三次失败，停止任务 request_id=%s",
                request_id,
            )
            try:
                request_state_storage.deactivate(request_id)
            except Exception as exc:
                logger.exception(
                    "HTTP Request 停用状态写入失败 request_id=%s error=%s",
                    request_id,
                    exc,
                )
            finally:
                self.stop(request_id)
