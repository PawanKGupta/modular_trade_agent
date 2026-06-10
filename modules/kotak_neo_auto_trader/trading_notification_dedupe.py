"""
In-process dedupe for terminal order notifications (PR3).

Prevents duplicate Telegram/in-app/email when both the immediate broker
verifier path and the unified order monitor detect the same fill/reject/cancel.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict

from services.notification_preference_service import NotificationEventType

logger = logging.getLogger(__name__)

# Terminal events only — partial fills and modifies may legitimately repeat.
DEDUPE_EVENT_TYPES = frozenset(
    {
        NotificationEventType.ORDER_EXECUTED,
        NotificationEventType.ORDER_REJECTED,
        NotificationEventType.ORDER_CANCELLED,
    }
)


class TradingNotificationDedupe:
    """Thread-safe TTL-bounded cache of (user_id, order_id, event_type) keys."""

    def __init__(self, max_entries: int = 10_000) -> None:
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._seen: OrderedDict[tuple[int, str, str], None] = OrderedDict()

    def try_acquire(self, user_id: int, order_id: str, event_type: str) -> bool:
        """
        Record first notification for a terminal order event.

        Returns True if this caller should proceed; False if already sent.
        """
        if event_type not in DEDUPE_EVENT_TYPES:
            return True

        key = (user_id, str(order_id), event_type)
        with self._lock:
            if key in self._seen:
                logger.debug(
                    "Duplicate trading notification suppressed: user=%s order=%s event=%s",
                    user_id,
                    order_id,
                    event_type,
                )
                return False
            self._seen[key] = None
            while len(self._seen) > self._max_entries:
                self._seen.popitem(last=False)
            return True

    def clear(self) -> None:
        """Reset state (tests only)."""
        with self._lock:
            self._seen.clear()


trading_notification_dedupe = TradingNotificationDedupe()
