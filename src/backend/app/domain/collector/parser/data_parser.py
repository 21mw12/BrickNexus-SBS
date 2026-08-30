"""API 与 MQTT 共用的 Point JSONPath 数据解析。"""

import math

from jsonpath_ng.exceptions import JsonPathLexerError, JsonPathParserError
from jsonpath_ng.ext import parse as parse_json_path


class DataParser:
    """将响应数据解析为测点值和 Sensor 在线状态。"""

    @staticmethod
    def compile_json_paths(point_list: list[dict]) -> dict[str, object | None]:
        """Request 启动时预编译 JSONPath，避免每次响应重复编译。"""
        compiled_paths = {}
        for point in point_list:
            json_path = point.get("json_path")
            try:
                compiled_paths[point["point_id"]] = (
                    parse_json_path(json_path) if isinstance(json_path, str) and json_path else None
                )
            except (JsonPathLexerError, JsonPathParserError):
                compiled_paths[point["point_id"]] = None
        return compiled_paths

    @staticmethod
    def _parse_number(value) -> float:
        if isinstance(value, bool):
            raise ValueError("boolean is not a measurement value")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("value is not numeric") from exc
        if not math.isfinite(number):
            raise ValueError("value must be finite")
        return number

    def parse(self, response_data, point_list: list[dict], compiled_paths: dict[str, object | None]) -> dict:
        """
        解析全部 Point；一个 Sensor 只要有一个 Point 成功就认为在线。
        :param response_data: HTTP 响应 JSON 数据
        :param point_list: 解析所需的终端和测点结构
        :param compiled_paths: 预编译的 JSONPath 表达式
        :return: 解析结果，包括 measurements、sensor_statuses 和 errors
        """
        measurements = []
        sensor_statuses: dict[str, bool] = {}
        errors = []

        for point in point_list:
            point_id = point["point_id"]
            sensor_id = point["sensor_id"]
            # Sensor 默认离线，任意 Point 成功后改为在线，后续失败不再覆盖。
            sensor_statuses.setdefault(sensor_id, False)
            expression = compiled_paths.get(point_id)
            try:
                if expression is None:
                    raise ValueError("json_path is invalid")
                
                # 解析 JSONPath，要求匹配到唯一值，否则报错。
                matches = expression.find(response_data)
                if len(matches) != 1:
                    raise ValueError("json_path must match exactly one value")
                
                # 解析数值，要求是有限的浮点数，否则报错。
                value = self._parse_number(matches[0].value)

                # 解析成功，记录测点值和 Sensor 在线状态。
                measurements.append(
                    {
                        "point_id": point_id,
                        "sensor_id": sensor_id,
                        "terminal_id": point["terminal_id"],
                        "value": value,
                    }
                )
                sensor_statuses[sensor_id] = True

            except (TypeError, ValueError) as exc:
                errors.append({"point_id": point_id, "error": str(exc)})

        return {
            "measurements": measurements,
            "sensor_statuses": sensor_statuses,
            "errors": errors,
        }

data_parser = DataParser()
