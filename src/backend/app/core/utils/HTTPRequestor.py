#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/04/22
# @function : HTTP请求器
# @version  : v2.0

import requests
from typing import Optional, Dict, Any, Tuple, Union


class HttpUtil:
    """
    统一 HTTP 工具类：
    - 支持 GET / POST / PUT / DELETE
    - 支持 JSON / 表单 / 文件
    - 统一返回格式 (success, data)
    - 自动异常处理
    """

    DEFAULT_TIMEOUT = 10.0

    @staticmethod
    def _request(
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str]] = None,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = None,
        return_json: bool = True,
    ) -> Tuple[bool, Any]:
        """
        通用请求入口
        """
        timeout = timeout or HttpUtil.DEFAULT_TIMEOUT

        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                params=params,
                data=data,
                json=json,
                files=files,
                headers=headers,
                timeout=timeout,
            )

            # 状态码校验
            if not response.ok:
                return (
                    False,
                    f"HTTP {response.status_code}：{response.text}"
                )

            # 返回 JSON or 原始 response
            if return_json:
                try:
                    return True, response.json()
                except ValueError:
                    return False, f"返回数据不是 JSON 格式"

            return True, response

        except requests.exceptions.Timeout:
            return False, f"请求超时"

        except requests.exceptions.ConnectionError:
            return False, f"连接失败"

        except requests.exceptions.RequestException as e:
            return False, f"请求异常：{str(e)}"

    @staticmethod
    def get(
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = None,
    ):
        return HttpUtil._request(
            "GET",
            url,
            params=params,
            headers=headers,
            timeout=timeout,
        )

    @staticmethod
    def post(
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str]] = None,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = None,
    ):
        return HttpUtil._request(
            "POST",
            url,
            params=params,
            data=data,
            json=json,
            files=files,
            headers=headers,
            timeout=timeout,
        )

    @staticmethod
    def put(
        url: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = None,
    ):
        return HttpUtil._request(
            "PUT",
            url,
            json=json,
            headers=headers,
            timeout=timeout,
        )

    @staticmethod
    def delete(
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = None,
    ):
        return HttpUtil._request(
            "DELETE",
            url,
            headers=headers,
            timeout=timeout,
        )