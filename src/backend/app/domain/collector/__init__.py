"""独立采集领域的公共出口。"""

from .RuntimeManager import collector_runtime
from .loader import request_loader

__all__ = [
    "collector_runtime",
    "request_loader",
]
