from email.headerregistry import Address
from typing import Any, Callable, Dict


class ValidationError(ValueError):
    pass


def validate_email_address(value: str) -> str:
    """使用标准库校验单个 addr-spec，不接受显示名或空白。"""
    if not isinstance(value, str) or not value or value != value.strip() or "@" not in value:
        raise ValueError("invalid email address")
    if len(value) > 254 or any(character.isspace() for character in value):
        raise ValueError("invalid email address")
    try:
        address = Address(addr_spec=value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid email address") from exc
    if address.addr_spec != value:
        raise ValueError("invalid email address")
    return value


def validate_str(value: Any, field: str, max_len: int) -> None:
    if value is None:
        raise ValidationError(f"{field} is required")
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string")
    if not value.strip():
        raise ValidationError(f"{field} cannot be empty")
    if len(value) > max_len:
        raise ValidationError(f"{field} length must be <= {max_len}")


def validate_int(value: Any, field: str, min_value: int = 0) -> None:
    if value is None:
        raise ValidationError(f"{field} is required")
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{field} must be an int")
    if value < min_value:
        raise ValidationError(f"{field} must be >= {min_value}")


def validate_bool(value: Any, field: str) -> None:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be a bool")


def validate_update(values: Dict[str, Any], rules: Dict[str, Callable[[Any], None]]) -> None:
    for key, value in values.items():
        if key == "asset_id":
            continue
        validator = rules.get(key)
        if validator:
            validator(value)
