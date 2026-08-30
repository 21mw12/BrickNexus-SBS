#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/06/08
# @function : Redis连接管理
# @version  : v1.0
import re
import redis
from typing import Any, Optional

from app.core.config.ConfigLoader import config


class RedisManager:

    @staticmethod
    def _create_pool_with_compat(kwargs: dict) -> redis.ConnectionPool:
        """兼容不同 redis-py 版本：遇到不支持参数时自动剔除并重试。"""
        pool_kwargs = dict(kwargs)
        while True:
            try:
                return redis.ConnectionPool(**pool_kwargs)
            except TypeError as e:
                match = re.search(r"unexpected keyword argument '([^']+)'", str(e))
                if not match:
                    raise

                bad_key = match.group(1)
                if bad_key not in pool_kwargs:
                    raise

                pool_kwargs.pop(bad_key)

    def __init__(self):
        if redis is None:
            raise RuntimeError("redis package is required, please install redis-py first")

        self.redis_config = config.redis
        # 基础连接参数
        pool_kwargs = {
            "host": self.redis_config.host,
            "port": self.redis_config.port,
            "db": self.redis_config.db,
            "password": self.redis_config.password or None,
            "username": self.redis_config.username or None,
            "decode_responses": self.redis_config.decode_responses,
            "max_connections": self.redis_config.max_connections,
            "socket_timeout": self.redis_config.socket_timeout,
            "health_check_interval": self.redis_config.health_check_interval,
        }
        # 处理 ssl 参数：如果为 False 则不传递（避免老版本报错），为 True 则传递
        if self.redis_config.ssl:
            pool_kwargs["ssl"] = True
            # 可选：如果还有 ssl_cert_reqs 等参数，也可以加入
        # 其他参数原样保留，交给兼容函数处理
        self.pool = self._create_pool_with_compat(pool_kwargs)
        self.client = redis.Redis(connection_pool=self.pool)

    def get_client(self):
        return self.client

    def ping(self) -> bool:
        return bool(self.client.ping())

    def get(self, key: str) -> Any:
        return self.client.get(key)

    def set(self, key: str, value: Any, ex: Optional[int] = None, nx: bool = False, xx: bool = False) -> bool:
        return bool(self.client.set(key, value, ex=ex, nx=nx, xx=xx))

    def delete(self, *keys: str) -> int:
        return self.client.delete(*keys)

    def exists(self, *keys: str) -> int:
        return self.client.exists(*keys)

    def expire(self, key: str, seconds: int) -> bool:
        return bool(self.client.expire(key, seconds))

    def hget(self, name: str, key: str) -> Any:
        return self.client.hget(name, key)

    def hset(self, name: str, key: str, value: Any) -> int:
        return self.client.hset(name, key, value)

    def hgetall(self, name: str):
        return self.client.hgetall(name)

    def publish(self, channel: str, message: str) -> int:
        """发布终端最新值更新通知。"""
        return int(self.client.publish(channel, message))

    def pipeline(self, transaction: bool = True):
        """创建 Redis Pipeline，用于将快照写入和更新通知按顺序提交。"""
        return self.client.pipeline(transaction=transaction)

    def close(self):
        self.pool.disconnect()


redis_manager = RedisManager()
