import os
import pytest

@pytest.mark.security
def test_telegram_notifier_does_not_log_token(monkeypatch, caplog):
    # Set a fake token and chat id in env
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "FAKE_TOKEN_SHOULD_NOT_APPEAR")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    # Stub core.telegram.send_telegram to avoid network and to inspect inputs
    calls = {}

    def fake_send_telegram(msg: str):
        calls["message"] = msg
        return True

    import src.infrastructure.notifications.telegram_notifier as notifier_mod
    monkeypatch.setattr(notifier_mod, "send_telegram", fake_send_telegram)

    from src.infrastructure.notifications.telegram_notifier import TelegramNotifier

    caplog.set_level("INFO")
    tn = TelegramNotifier()
    ok = tn.send_alert("hello world")

    assert ok is True
    # Ensure the token is not leaked in logs
    assert "FAKE_TOKEN_SHOULD_NOT_APPEAR" not in caplog.text
    # And message went through the stub
    assert calls.get("message") == "hello world"