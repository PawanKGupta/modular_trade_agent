"""Unit tests for trading notification dedupe (PR3)."""

import pytest

from modules.kotak_neo_auto_trader.trading_notification_dedupe import (
    TradingNotificationDedupe,
    trading_notification_dedupe,
)
from services.notification_preference_service import NotificationEventType


@pytest.fixture(autouse=True)
def _clear_global_dedupe():
    trading_notification_dedupe.clear()
    yield
    trading_notification_dedupe.clear()


def test_terminal_events_dedupe_once():
    dedupe = TradingNotificationDedupe()
    assert dedupe.try_acquire(1, "ORD1", NotificationEventType.ORDER_EXECUTED) is True
    assert dedupe.try_acquire(1, "ORD1", NotificationEventType.ORDER_EXECUTED) is False


def test_different_event_types_not_deduped():
    dedupe = TradingNotificationDedupe()
    assert dedupe.try_acquire(1, "ORD1", NotificationEventType.ORDER_EXECUTED) is True
    assert dedupe.try_acquire(1, "ORD1", NotificationEventType.ORDER_REJECTED) is True


def test_non_terminal_events_always_acquire():
    dedupe = TradingNotificationDedupe()
    assert dedupe.try_acquire(1, "ORD1", NotificationEventType.PARTIAL_FILL) is True
    assert dedupe.try_acquire(1, "ORD1", NotificationEventType.PARTIAL_FILL) is True
    assert dedupe.try_acquire(1, "ORD1", NotificationEventType.ORDER_MODIFIED) is True
    assert dedupe.try_acquire(1, "ORD1", NotificationEventType.ORDER_MODIFIED) is True


def test_different_users_not_deduped():
    dedupe = TradingNotificationDedupe()
    assert dedupe.try_acquire(1, "ORD1", NotificationEventType.ORDER_CANCELLED) is True
    assert dedupe.try_acquire(2, "ORD1", NotificationEventType.ORDER_CANCELLED) is True
