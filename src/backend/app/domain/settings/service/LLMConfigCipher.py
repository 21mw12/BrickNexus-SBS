"""Encryption boundary for LLM provider credentials."""

import os

from app.common.validators import ValidationError


class LLMConfigCipher:
    # Reuse the deployment key already used for encrypted channel credentials.
    FERNET_KEY = os.getenv("SMARTBUILDING_FERNET_KEY", "").encode() or b"ViFvW5GtpwUP-jKytYzIqRW17UuOIuU8M82X4wpsRoQ="

    @classmethod
    def _fernet(cls):
        try:
            from cryptography.fernet import Fernet
            return Fernet(cls.FERNET_KEY)
        except ImportError as exc:
            raise RuntimeError("cryptography dependency is not installed") from exc
        except Exception as exc:
            raise ValidationError("the configured Fernet key is invalid") from exc

    @classmethod
    def encrypt(cls, value: str) -> str:
        return cls._fernet().encrypt(value.encode("utf-8")).decode("ascii")

    @classmethod
    def decrypt(cls, value: str) -> str:
        try:
            return cls._fernet().decrypt(value.encode("ascii")).decode("utf-8")
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError("LLM API key cannot be decrypted with the configured key") from exc

