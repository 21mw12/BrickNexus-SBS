#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/06/08
# @function : JWT工具
# @version  : v1.0

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional


class JWTUtil:

    DEFAULT_SECRET = os.getenv("SMARTBUILDING_JWT_SECRET") or "SmartBuilding_V2.0.JWT.SECRET"
    DEFAULT_EXPIRE_SECONDS = 24 * 60 * 60

    @staticmethod
    def _base64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

    @staticmethod
    def _base64url_decode(text: str) -> bytes:
        padding = "=" * (-len(text) % 4)
        return base64.urlsafe_b64decode(text + padding)

    @staticmethod
    def encode(payload: Dict[str, Any], secret: str = None, expires_in: int = None) -> str:
        secret = secret or JWTUtil.DEFAULT_SECRET
        expires_in = expires_in or JWTUtil.DEFAULT_EXPIRE_SECONDS

        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        body = dict(payload)
        body.setdefault("iat", now)
        body["exp"] = now + expires_in

        header_part = JWTUtil._base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_part = JWTUtil._base64url_encode(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{header_part}.{payload_part}".encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        signature_part = JWTUtil._base64url_encode(signature)
        return f"{header_part}.{payload_part}.{signature_part}"

    @staticmethod
    def decode(token: str, secret: str = None) -> Dict[str, Any]:
        secret = secret or JWTUtil.DEFAULT_SECRET
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("invalid token")

        header_part, payload_part, signature_part = parts
        signing_input = f"{header_part}.{payload_part}".encode("utf-8")
        expected_signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if JWTUtil._base64url_encode(expected_signature) != signature_part:
            raise ValueError("invalid token signature")

        payload = json.loads(JWTUtil._base64url_decode(payload_part).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("token expired")

        return payload


jwt_util = JWTUtil()