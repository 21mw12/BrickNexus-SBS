"""MQTT Request 按 Broker 分组加载、订阅、解析和采集事件发布。"""

import json
from datetime import datetime, timedelta, timezone
from math import isfinite
from threading import RLock

from app.core.middleware.LogRecorder import get_logger
from app.domain.channel.repository.models.Request import Request
from app.infra.MQTT import (
    MQTTClientFactory,
    MQTTConnectionOptions,
    mqtt_result_code,
    subscribe_checked,
)
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


class MqttRequestLoader:
    """同一 Broker 只维护一个连接，并合并该 Broker 下的全部 Topic。"""

    # 全部 MQTT Request 共用一个轻量检查任务，不为每个 Topic 单独创建定时任务。
    HEALTH_TASK_ID = "collector:mqtt:health"

    def __init__(self, client_factory: MQTTClientFactory | None = None) -> None:
        self._client_factory = client_factory or MQTTClientFactory()
        # request_id -> 当前 Request 的 Broker、Topic 和解析结构。
        self.requests: dict[str, dict] = {}
        # address -> MQTT Client、认证配置和 Topic 映射。
        self.brokers: dict[str, dict] = {}
        # JSONPath 在 Request 启动时预编译，定时响应到达后直接执行匹配。
        self.json_paths: dict[str, dict[str, object | None]] = {}
        # 锁保护 brokers、requests 和 json_paths 的并发访问，避免回调线程和主线程冲突。
        self._lock = RLock()
        # 记录本 Loader 是否已经登记 MQTT 健康检查任务。
        self._health_task_started = False

    def start(self, request: Request) -> dict:
        """
        加载 MQTT Request，并创建或复用对应 Broker 连接。
        返回 request_data 供后续解析响应使用。
        """
        # 1. 检查 request_info 中的 address、topic、qos 是否有效
        request_id = request.request_id
        info = dict(request.request_info or {})
        address, host, port = self._parse_address(info.get("address"))
        broker_key = info.get("channel_id") or address
        topic = info.get("topic")
        if not isinstance(topic, str) or not topic:
            raise ValueError("topic is required")
        qos = info.get("qos", 0)
        if isinstance(qos, bool) or not isinstance(qos, int) or qos not in {0, 1, 2}:
            raise ValueError("qos must be 0, 1 or 2")
        username = info.get("username")
        password = info.get("password")
        connect_timeout = self._positive_seconds(
            info.get("connect_timeout_second", info.get("connect_timeout_seconds", 20)),
            "connect_timeout_second",
        )
        data_timeout = self._positive_seconds(info.get("data_timeout", 60), "data_timeout")
        storage_interval_value = info.get("storage_interval_seconds")
        storage_interval = (
            self._positive_seconds(storage_interval_value, "storage_interval_seconds")
            if storage_interval_value is not None
            else None
        )
        started_at = datetime.now(timezone.utc)

        # 2. 加载 request_data 和 JSONPath
        request_data = request_data_loader.load(request_id)
        compiled_paths = data_parser.compile_json_paths(request_data["point_list"])

        # 3. 重复启动时先移除旧的 Topic 关系，保证 Request 只登记一次。
        self.stop(request_id)
        with self._lock:
            broker = self.brokers.get(broker_key)
            is_new_broker = broker is None
            # 4.1. 如果是新 Broker，创建 Client 并保存连接信息
            if broker is None:
                client = self._client_factory.create(
                    MQTTConnectionOptions(
                        host=host,
                        port=port,
                        client_id=info.get("client_id"),
                        username=username,
                        password=password,
                        keepalive=60,
                    )
                )
                broker = {
                    "client": client,
                    "host": host,
                    "port": port,
                    "username": username,
                    "password": password,
                    "connected": False,
                    # connect_async 只发起连接，回调成功前由健康检查计算连接耗时。
                    "connection_started_at": started_at,
                    "topics": {},
                }
                self._set_callbacks(client, broker_key)
                self.brokers[broker_key] = broker
            # 4.2.如果是已存在的 Broker，检查用户名密码是否一致
            elif broker["username"] != username or broker["password"] != password:
                raise ValueError("requests using the same MQTT address must use the same credentials")

            # 5.1. 如果是新 Topic，创建 Topic 数据并保存 request_id
            topic_data = broker["topics"].get(topic)
            is_new_topic = topic_data is None
            if topic_data is None:
                topic_data = {"qos": qos, "request_ids": set()}
                broker["topics"][topic] = topic_data
                qos_changed = False
            # 5.2. 如果是已存在的 Topic，更新 qos 为最大值，并检查是否变更。
            else:
                old_qos = topic_data["qos"]
                topic_data["qos"] = max(topic_data["qos"], qos)
                qos_changed = topic_data["qos"] != old_qos
            topic_data["request_ids"].add(request_id)

            # 6. 保存 Request 的 Broker、Topic 和解析结构
            self.requests[request_id] = {
                "address": address,
                "broker_key": broker_key,
                "topic": topic,
                "qos": qos,
                "request_data": request_data,
                "connect_timeout": connect_timeout,
                "data_timeout": data_timeout,
                # 存储策略随采集事件传给 data 消费者，collector 不保存待写数据。
                "storage_interval": storage_interval,
                "started_at": started_at,
                # 已连接 Broker 上新增的 Request 从加入时开始等待首条消息；
                # 未连接 Broker 则等 on_connect 后再开始计算 data_timeout。
                "data_wait_started_at": started_at if broker["connected"] else None,
                "last_message_at": None,
                "offline_marked": False,
                "fatal_error_reason": None,
            }
            self.json_paths[request_id] = compiled_paths

            # 7.1. 如果是新 Broker，启动异步连接和网络循环
            if is_new_broker:
                try:
                    self._connect(broker, broker_key)
                except Exception:
                    self.requests.pop(request_id, None)
                    self.json_paths.pop(request_id, None)
                    raise
            # 7.2. 如果是已连接的 Broker 且 Topic 是新订阅或 qos 变更，则订阅该 Topic
            elif broker["connected"] and (is_new_topic or qos_changed):
                try:
                    subscribe_checked(broker["client"], topic, topic_data["qos"])
                except Exception as exc:
                    # 与异步 on_connect 保持一致，由健康检查完成离线和停用。
                    self._queue_request_error(
                        (request_id,),
                        f"MQTT Topic 订阅失败: {topic}",
                    )
                    logger.error(
                        "MQTT Topic 订阅失败 address=%s topic=%s error=%s",
                        address,
                        topic,
                        exc,
                    )

            # 8. 所有 Broker 共用一个每秒执行的超时检查任务。
            if not self._health_task_started:
                scheduler.add_task(
                    self.HEALTH_TASK_ID,
                    self.health_check,
                    interval_seconds=1,
                )
                self._health_task_started = True

        logger.info("MQTT Request 已加载 request_id=%s address=%s topic=%s", request_id, address, topic)
        return request_data

    def update_point_descriptions(self, descriptions: dict[str, str | None]) -> int:
        """在 Loader 锁内刷新已加载 MQTT Request 的实例测点说明。"""
        updated = 0
        with self._lock:
            for request in self.requests.values():
                for point in request["request_data"]["point_list"]:
                    if point["point_id"] in descriptions:
                        point["point_description"] = descriptions[point["point_id"]]
                        updated += 1
        return updated

    def stop(self, request_id: str) -> None:
        """移除一个 Request；最后一个 Topic 移除后关闭 Broker 连接。"""
        remove_health_task = False
        unsubscribe_action = None
        close_client = None
        with self._lock:
            # 1. 移除 Request 的 Broker、Topic 和解析结构
            request = self.requests.pop(request_id, None)
            self.json_paths.pop(request_id, None)
            if request is None:
                return

            # 2. 移除 Broker 下的 Topic 和 request_id；如果没有 Topic 则关闭连接
            broker_key = request.get("broker_key", request["address"])
            topic = request["topic"]
            broker = self.brokers.get(broker_key)
            if broker is not None:
                # 3. 移除该 Topic 下的 request_id，如果没有 request_id 则取消订阅并删除 Topic
                topic_data = broker["topics"].get(topic)
                if topic_data is not None:
                    topic_data["request_ids"].discard(request_id)
                    if not topic_data["request_ids"]:
                        # MQTT 网络操作不能在 Loader 锁内执行。Paho 的 loop_stop 会
                        # 等待网络线程，而网络线程的 on_disconnect 回调也需要这把锁。
                        if broker["connected"]:
                            unsubscribe_action = (broker["client"], topic)
                        broker["topics"].pop(topic, None)

                # 4. 如果没有 Topic，先从内存中摘除 Broker，再在锁外关闭连接。
                # 这样断开回调能够立即获得锁，不会与 loop_stop 互相等待。
                if not broker["topics"]:
                    close_client = broker["client"]
                    unsubscribe_action = None
                    self.brokers.pop(broker_key, None)

            # 最后一个 MQTT Request 停止后，同时移除共用健康检查任务。
            if not self.requests and self._health_task_started:
                self._health_task_started = False
                remove_health_task = True

        # 5. Paho 调用全部放在锁外，避免网络回调线程与停用线程形成死锁。
        if unsubscribe_action is not None:
            client, removed_topic = unsubscribe_action
            try:
                client.unsubscribe(removed_topic)
            except Exception as exc:
                logger.exception(
                    "MQTT Topic 取消订阅失败 request_id=%s topic=%s error=%s",
                    request_id,
                    removed_topic,
                    exc,
                )

        if close_client is not None:
            try:
                close_client.disconnect()
            except Exception as exc:
                logger.exception(
                    "MQTT Broker 断开失败 request_id=%s error=%s",
                    request_id,
                    exc,
                )
            finally:
                try:
                    close_client.loop_stop()
                except Exception as exc:
                    logger.exception(
                        "MQTT Broker 网络循环停止失败 request_id=%s error=%s",
                        request_id,
                        exc,
                    )

        if remove_health_task:
            scheduler.remove_task(self.HEALTH_TASK_ID)

        collection_event_bus.publish(CollectionRequestStoppedEvent(request_id=request_id))
        logger.info("MQTT Request 已停止 request_id=%s", request_id)

    def stop_all(self) -> None:
        """停止全部 Request，并释放所有 Broker 连接。"""
        for request_id in tuple(self.requests):
            self.stop(request_id)

    def _set_callbacks(self, client, address: str) -> None:
        """回调只保存 address，通过 address 找到对应 Broker 和 Topic。"""
        client.on_connect = (
            lambda mqtt_client, userdata, flags, rc, properties=None:
            self._on_connect(address, rc)
        )
        client.on_disconnect = (
            lambda mqtt_client, userdata, rc, properties=None:
            self._on_disconnect(address, rc)
        )
        client.on_message = (
            lambda mqtt_client, userdata, message:
            self._on_message(address, message.topic, message.payload)
        )

    def _connect(self, broker: dict, address: str) -> None:
        """启动一个 Broker 的异步连接和网络循环。"""
        try:
            broker["client"].connect_async(broker["host"], broker["port"], keepalive=60)
            broker["client"].loop_start()
        except Exception:
            self.brokers.pop(address, None)
            raise

    def _on_connect(self, address: str, rc) -> None:
        """连接成功后一次性订阅该 Broker 当前登记的全部 Topic。"""
        if mqtt_result_code(rc) != 0:
            failed_request_ids = ()
            with self._lock:
                broker = self.brokers.get(address)
                if broker is not None:
                    broker["connected"] = False
                    broker["connection_started_at"] = (
                        broker.get("connection_started_at") or datetime.now(timezone.utc)
                    )
                    # 认证失败属于确定性错误，无需继续等待连接超时。
                    if mqtt_result_code(rc) in {4, 5}:
                        failed_request_ids = tuple(
                            request_id
                            for topic_data in broker["topics"].values()
                            for request_id in topic_data["request_ids"]
                        )
            logger.error("MQTT Broker 连接失败 address=%s rc=%s", address, rc)
            self._queue_request_error(failed_request_ids, "MQTT 身份认证失败")
            return
        failed_subscriptions: list[tuple[str, str]] = []
        with self._lock:
            broker = self.brokers.get(address)
            if broker is None:
                return
            connected_at = datetime.now(timezone.utc)
            broker["connected"] = True
            broker["connection_started_at"] = None
            for request in self.requests.values():
                if request.get("broker_key", request["address"]) == address:
                    request["data_wait_started_at"] = connected_at
            topics = [
                (topic, topic_data["qos"])
                for topic, topic_data in broker["topics"].items()
            ]
            for topic, qos in topics:
                try:
                    subscribe_checked(broker["client"], topic, qos)
                except Exception as exc:
                    logger.error(
                        "MQTT Topic 订阅失败 address=%s topic=%s error=%s",
                        address,
                        topic,
                        exc,
                    )
                    failed_subscriptions.extend(
                        (request_id, f"MQTT Topic 订阅失败: {topic}")
                        for request_id in broker["topics"][topic]["request_ids"]
                    )
        for request_id, reason in failed_subscriptions:
            self._queue_request_error((request_id,), reason)
        logger.info("MQTT Broker 连接成功 address=%s topics=%s", address, len(topics))

    def _on_disconnect(self, address: str, rc) -> None:
        with self._lock:
            broker = self.brokers.get(address)
            # 主动停止时 Broker 已经从内存摘除，不需要再更新或记录异常断线。
            if broker is None:
                return
            broker["connected"] = False
            # 断线后 paho 会继续重连，从此刻重新计算连接超时时间。
            broker["connection_started_at"] = datetime.now(timezone.utc)
        logger.warning("MQTT Broker 连接断开 address=%s rc=%s", address, rc)

    def _on_message(self, address: str, topic: str, raw_payload) -> None:
        """将 Topic 消息只分发给该 Broker、该 Topic 下登记的 Request。"""
        with self._lock:
            broker = self.brokers.get(address)
            topic_data = broker["topics"].get(topic) if broker else None
            request_ids = tuple(topic_data["request_ids"]) if topic_data else ()

            # 收到消息即刷新等待时间；JSON 内容无效只影响 Sensor 解析状态。
            received_at = datetime.now(timezone.utc)
            for request_id in request_ids:
                request = self.requests.get(request_id)
                if request is not None:
                    request["last_message_at"] = received_at
                    request["offline_marked"] = False
                    request["fatal_error_reason"] = None

        try:
            text = raw_payload.decode("utf-8") if isinstance(raw_payload, bytes) else raw_payload
            response_data = json.loads(text)
        except (UnicodeDecodeError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("MQTT 消息不是有效 JSON address=%s topic=%s error=%s", address, topic, exc)
            for request_id in request_ids:
                self._mark_message_parse_failed(request_id)
            return

        for request_id in request_ids:
            try:
                self._process_message(request_id, response_data)
            except Exception as exc:
                logger.exception("MQTT 消息处理失败 request_id=%s error=%s", request_id, exc)

    def _process_message(self, request_id: str, response_data) -> dict | None:
        """复用公共解析器和存储器处理一个 MQTT Request 的消息。"""
        request = self.requests.get(request_id)
        if request is None:
            return None
        request_data = request["request_data"]
        measurement_time = time_parser.parse(
            response_data,
            request_data["time_json_path"],
            request_data["time_parse"],
        )
        parsed_data = data_parser.parse(
            response_data,
            request_data["point_list"],
            self.json_paths.get(request_id, {}),
        )
        measurements = parsed_data["measurements"]
        sensor_statuses = parsed_data["sensor_statuses"]
        for measurement in measurements:
            measurement["time"] = measurement_time
        for error in parsed_data["errors"]:
            logger.warning(
                "MQTT Point 解析失败 request_id=%s point_id=%s error=%s",
                request_id,
                error["point_id"],
                error["error"],
            )

        collection_event_bus.publish(
            MeasurementBatchEvent(
                request_id=request_id,
                request_type="mqtt",
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
                storage_interval_seconds=request["storage_interval"],
            )
        )
        return {
            "measurements": measurements,
            "sensor_statuses": sensor_statuses,
            "measurement_time": measurement_time,
        }

    def _mark_message_parse_failed(self, request_id: str) -> None:
        """收到非 JSON 消息时 Terminal 在线，但全部 Sensor 解析失败。"""
        request = self.requests.get(request_id)
        if request is None:
            return
        request_data = request["request_data"]
        sensor_ids = {point["sensor_id"] for point in request_data["point_list"]}
        sensor_statuses = {sensor_id: False for sensor_id in sensor_ids}
        now = datetime.now(time_parser.default_timezone)
        collection_event_bus.publish(
            CollectionStatusEvent(
                request_id=request_id,
                occurred_at=now,
                terminal_ids=tuple(request_data["terminal_list"]),
                points=points_from_request_data(request_data),
                sensor_statuses=tuple(sorted(sensor_statuses.items())),
                terminal_online=True,
            )
        )

    def health_check(self) -> None:
        """检查 MQTT 连接和数据接收异常。"""
        now = datetime.now(timezone.utc)
        timed_out: list[tuple[str, str]] = []

        with self._lock:
            for request_id, request in self.requests.items():
                if request["offline_marked"]:
                    continue

                if request["fatal_error_reason"]:
                    timed_out.append((request_id, request["fatal_error_reason"]))
                    continue

                broker = self.brokers.get(request.get("broker_key", request["address"]))
                if broker is None:
                    timed_out.append((request_id, "Broker 不存在"))
                    continue

                if not broker["connected"]:
                    connection_started_at = broker.get("connection_started_at") or request["started_at"]
                    # Request 可能在共享连接已经开始后才加入，不能把加入前的时间算给它。
                    connection_started_at = max(connection_started_at, request["started_at"])
                    if now - connection_started_at >= timedelta(seconds=request["connect_timeout"]):
                        timed_out.append((request_id, "MQTT 连接超时"))
                    continue

                last_received_at = (
                    request["last_message_at"]
                    or request["data_wait_started_at"]
                    or request["started_at"]
                )
                if now - last_received_at >= timedelta(seconds=request["data_timeout"]):
                    timed_out.append((request_id, "MQTT 数据接收超时"))

        for request_id, reason in timed_out:
            self._mark_request_offline(
                request_id,
                reason,
                datetime.now(time_parser.default_timezone),
            )

    def _mark_request_offline(self, request_id: str, reason: str, status_time: datetime) -> None:
        """异常时设置资产离线、持久化停用状态并移除对应 MQTT Request。"""
        with self._lock:
            request = self.requests.get(request_id)
            if request is None or request["offline_marked"]:
                return
            request_data = request["request_data"]

        try:
            sensor_ids = {point["sensor_id"] for point in request_data["point_list"]}
            collection_event_bus.publish(
                CollectionStatusEvent(
                    request_id=request_id,
                    occurred_at=status_time,
                    terminal_ids=tuple(request_data["terminal_list"]),
                    points=points_from_request_data(request_data),
                    sensor_statuses=tuple((sensor_id, False) for sensor_id in sorted(sensor_ids)),
                    terminal_online=False,
                )
            )
        except Exception as exc:
            logger.exception(
                "MQTT 离线状态更新失败 request_id=%s reason=%s error=%s",
                request_id,
                reason,
                exc,
            )
        try:
            request_state_storage.deactivate(request_id)
        except Exception as exc:
            logger.exception(
                "MQTT Request 停用状态写入失败 request_id=%s error=%s",
                request_id,
                exc,
            )
        finally:
            # 即使状态存储失败，也必须释放当前进程中的 Topic 和 Broker 资源。
            self.stop(request_id)
        logger.warning("MQTT Request 已因异常停止 request_id=%s reason=%s", request_id, reason)

    def _queue_request_error(self, request_ids, reason: str) -> None:
        """回调线程只登记致命错误，实际停止操作交给健康检查任务执行。"""
        with self._lock:
            for request_id in request_ids:
                request = self.requests.get(request_id)
                if request is not None:
                    request["fatal_error_reason"] = reason

    @staticmethod
    def _positive_seconds(value, field_name: str) -> float:
        """校验 request_info 中的超时秒数，布尔值不能作为数字使用。"""
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{field_name} must be greater than 0")
        return float(value)

    @staticmethod
    def _parse_address(value) -> tuple[str, str, int]:
        """将 address 规范为 host:port，未写端口时使用 1883。"""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("address is required")
        value = value.strip()
        if ":" in value:
            host, port_text = value.rsplit(":", 1)
            try:
                port = int(port_text)
            except ValueError as exc:
                raise ValueError("MQTT port must be an integer") from exc
        else:
            host, port = value, 1883
        if not host or not 1 <= port <= 65535:
            raise ValueError("MQTT address is invalid")
        return f"{host}:{port}", host, port
