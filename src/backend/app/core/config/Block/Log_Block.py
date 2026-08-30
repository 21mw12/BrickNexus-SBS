#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/04/22
# @function : 读取yaml文件配置日志
# @version  : v1.0

from dataclasses import dataclass

@dataclass
class LogBlock:
    console_show_level: str # 控制台显示的最低日志等级
    file_show_level: str    # 日志文件保存的最低日志等级
    to_file: bool           # 是否保存到日志文件
    file_fmt: str           # 日志文件格式
    item_fmt: str           # 日志每项格式
    item_date: str          # 日志每项时间格式