from dataclasses import dataclass


@dataclass
class SMTPBlock:
    """规则邮件动作使用的全局 SMTP 配置。"""

    enabled: bool = False
    host: str = ""
    port: int = 465
    security: str = "ssl"
    username: str | None = None
    password: str | None = None
    sender_email: str = ""
    sender_name: str = "SmartBuilding"
    timeout_seconds: int = 20
