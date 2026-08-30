#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/04/22
# @function : 读取并加载yaml配置文件
# @version  : v2.0

import os

import yaml
from dataclasses import dataclass

from .Block import *
from app.common.EnvLoader import get_env_settings

env_settings = get_env_settings()

@dataclass
class GlobalConfig:
    server: ServerBlock
    log: LogBlock
    db: DataBaseBlock
    redis: RedisBlock
    time: TimeBlock
    smtp: SMTPBlock


def load_config() -> GlobalConfig:
    with open(env_settings.config_path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)

    # 加载数据库配置模块的内容（环境变量优先，yaml 作为默认值）
    db_raw = raw.get("database", {})
    db_names_raw = db_raw.get("db_names")
    db_names = db_names_raw or {}
    if os.getenv("DB_NAME"):
        db_names["main"] = os.getenv("DB_NAME")
    db_config = DataBaseBlock(
        type=os.getenv("DB_TYPE", db_raw.get("type")),
        host=os.getenv("DB_HOST", db_raw.get("host")),
        port=int(os.getenv("DB_PORT", db_raw.get("port"))),
        username=os.getenv("DB_USER", db_raw.get("username")),
        password=os.getenv("DB_PASSWORD", db_raw.get("password")),
        db_names=db_names,
    )

    # 加载Redis配置模块的内容（环境变量优先，yaml 作为默认值）
    redis_raw = raw.get("redis", {})
    redis_config = RedisBlock(
        host=os.getenv("REDIS_HOST", redis_raw.get("host")),
        port=int(os.getenv("REDIS_PORT", redis_raw.get("port"))),
        db=int(os.getenv("REDIS_DB", redis_raw.get("db", 0))),
        password=os.getenv("REDIS_PASSWORD", redis_raw.get("password")),
        username=redis_raw.get("username"),
        decode_responses=redis_raw.get("decode_responses", True),
        max_connections=redis_raw.get("max_connections", 20),
        socket_timeout=redis_raw.get("socket_timeout", 5),
        health_check_interval=redis_raw.get("health_check_interval", 30),
        ssl=redis_raw.get("ssl", False),
    )

    return GlobalConfig(
        server=ServerBlock(**raw.get("server", {})),
        log=LogBlock(**raw.get("log", {})),
        db=db_config,
        redis=redis_config,
        time=TimeBlock(**raw.get("time", {})),
        smtp=SMTPBlock(**raw.get("smtp", {})),
    )

# 加载成全局变量
config: GlobalConfig = load_config()
