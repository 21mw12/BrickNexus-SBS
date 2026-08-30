#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/04/23
# @function : API公共返回结构
# @version  : v2.0

import io
import os
from datetime import datetime
from typing import Any, Optional, Dict
from urllib.parse import quote

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel

class BaseResponse(BaseModel):
    """ 基础响应模型 """
    success: bool
    code: int
    message: str
    data: Optional[Any] = None

class Response:
    # =========================
    # 核心构造方法
    # =========================
    @staticmethod
    def _build_response(
        success: bool,
        code: int,
        message: str,
        data: Optional[Any] = None,
        http_status: int = 200,
        extra: Optional[Dict] = None
    ) -> JSONResponse:
        """
        构建统一 JSON 响应
        """
        if extra:
            if data is None:
                data = extra
            elif isinstance(data, dict):
                data.update(extra)
            else:
                data = {"data": data, **extra}

        content = jsonable_encoder(
            BaseResponse(
                success=success,
                code=code,
                message=message,
                data=data
            )
        )

        return JSONResponse(content=content, status_code=http_status)

    # =========================
    # 成功响应
    # =========================
    @staticmethod
    def success(
        data: Any = None,
        message: str = "请求成功",
        code: int = 200,
        **extra
    ) -> JSONResponse:
        return Response._build_response(
            True, code, message, data, 200, extra
        )

    # =========================
    # 错误响应（统一入口）
    # =========================
    @staticmethod
    def error(
        message: str = "请求失败",
        code: int = 400,
        http_status: int = 400,
        data: Any = None,
        **extra
    ) -> JSONResponse:
        return Response._build_response(
            False, code, message, data, http_status, extra
        )

    # =========================
    # 常用错误封装（语义化）
    # =========================
    @staticmethod
    def error_params(message="参数错误", **kwargs):
        return Response.error(message, 400, 400, **kwargs)

    @staticmethod
    def error_forbidden(message="权限不足", **kwargs):
        return Response.error(message, 403, 403, **kwargs)

    @staticmethod
    def error_system(message="系统错误", **kwargs):
        return Response.error(message, 500, 500, **kwargs)

    # =========================
    # 文件名生成（复用）
    # =========================
    @staticmethod
    def _build_content_disposition(
        base_name_en: str,
        base_name_cn: str,
        ext: str
    ) -> str:
        """
        构建 Content-Disposition 头
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        filename_en = f"{base_name_en}_{timestamp}{ext}"
        filename_cn = f"{base_name_cn}_{timestamp}{ext}"
        filename_cn_encoded = quote(filename_cn)

        return (
            f"attachment; filename={filename_en};"
            f"filename*=UTF-8''{filename_cn_encoded}"
        )

    # =========================
    # 流式下载
    # =========================
    @staticmethod
    def stream(
        stream: io.BytesIO,
        media_type: str,
        base_name_en: str = "export",
        base_name_cn: str = "导出文件",
        ext: str = ".xlsx"
    ) -> StreamingResponse:
        return StreamingResponse(
            stream,
            media_type=media_type,
            headers={
                "Content-Disposition": Response._build_content_disposition(
                    base_name_en, base_name_cn, ext
                )
            }
        )

    # =========================
    # 文件下载
    # =========================
    @staticmethod
    def file(
        file_path: str,
        base_name_en: str = "download",
        base_name_cn: str = "下载文件",
        ext: Optional[str] = None,
        media_type: str = "application/octet-stream"
    ) -> FileResponse:
        if ext is None:
            ext = os.path.splitext(file_path)[1]

        return FileResponse(
            path=file_path,
            media_type=media_type,
            headers={
                "Content-Disposition": Response._build_content_disposition(
                    base_name_en, base_name_cn, ext
                )
            }
        )
