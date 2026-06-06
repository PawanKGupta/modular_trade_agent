"""In-memory AuthEmailService stand-in for pytest (no outbound SMTP)."""

from __future__ import annotations

from types import SimpleNamespace

_sent_state = SimpleNamespace(reset=[], verify=[])


def reset_auth_email_sent() -> SimpleNamespace:
    """Reset and return the shared sent-email tracker."""
    _sent_state.reset.clear()
    _sent_state.verify.clear()
    return _sent_state


def get_auth_email_sent() -> SimpleNamespace:
    """Return the current sent-email tracker."""
    return _sent_state


def install_mock_auth_email_service(monkeypatch) -> SimpleNamespace:
    """
    Patch auth routes to use a no-op email service and clear SMTP env vars.

    Returns a tracker with ``reset`` and ``verify`` lists of (email, token) tuples.
    """
    sent = reset_auth_email_sent()

    class MockAuthEmailService:
        """Records auth emails in memory; never connects to SMTP."""

        def __init__(self, *args, **kwargs):
            pass

        def is_smtp_configured(self) -> bool:
            return True

        def send_password_reset_email(self, to_email: str, token: str) -> bool:
            sent.reset.append((to_email, token))
            return True

        def send_verification_email(self, to_email: str, token: str) -> bool:
            sent.verify.append((to_email, token))
            return True

    monkeypatch.setattr(
        "server.app.routers.auth.AuthEmailService",
        MockAuthEmailService,
    )
    for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM_EMAIL"):
        monkeypatch.delenv(key, raising=False)
    return sent
