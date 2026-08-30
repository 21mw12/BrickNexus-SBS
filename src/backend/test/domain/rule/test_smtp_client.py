from types import SimpleNamespace
from importlib import import_module

import pytest

from app.common.validators import ValidationError
from app.infra.Email.SMTPClient import SMTPClient, config

smtp_module = import_module("app.infra.Email.SMTPClient")


class FakeSMTP:
    def __init__(self, host, port, timeout, **kwargs):
        self.connection = (host, port, timeout, kwargs)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def ehlo(self):
        self.calls.append("ehlo")

    def starttls(self, **kwargs):
        self.calls.append(("starttls", kwargs))

    def login(self, username, password):
        self.calls.append(("login", username, password))

    def send_message(self, message):
        self.calls.append(("send", message))


def _smtp(security="ssl", username=None, password=None):
    return SimpleNamespace(
        enabled=True, host="smtp.example.com", port=465, security=security,
        username=username, password=password, sender_email="sender@example.com",
        sender_name="SmartBuilding", timeout_seconds=9,
    )


@pytest.mark.parametrize("security", ["ssl", "starttls", "none"])
def test_smtp_security_modes(monkeypatch, security):
    monkeypatch.setattr(config, "smtp", _smtp(security))
    clients = []

    def factory(*args, **kwargs):
        client = FakeSMTP(*args, **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(smtp_module.smtplib, "SMTP_SSL", factory)
    monkeypatch.setattr(smtp_module.smtplib, "SMTP", factory)
    SMTPClient.send(["ops@example.com"], "标题", "正文")
    client = clients[0]
    assert client.connection[:3] == ("smtp.example.com", 465, 9)
    assert any(call[0] == "send" for call in client.calls if isinstance(call, tuple))
    assert any(isinstance(call, tuple) and call[0] == "starttls" for call in client.calls) is (security == "starttls")


def test_smtp_optional_auth_and_configuration_errors(monkeypatch):
    monkeypatch.setattr(config, "smtp", _smtp("ssl", "user", "secret"))
    client = FakeSMTP("", 0, 0)
    monkeypatch.setattr(smtp_module.smtplib, "SMTP_SSL", lambda *args, **kwargs: client)
    SMTPClient.send(["ops@example.com"], "subject", "content")
    assert ("login", "user", "secret") in client.calls

    monkeypatch.setattr(config, "smtp", _smtp("ssl", "user", None))
    with pytest.raises(ValidationError, match="both"):
        SMTPClient.validate_config()

    disabled = _smtp()
    disabled.enabled = False
    monkeypatch.setattr(config, "smtp", disabled)
    with pytest.raises(ValidationError, match="disabled"):
        SMTPClient.validate_config()
