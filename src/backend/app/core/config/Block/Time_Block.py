"""采集时间相关配置。"""

from dataclasses import dataclass


@dataclass
class TimeBlock:
    """未携带时区的设备时间所使用的默认时区。"""

    default_timezone: str = "Asia/Shanghai"
