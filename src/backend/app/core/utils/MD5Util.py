#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/06/08
# @function : MD5加密工具
# @version  : v2.0

import hashlib


class MD5Util:

    DEFAULT_SALT = "SmartBuilding_V2.0"

    @staticmethod
    def encrypt(text: str, salt: str = None) -> str:
        """ 对文本进行带盐 MD5 加密 """
        if text is None:
            raise ValueError("text is required")

        salt = salt if salt is not None else MD5Util.DEFAULT_SALT
        raw = f"{salt}{text}{salt}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def verify(text: str, encrypted: str, salt: str = None) -> bool:
        """ 校验明文和密文是否匹配 """
        return MD5Util.encrypt(text, salt=salt) == encrypted


md5_util = MD5Util()