#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/04/22
# @function : UUID生成器
# @version  : v2.0

import uuid

class UUIDGenerator:

    @staticmethod
    def random():
        """ 生成随机的UUID """
        return str(uuid.uuid4())

    @staticmethod
    def from_name(name: str):
        """ 生成固定的UUID """
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))

uuid_generator = UUIDGenerator()