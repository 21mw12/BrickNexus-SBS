"""API 与 MQTT 共用的测量时间解析。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from jsonpath_ng.exceptions import JsonPathLexerError, JsonPathParserError
from jsonpath_ng.ext import parse as parse_json_path

from app.core.config.ConfigLoader import config


class TimeParser:
    """按照 Request 时间配置解析响应；失败时返回系统时间。"""

    _FORMAT_TOKENS = (
        ("yyyy", "%Y"),
        ("yy", "%y"),
        ("MM", "%m"),
        ("dd", "%d"),
        ("hh", "%H"),
        ("mm", "%M"),
        ("ss", "%S"),
    )

    def __init__(self) -> None:
        # 配置错误应在应用加载阶段暴露，避免静默使用错误时区。
        self.default_timezone = ZoneInfo(config.time.default_timezone)

    def _parse_value(self, value, time_parse: str) -> datetime:
        """ 解析时间值 """
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            raise ValueError("time value must be a string or datetime")

        if time_parse:
            # HH 格式暂不支持，避免与 hh 冲突
            if "HH" in time_parse:
                raise ValueError("time_parse uses hh for 24-hour time")
            python_format = time_parse
            for source, target in self._FORMAT_TOKENS:
                python_format = python_format.replace(source, target)
            return datetime.strptime(value, python_format)

        # ISO 8601 格式，支持 Z 结尾的 UTC 时间
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        return datetime.fromisoformat(normalized)

    def parse(self, response_data, time_json_path: str, time_parse: str, system_time: datetime | None = None) -> datetime:
        """
        提取并解析响应时间；无配置、路径错误或格式错误都使用系统时间。
        :param response_data: HTTP 响应 JSON 数据
        :param time_json_path: JSONPath 表达式
        :param time_parse: 时间格式化字符串
        :param system_time: 系统时间，默认为 None 时使用配置的默认时区
        :return: 解析后的时间，带时区信息
        """
        # 1. 解析时间，失败时使用系统时间
        fallback = system_time or datetime.now(self.default_timezone)
        if fallback.tzinfo is None:
            fallback = fallback.replace(tzinfo=self.default_timezone)
        if not time_json_path:
            return fallback

        # 2. 使用 JSONPath 提取时间字符串，并解析为 datetime 对象
        try:
            matches = parse_json_path(time_json_path).find(response_data)
            if len(matches) != 1:
                return fallback
            parsed_time = self._parse_value(matches[0].value, time_parse)
            if parsed_time.tzinfo is None:
                parsed_time = parsed_time.replace(tzinfo=self.default_timezone)
            return parsed_time
        except (JsonPathLexerError, JsonPathParserError, TypeError, ValueError):
            return fallback


time_parser = TimeParser()
