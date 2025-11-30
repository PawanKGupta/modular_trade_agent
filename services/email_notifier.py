"""
Email Notifier Service

Service for sending email notifications.
Supports SMTP configuration via environment variables.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.logger import logger


class EmailNotifier:
    """
    Service for sending email notifications via SMTP.

    Configuration via environment variables:
    - SMTP_HOST: SMTP server hostname (e.g., smtp.gmail.com)
    - SMTP_PORT: SMTP server port (default: 587 for TLS)
    - SMTP_USER: SMTP username/email
    - SMTP_PASSWORD: SMTP password or app password
    - SMTP_FROM_EMAIL: From email address (defaults to SMTP_USER)
    - SMTP_USE_TLS: Use TLS encryption (default: True)
    """

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        smtp_from_email: str | None = None,
        smtp_use_tls: bool = True,
    ):
        """
        Initialize email notifier.

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_user: SMTP username/email
            smtp_password: SMTP password
            smtp_from_email: From email address
            smtp_use_tls: Use TLS encryption
        """
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.smtp_from_email = smtp_from_email or os.getenv("SMTP_FROM_EMAIL") or self.smtp_user
        self.smtp_use_tls = (
            smtp_use_tls
            if smtp_use_tls is not None
            else os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        )

        self.enabled = bool(self.smtp_host and self.smtp_user and self.smtp_password)

        if not self.enabled:
            logger.warning(
                "Email notifier disabled: SMTP configuration missing. "
                "Set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD environment variables."
            )
        else:
            logger.info("Email notifier initialized and enabled")

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        is_html: bool = False,
    ) -> bool:
        """
        Send an email notification.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body (plain text or HTML)
            is_html: Whether body is HTML (default: False)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Email notifier is disabled, skipping email send")
            return False

        if not to_email:
            logger.warning("No recipient email address provided")
            return False

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = self.smtp_from_email
            msg["To"] = to_email
            msg["Subject"] = subject

            # Add body
            if is_html:
                msg.attach(MIMEText(body, "html"))
            else:
                msg.attach(MIMEText(body, "plain"))

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def send_service_notification(
        self,
        to_email: str,
        title: str,
        message: str,
        level: str = "info",
    ) -> bool:
        """
        Send a service event notification email.

        Args:
            to_email: Recipient email address
            title: Notification title
            message: Notification message
            level: Notification level (info, warning, error, critical)

        Returns:
            True if sent successfully, False otherwise
        """
        # Format subject
        level_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨",
        }
        emoji = level_emoji.get(level, "ℹ️")
        subject = f"{emoji} {title} - Rebound"

        # Format body
        body = f"""
{title}

{message}

---
Rebound — Modular Trade Agent
This is an automated message. Please do not reply.
        """.strip()

        return self.send_email(to_email=to_email, subject=subject, body=body)

    def is_available(self) -> bool:
        """
        Check if email notifier is available and configured.

        Returns:
            True if email notifier is enabled and configured
        """
        return self.enabled
