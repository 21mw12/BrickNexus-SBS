#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/04/22
# @function : 读取yaml文件配置数据库
# @version  : v2.0

from typing import Dict
from dataclasses import dataclass

@dataclass
class DataBaseBlock:
    type: str                   # 使用的数据库类型（mysql |　postgresql）
    host: str                   # 服务IP地址
    port: int                   # 服务端口
    username: str               # 用户名
    password: str               # 密码
    db_names: Dict[str, str]    # 逻辑数据库名

    def get_db_name(self, key: str = "main") -> str:
        return self.db_names.get(key)
