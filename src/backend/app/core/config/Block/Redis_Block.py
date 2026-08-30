#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/06/08
# @function : 读取yaml文件配置Redis
# @version  : v1.0

from dataclasses import dataclass


@dataclass
class RedisBlock:
    host: str                   # 服务IP地址
    port: int                   # 服务端口
    db: int                     # Redis数据库编号
    password: str | None = None # 密码
    username: str | None = None # 用户名
    decode_responses: bool = True
    max_connections: int = 20
    socket_timeout: int = 5
    health_check_interval: int = 30
    ssl: bool = False