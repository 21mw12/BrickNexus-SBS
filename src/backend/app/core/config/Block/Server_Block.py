#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/04/22
# @function : 读取yaml文件配置服务
# @version  : v1.0

from dataclasses import dataclass

@dataclass
class ServerBlock:
    host: str
    port: int
    version: str
