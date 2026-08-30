from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.common.validators import ValidationError, validate_email_address
from app.core.config.ConfigLoader import config


class SMTPClient:
    """使用 config.yaml 中的单一账号发送规则纯文本邮件。"""

    @staticmethod
    def validate_config() -> None:
        smtp = config.smtp
        if not smtp.enabled:
            raise ValidationError("SMTP is disabled")
        if not isinstance(smtp.host, str) or not smtp.host.strip():
            raise ValidationError("SMTP host is required")
        if not isinstance(smtp.port, int) or isinstance(smtp.port, bool) or not 1 <= smtp.port <= 65535:
            raise ValidationError("SMTP port must be between 1 and 65535")
        if smtp.security not in {"none", "starttls", "ssl"}:
            raise ValidationError("SMTP security must be none, starttls or ssl")
        if not isinstance(smtp.timeout_seconds, int) or smtp.timeout_seconds <= 0:
            raise ValidationError("SMTP timeout_seconds must be greater than 0")
        try:
            validate_email_address(smtp.sender_email)
        except ValueError as exc:
            raise ValidationError(f"invalid SMTP sender_email: {exc}") from exc
        if (smtp.username is None) != (smtp.password is None):
            raise ValidationError("SMTP username and password must both be configured or both be null")

    @classmethod
    def send(cls, recipients: list[str], subject: str, content: str) -> None:
        cls.validate_config()
        smtp = config.smtp
        message = EmailMessage()
        message["From"] = formataddr((smtp.sender_name, smtp.sender_email))
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(content, subtype="plain", charset="utf-8")

        context = ssl.create_default_context()
        if smtp.security == "ssl":
            client = smtplib.SMTP_SSL(
                smtp.host, smtp.port, timeout=smtp.timeout_seconds, context=context
            )
        else:
            client = smtplib.SMTP(smtp.host, smtp.port, timeout=smtp.timeout_seconds)
        with client:
            if smtp.security == "starttls":
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
            if smtp.username is not None:
                client.login(smtp.username, smtp.password)
            client.send_message(message)


smtp_client = SMTPClient()
