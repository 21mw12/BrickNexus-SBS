"""Fernet encryption for MQTT channel credentials."""

import os

from app.common.validators import ValidationError


class ChannelCipher:
    # 项目固定密钥。修改该值后，数据库中已经加密的 MQTT 密码将无法解密。
    # 支持环境变量 SMARTBUILDING_FERNET_KEY 覆盖；未设置时回退到内置默认值，
    # 以保证历史已加密的 MQTT 密码仍可解密。
    FERNET_KEY = os.getenv("SMARTBUILDING_FERNET_KEY", "").encode() or b"ViFvW5GtpwUP-jKytYzIqRW17UuOIuU8M82X4wpsRoQ="

    @classmethod
    def _fernet(cls):
        try:
            from cryptography.fernet import Fernet
            return Fernet(cls.FERNET_KEY)
        except ImportError as exc:
            raise RuntimeError("cryptography dependency is not installed") from exc
        except Exception as exc:
            raise ValidationError("the built-in MQTT Fernet key is invalid") from exc

    @classmethod
    def encrypt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return cls._fernet().encrypt(value.encode("utf-8")).decode("ascii")

    @classmethod
    def decrypt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return cls._fernet().decrypt(value.encode("ascii")).decode("utf-8")
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError("MQTT channel password cannot be decrypted with the configured key") from exc
