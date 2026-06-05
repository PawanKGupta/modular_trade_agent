import logging

from server.app.core.config import settings
from services.email_notifier import EmailNotifier

logger = logging.getLogger(__name__)

FORGOT_PASSWORD_SUBJECT = "Reset your Rebound password"
VERIFY_EMAIL_SUBJECT = "Verify your Rebound email"


class AuthEmailService:
    """Send auth-related emails via configured SMTP (e.g. Gmail)."""

    def __init__(self, notifier: EmailNotifier | None = None):
        self._notifier = notifier or EmailNotifier()

    def _base_url(self) -> str:
        return settings.frontend_base_url.rstrip("/")

    def send_password_reset_email(self, to_email: str, token: str) -> bool:
        reset_url = f"{self._base_url()}/reset-password?token={token}"
        plain = (
            "You requested a password reset for your Rebound account.\n\n"
            f"Reset your password: {reset_url}\n\n"
            "This link expires in 1 hour. If you did not request this, ignore this email.\n\n"
            "---\nRebound — Modular Trade Agent"
        )
        return self._send(to_email, FORGOT_PASSWORD_SUBJECT, plain, token, "password reset")

    def send_verification_email(self, to_email: str, token: str) -> bool:
        verify_url = f"{self._base_url()}/verify-email?token={token}"
        plain = (
            "Welcome to Rebound. Please verify your email address.\n\n"
            f"Verify email: {verify_url}\n\n"
            "---\nRebound — Modular Trade Agent"
        )
        return self._send(to_email, VERIFY_EMAIL_SUBJECT, plain, token, "email verification")

    def _send(
        self,
        to_email: str,
        subject: str,
        plain: str,
        token: str,
        purpose: str,
    ) -> bool:
        if not self._notifier.is_available():
            logger.warning(
                "SMTP not configured; %s token for %s (dev only): %s",
                purpose,
                to_email,
                token,
            )
            return False
        return self._notifier.send_email(to_email, subject, plain, is_html=False)
