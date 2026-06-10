"""
Multi-channel trading notification dispatcher (PR2).

Delivers order events to Telegram, in-app, and email based on per-channel
user preferences and quiet hours. Failures are logged only — never raises.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from modules.kotak_neo_auto_trader.telegram_notifier import TelegramNotifier
    from services.notification_preference_service import NotificationPreferenceService

logger = logging.getLogger(__name__)

NotificationLevel = Literal["info", "warning", "error", "critical"]


def dispatch_trading_notification(
    *,
    user_id: int | None,
    event_type: str,
    title: str,
    message_plain: str,
    telegram_notifier: TelegramNotifier | None = None,
    telegram_body: str | None = None,
    db_session: Session | None = None,
    preference_service: NotificationPreferenceService | None = None,
    level: NotificationLevel = "info",
) -> bool:
    """
    Send a trading notification on all enabled channels.

    Returns True if Telegram was sent successfully (backward-compatible with
    legacy ``TelegramNotifier.notify_*`` return values).
    """
    body_for_telegram = telegram_body or message_plain

    # Legacy path: no user context — Telegram only (preference service unavailable).
    if user_id is None or preference_service is None:
        if telegram_notifier is None or not getattr(telegram_notifier, "enabled", False):
            return False
        try:
            return bool(
                telegram_notifier.send_message(body_for_telegram, user_id=user_id)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed legacy Telegram notification for event %s: %s",
                event_type,
                exc,
                exc_info=True,
            )
            return False

    telegram_sent = False

    telegram_allowed = False
    try:
        telegram_allowed = preference_service.should_notify(
            user_id, event_type, channel="telegram"
        )
    except Exception as exc:  # noqa: BLE001
        # Match legacy TelegramNotifier fail-open when preference lookup errors.
        logger.warning(
            "Error checking Telegram preference for user %s event %s: %s (fail-open)",
            user_id,
            event_type,
            exc,
            exc_info=True,
        )
        telegram_allowed = True

    if telegram_allowed:
        if telegram_notifier is not None and getattr(telegram_notifier, "enabled", False):
            try:
                telegram_sent = bool(
                    telegram_notifier.send_message(body_for_telegram, user_id=user_id)
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed Telegram notification for user %s event %s: %s",
                    user_id,
                    event_type,
                    exc,
                    exc_info=True,
                )

    notification_record: Any | None = None
    try:
        if preference_service.should_notify(user_id, event_type, channel="in_app"):
            if db_session is not None:
                try:
                    from src.infrastructure.persistence.notification_repository import (
                        NotificationRepository,
                    )

                    notification_record = NotificationRepository(db_session).create(
                        user_id=user_id,
                        type="trading",
                        level=level,
                        title=title,
                        message=message_plain,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed in-app notification for user %s event %s: %s",
                        user_id,
                        event_type,
                        exc,
                        exc_info=True,
                    )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Error checking in-app preference for user %s event %s: %s",
            user_id,
            event_type,
            exc,
            exc_info=True,
        )

    try:
        if preference_service.should_notify(user_id, event_type, channel="email"):
            preferences = preference_service.get_preferences(user_id)
            if preferences and preferences.email_address and db_session is not None:
                try:
                    from services.email_notifier import EmailNotifier

                    email_notifier = EmailNotifier()
                    if email_notifier.is_available():
                        email_sent = email_notifier.send_trading_notification(
                            to_email=preferences.email_address,
                            title=title,
                            message=message_plain,
                            level=level,
                        )
                        if email_sent and notification_record is not None:
                            try:
                                from src.infrastructure.persistence.notification_repository import (
                                    NotificationRepository,
                                )

                                NotificationRepository(db_session).update_delivery_status(
                                    notification_id=notification_record.id,
                                    email_sent=True,
                                )
                            except Exception as exc:  # noqa: BLE001
                                logger.warning(
                                    "Failed to update email delivery status: %s",
                                    exc,
                                    exc_info=True,
                                )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed email notification for user %s event %s: %s",
                        user_id,
                        event_type,
                        exc,
                        exc_info=True,
                    )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Error checking email preference for user %s event %s: %s",
            user_id,
            event_type,
            exc,
            exc_info=True,
        )

    return telegram_sent
