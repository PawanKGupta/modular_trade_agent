"""Unit tests for multi-channel trading notification dispatcher."""

from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.trading_notification_dedupe import (
    trading_notification_dedupe,
)
from modules.kotak_neo_auto_trader.trading_notification_dispatcher import (
    dispatch_trading_notification,
)
from services.notification_preference_service import NotificationEventType


@pytest.fixture(autouse=True)
def _clear_dedupe():
    trading_notification_dedupe.clear()
    yield
    trading_notification_dedupe.clear()


@pytest.fixture
def mock_pref_service():
    service = Mock()
    service.should_notify = Mock(return_value=True)
    service.get_preferences = Mock(
        return_value=Mock(email_address="user@example.com")
    )
    return service


@pytest.fixture
def mock_telegram_notifier():
    notifier = Mock()
    notifier.enabled = True
    notifier.send_message = Mock(return_value=True)
    return notifier


def test_dispatch_all_channels(mock_pref_service, mock_telegram_notifier):
    """Telegram, in-app, and email when all channels enabled."""
    mock_db = Mock()
    mock_notification = Mock(id=42)

    with (
        patch(
            "src.infrastructure.persistence.notification_repository.NotificationRepository"
        ) as repo_cls,
        patch("services.email_notifier.EmailNotifier") as email_cls,
    ):
        repo = Mock()
        repo.create.return_value = mock_notification
        repo_cls.return_value = repo

        email = Mock()
        email.is_available.return_value = True
        email.send_trading_notification.return_value = True
        email_cls.return_value = email

        result = dispatch_trading_notification(
            user_id=1,
            event_type=NotificationEventType.ORDER_PLACED,
            title="Order Placed",
            message_plain="RELIANCE buy 10",
            telegram_notifier=mock_telegram_notifier,
            db_session=mock_db,
            preference_service=mock_pref_service,
        )

    assert result is True
    assert mock_telegram_notifier.send_message.call_count == 1
    repo.create.assert_called_once()
    email.send_trading_notification.assert_called_once()
    repo.update_delivery_status.assert_called_once_with(
        notification_id=42, email_sent=True
    )


def test_dispatch_in_app_only_when_telegram_disabled(
    mock_pref_service, mock_telegram_notifier
):
    """In-app can fire when Telegram preference is off."""
    mock_pref_service.should_notify = Mock(
        side_effect=lambda _uid, _evt, channel: channel == "in_app"
    )
    mock_db = Mock()

    with patch(
        "src.infrastructure.persistence.notification_repository.NotificationRepository"
    ) as repo_cls:
        repo = Mock()
        repo_cls.return_value = repo

        result = dispatch_trading_notification(
            user_id=1,
            event_type=NotificationEventType.ORDER_EXECUTED,
            title="Order Executed",
            message_plain="Filled",
            telegram_notifier=mock_telegram_notifier,
            db_session=mock_db,
            preference_service=mock_pref_service,
        )

    assert result is False
    mock_telegram_notifier.send_message.assert_not_called()
    repo.create.assert_called_once()


def test_dispatch_legacy_telegram_only_without_preferences(mock_telegram_notifier):
    """user_id=None keeps Telegram-only backward compatibility."""
    result = dispatch_trading_notification(
        user_id=None,
        event_type=NotificationEventType.ORDER_PLACED,
        title="Order Placed",
        message_plain="plain",
        telegram_notifier=mock_telegram_notifier,
    )

    assert result is True
    mock_telegram_notifier.send_message.assert_called_once_with(
        "plain", user_id=None, rate_limit_exempt=True
    )


def test_dispatch_dedupes_terminal_order_events(mock_pref_service, mock_telegram_notifier):
    """Second dispatch for same user/order/event is suppressed (PR3)."""
    mock_db = Mock()

    with patch(
        "src.infrastructure.persistence.notification_repository.NotificationRepository"
    ) as repo_cls:
        repo = Mock()
        repo_cls.return_value = repo

        first = dispatch_trading_notification(
            user_id=1,
            event_type=NotificationEventType.ORDER_EXECUTED,
            title="Order Executed",
            message_plain="Filled",
            order_id="ORD-99",
            telegram_notifier=mock_telegram_notifier,
            db_session=mock_db,
            preference_service=mock_pref_service,
        )
        second = dispatch_trading_notification(
            user_id=1,
            event_type=NotificationEventType.ORDER_EXECUTED,
            title="Order Executed",
            message_plain="Filled again",
            order_id="ORD-99",
            telegram_notifier=mock_telegram_notifier,
            db_session=mock_db,
            preference_service=mock_pref_service,
        )

    assert first is True
    assert second is False
    assert mock_telegram_notifier.send_message.call_count == 1
    assert repo.create.call_count == 1


def test_dispatch_telegram_rate_limit_exempt(mock_pref_service, mock_telegram_notifier):
    """Order events pass rate_limit_exempt to Telegram send_message."""
    dispatch_trading_notification(
        user_id=1,
        event_type=NotificationEventType.ORDER_REJECTED,
        title="Order Rejected",
        message_plain="Rejected",
        order_id="ORD-1",
        telegram_notifier=mock_telegram_notifier,
        db_session=Mock(),
        preference_service=mock_pref_service,
    )

    mock_telegram_notifier.send_message.assert_called_once()
    _, kwargs = mock_telegram_notifier.send_message.call_args
    assert kwargs.get("rate_limit_exempt") is True


def test_dispatch_never_raises_on_in_app_failure(
    mock_pref_service, mock_telegram_notifier
):
    """In-app persistence errors are logged, Telegram still attempted."""
    mock_db = Mock()

    with patch(
        "src.infrastructure.persistence.notification_repository.NotificationRepository"
    ) as repo_cls:
        repo = Mock()
        repo.create.side_effect = RuntimeError("db down")
        repo_cls.return_value = repo
        result = dispatch_trading_notification(
            user_id=1,
            event_type=NotificationEventType.ORDER_REJECTED,
            title="Order Rejected",
            message_plain="Rejected",
            telegram_notifier=mock_telegram_notifier,
            db_session=mock_db,
            preference_service=mock_pref_service,
        )

    assert result is True
