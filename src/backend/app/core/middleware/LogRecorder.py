#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/04/22
# @function : 日志记录器
# @version  : v2.0
"""
# 使用 logger
# logger = get_logger()
# logger.debug("这是一个 DEBUG 日志")
# logger.info("这是一个 INFO 日志")
# logger.warning("这是一个 WARNING 日志")
# logger.error("这是一个 ERROR 日志")
# logger.critical("这是一个 CRITICAL 日志")
"""

import logging
import os
from logging import Logger
from logging.handlers import TimedRotatingFileHandler

from app.core.config.ConfigLoader import config
from app.common.EnvLoader import get_env_settings

env_settings = get_env_settings()

def _setup_logger(
        name: str,
        console_show_level: str = None,
        file_show_level: str = None,
        log_to_file: bool = None,
        log_dir: str = None
) -> Logger:
    """
    设置日志器（按天滚动）
    :param name: 日志器名称
    :param console_show_level: 控制台显示日志的最小等级（如 "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"）
    :param file_show_level: 文件显示日志的最小等级（如 "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"）
    :param log_to_file: 是否输出到文件
    :param log_dir: 日志目录，默认是 log/
    :return: 配置好的 Logger 对象
    """
    # 使用配置默认值（避免函数定义时绑定）
    console_show_level = console_show_level or config.log.console_show_level
    file_show_level = file_show_level or config.log.file_show_level
    log_to_file = log_to_file if log_to_file is not None else config.log.to_file
    log_path = env_settings.log_dir

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # 防止重复添加 handler
    if logger.handlers:
        return logger

    # 日志格式设置
    formatter = logging.Formatter(
        fmt=config.log.item_fmt,
        datefmt=config.log.item_date
    )

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, console_show_level.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出
    if log_to_file:
        os.makedirs(log_path, exist_ok=True)

        # 固定文件名，让 handler 管滚动
        log_file = log_path / "app.log"

        file_handler = TimedRotatingFileHandler(
            str(log_file),
            when="midnight",
            interval=1,
            backupCount=getattr(config.log, "backup_count", 7),
            encoding="utf-8"
        )

        # 切割后的文件名
        file_handler.suffix = config.log.file_fmt + "%Y-%m-%d.log"

        file_handler.setLevel(getattr(logging, file_show_level.upper(), logging.DEBUG))
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

    return logger

def get_logger(name=None):
    import inspect

    if name is None:
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
        name = module.__name__ if module else "unknown"

    return _setup_logger(name)
