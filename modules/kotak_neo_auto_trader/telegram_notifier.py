#!/usr/bin/env python3
"""
Telegram Notifier Module
Sends notifications to Telegram for order rejections, executions, and alerts.

SOLID Principles:
- Single Responsibility: Only handles Telegram notifications
- Open/Closed: Extensible for different notification types
- Dependency Inversion: Abstract notification interface

Phase 2 Feature: Telegram notifications for order status changes
Phase 3: Notification Preferences - Checks user preferences before sending
"""

import os

# Use existing project logger
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

# Phase 3: Import notification preference service
try:
    from sqlalchemy.orm import Session

    from services.notification_preference_service import (
        NotificationEventType,
        NotificationPreferenceService,
    )

    PREFERENCE_SERVICE_AVAILABLE = True
except ImportError:
    PREFERENCE_SERVICE_AVAILABLE = False
    logger.warning(
        "NotificationPreferenceService not available. Notifications will be sent without preference checking."
    )


class TelegramNotifier:
    """
    Sends notifications to Telegram for trading events.
    Handles order rejections, executions, and system alerts.
    """

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
        enabled: bool = True,
        rate_limit_per_minute: int = 10,
        rate_limit_per_hour: int = 100,
        # Phase 3: Notification Preferences
        db_session: Session | None = None,
        preference_service: NotificationPreferenceService | None = None,
    ):
        """
        Initialize Telegram notifier.

        Phase 9: Added rate limiting to prevent spam.
        Phase 3: Added preference checking support.

        Args:
            bot_token: Telegram bot token (or reads from TELEGRAM_BOT_TOKEN env var)
            chat_id: Telegram chat ID (or reads from TELEGRAM_CHAT_ID env var)
            enabled: Whether notifications are enabled
            rate_limit_per_minute: Maximum notifications per minute (default: 10)
            rate_limit_per_hour: Maximum notifications per hour (default: 100)
            db_session: Optional database session for preference checking
            preference_service: Optional NotificationPreferenceService instance
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = enabled

        # Phase 9: Rate limiting
        self.rate_limit_per_minute = rate_limit_per_minute
        self.rate_limit_per_hour = rate_limit_per_hour
        self._notification_timestamps: list[datetime] = []
        self._rate_limit_lock = False  # Simple flag to prevent concurrent access issues

        # Phase 3: Notification Preferences
        self.db_session = db_session
        if preference_service:
            self.preference_service = preference_service
        elif db_session and PREFERENCE_SERVICE_AVAILABLE:
            self.preference_service = NotificationPreferenceService(db_session=db_session)
        else:
            self.preference_service = None
            if PREFERENCE_SERVICE_AVAILABLE:
                logger.debug(
                    "NotificationPreferenceService not initialized. "
                    "Notifications will be sent without preference checking."
                )

        if self.enabled and not self.bot_token:
            logger.warning(
                "Telegram bot token not provided. "
                "Notifications will be disabled. "
                "Set TELEGRAM_BOT_TOKEN environment variable."
            )
            self.enabled = False

        if self.enabled and not self.chat_id:
            logger.warning(
                "Telegram chat ID not provided. "
                "Notifications will be disabled. "
                "Set TELEGRAM_CHAT_ID environment variable."
            )
            self.enabled = False

        if self.enabled:
            logger.info("Telegram notifier initialized and enabled")
        else:
            logger.info("Telegram notifier disabled")

    def _check_rate_limit(self) -> bool:
        """
        Check if sending a notification would exceed rate limits.

        Phase 9: Rate limiting to prevent spam.

        Returns:
            True if within rate limits, False if rate limit exceeded
        """
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        one_hour_ago = now - timedelta(hours=1)

        # Clean old timestamps
        self._notification_timestamps = [
            ts for ts in self._notification_timestamps if ts > one_hour_ago
        ]

        # Check per-minute limit
        recent_minute = [ts for ts in self._notification_timestamps if ts > one_minute_ago]
        if len(recent_minute) >= self.rate_limit_per_minute:
            logger.debug(
                f"Rate limit exceeded: {len(recent_minute)} notifications in last minute "
                f"(limit: {self.rate_limit_per_minute})"
            )
            return False

        # Check per-hour limit
        if len(self._notification_timestamps) >= self.rate_limit_per_hour:
            logger.debug(
                f"Rate limit exceeded: {len(self._notification_timestamps)} notifications in last hour "
                f"(limit: {self.rate_limit_per_hour})"
            )
            return False

        return True

    def _should_send_notification(self, user_id: int | None, event_type: str) -> bool:
        """
        Check if notification should be sent based on user preferences.

        Phase 3: Notification Preferences integration.

        Args:
            user_id: User ID (None for backward compatibility)
            event_type: Event type from NotificationEventType constants

        Returns:
            True if notification should be sent, False otherwise
        """
        # Backward compatibility: If no user_id or preference_service, send notification
        if user_id is None or self.preference_service is None:
            return True

        # Check preferences
        try:
            should_notify = self.preference_service.should_notify(
                user_id=user_id, event_type=event_type, channel="telegram"
            )
            if not should_notify:
                logger.debug(
                    f"Notification skipped for user {user_id}, event {event_type} "
                    "(preference disabled or quiet hours)"
                )
            return should_notify
        except Exception as e:
            # On error, default to sending (fail open for backward compatibility)
            logger.warning(f"Error checking notification preferences: {e}. Sending notification.")
            return True

    def send_message(
        self, message: str, parse_mode: str = "Markdown", user_id: int | None = None
    ) -> bool:
        """
        Send text message to Telegram.

        Phase 9: Added rate limiting to prevent spam.
        Phase 3: Added preference checking.

        Args:
            message: Message text (supports Markdown)
            parse_mode: Parse mode ('Markdown', 'HTML', or None)
            user_id: Optional user ID for preference checking

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug(f"Telegram notification skipped (disabled): {message[:50]}...")
            return False

        # Phase 3: Check preferences if user_id and preference_service are available
        if user_id is not None and self.preference_service:
            # Note: We can't check event type here since send_message is generic
            # Specific notification methods will check preferences before calling send_message
            pass

        # Phase 9: Check rate limit
        if not self._check_rate_limit():
            logger.debug("Telegram notification skipped due to rate limit")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            payload = {"chat_id": self.chat_id, "text": message, "parse_mode": parse_mode}

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                # Phase 9: Record successful notification timestamp
                self._notification_timestamps.append(datetime.now())
                logger.debug("Telegram notification sent successfully")
                return True
            else:
                logger.error(
                    f"Telegram notification failed: HTTP {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            return False

    def notify_order_rejection(
        self,
        symbol: str,
        order_id: str,
        quantity: int,
        rejection_reason: str,
        additional_info: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> bool:
        """
        Send notification for rejected order.

        Phase 3: Added user_id parameter for preference checking.

        Args:
            symbol: Trading symbol
            order_id: Order ID that was rejected
            quantity: Order quantity
            rejection_reason: Reason for rejection
            additional_info: Optional additional details
            user_id: Optional user ID for preference checking

        Returns:
            True if sent successfully
        """
        # Phase 3: Check preferences
        if not self._should_send_notification(user_id, NotificationEventType.ORDER_REJECTED):
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = (
            f"ORDER REJECTED\n\n"
            f"Symbol: `{symbol}`\n"
            f"Order ID: `{order_id}`\n"
            f"Quantity: {quantity}\n"
            f"Reason: {rejection_reason}\n"
            f"Time: {timestamp}\n"
        )

        if additional_info:
            message += "\n*Additional Info:*\n"
            for key, value in additional_info.items():
                message += f"  - {key}: {value}\n"

        message += "\n_Please review and take necessary action._"

        logger.info(f"Sending rejection notification for {symbol}")
        return self.send_message(message, user_id=user_id)

    def notify_order_execution(
        self,
        symbol: str,
        order_id: str,
        quantity: int,
        executed_price: float | None = None,
        additional_info: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> bool:
        """
        Send notification for successfully executed order.

        Phase 3: Added user_id parameter for preference checking.

        Args:
            symbol: Trading symbol
            order_id: Order ID that was executed
            quantity: Executed quantity
            executed_price: Execution price (if available)
            additional_info: Optional additional details
            user_id: Optional user ID for preference checking

        Returns:
            True if sent successfully
        """
        # Phase 3: Check preferences
        if not self._should_send_notification(user_id, NotificationEventType.ORDER_EXECUTED):
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = (
            f"ORDER EXECUTED\n\nSymbol: `{symbol}`\nOrder ID: `{order_id}`\nQuantity: {quantity}\n"
        )

        if executed_price:
            message += f"Price: Rs {executed_price:.2f}\n"
            total_value = executed_price * quantity
            message += f"Total Value: Rs {total_value:,.2f}\n"

        message += f"Time: {timestamp}\n"

        if additional_info:
            message += "\n*Additional Info:*\n"
            for key, value in additional_info.items():
                message += f"  - {key}: {value}\n"

        logger.info(f"Sending execution notification for {symbol}")
        return self.send_message(message, user_id=user_id)

    def notify_partial_fill(
        self,
        symbol: str,
        order_id: str,
        filled_qty: int,
        total_qty: int,
        remaining_qty: int,
        additional_info: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> bool:
        """
        Send notification for partially filled order.

        Phase 3: Added user_id parameter for preference checking.

        Args:
            symbol: Trading symbol
            order_id: Order ID
            filled_qty: Quantity filled so far
            total_qty: Total order quantity
            remaining_qty: Remaining unfilled quantity
            additional_info: Optional additional details
            user_id: Optional user ID for preference checking

        Returns:
            True if sent successfully
        """
        # Phase 3: Check preferences
        if not self._should_send_notification(user_id, NotificationEventType.PARTIAL_FILL):
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fill_percentage = (filled_qty / total_qty * 100) if total_qty > 0 else 0

        message = (
            f"ORDER PARTIALLY FILLED\n\n"
            f"Symbol: `{symbol}`\n"
            f"Order ID: `{order_id}`\n"
            f"Filled: {filled_qty} / {total_qty} ({fill_percentage:.1f}%)\n"
            f"Remaining: {remaining_qty}\n"
            f"Time: {timestamp}\n"
        )

        if additional_info:
            message += "\n*Additional Info:*\n"
            for key, value in additional_info.items():
                message += f"  - {key}: {value}\n"

        logger.info(f"Sending partial fill notification for {symbol}")
        return self.send_message(message, user_id=user_id)

    def notify_system_alert(
        self,
        alert_type: str,
        message_text: str,
        severity: str = "INFO",
        user_id: int | None = None,
    ) -> bool:
        """
        Send generic system alert notification.

        Phase 3: Added user_id parameter for preference checking.

        Args:
            alert_type: Type of alert (e.g., "ERROR", "WARNING", "INFO")
            message_text: Alert message
            severity: Severity level
            user_id: Optional user ID for preference checking

        Returns:
            True if sent successfully
        """
        # Phase 3: Map severity to event type and check preferences
        # Check if this is a service event (SERVICE_STARTED, SERVICE_STOPPED, SERVICE_EXECUTION)
        if alert_type in ("SERVICE_STARTED", "SERVICE_STOPPED", "SERVICE_EXECUTION"):
            event_type = NotificationEventType.SERVICE_EVENT
        else:
            event_type_map = {
                "ERROR": NotificationEventType.SYSTEM_ERROR,
                "WARNING": NotificationEventType.SYSTEM_WARNING,
                "INFO": NotificationEventType.SYSTEM_INFO,
            }
            event_type = event_type_map.get(severity.upper(), NotificationEventType.SYSTEM_INFO)

        if not self._should_send_notification(user_id, event_type):
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Choose emoji based on severity
        emoji_map = {"ERROR": "", "WARNING": "", "INFO": "", "SUCCESS": ""}
        emoji = emoji_map.get(severity.upper(), "")

        # For service events and trading events, use a cleaner format without redundant "SYSTEM ALERT" prefix
        # since message_text already contains the context
        clean_format_alert_types = (
            "SERVICE_STARTED",
            "SERVICE_STOPPED",
            "SERVICE_EXECUTION",
            "POSITION_ALERT",
            "MANUAL_TRADE",
            "PRE_MARKET_ADJUSTMENT",
        )
        if alert_type in clean_format_alert_types:
            message = f"{emoji} {message_text}\n\nTime: {timestamp}\n"
        else:
            # For other alerts, include the alert type for context
            message = f"{emoji} SYSTEM ALERT: {alert_type}\n\n{message_text}\n\nTime: {timestamp}\n"

        logger.info(f"Sending system alert: {alert_type}")
        return self.send_message(message, user_id=user_id)

    def notify_daily_summary(
        self,
        orders_placed: int,
        orders_executed: int,
        orders_rejected: int,
        orders_pending: int,
        tracked_symbols: int,
        additional_stats: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> bool:
        """
        Send end-of-day summary notification.

        Phase 3: Added user_id parameter for preference checking.

        Args:
            orders_placed: Total orders placed today
            orders_executed: Successfully executed orders
            orders_rejected: Rejected orders
            orders_pending: Still pending orders
            tracked_symbols: Number of symbols being tracked
            additional_stats: Optional additional statistics
            user_id: Optional user ID for preference checking

        Returns:
            True if sent successfully
        """
        # Phase 3: Check preferences
        if not self._should_send_notification(user_id, NotificationEventType.SYSTEM_INFO):
            return False

        date = datetime.now().strftime("%Y-%m-%d")

        message = (
            f"DAILY TRADING SUMMARY\n"
            f"Date: {date}\n\n"
            f"Order Statistics:\n"
            f"  - Orders Placed: {orders_placed}\n"
            f"  - Executed: {orders_executed}\n"
            f"  - Rejected: {orders_rejected}\n"
            f"  - Pending: {orders_pending}\n\n"
            f"Tracking Status:\n"
            f"  - Active Symbols: {tracked_symbols}\n"
        )

        if additional_stats:
            message += "\n*Additional Stats:*\n"
            for key, value in additional_stats.items():
                message += f"  - {key}: {value}\n"

        success_rate = (orders_executed / orders_placed * 100) if orders_placed > 0 else 0
        message += f"\nSuccess Rate: {success_rate:.1f}%"

        logger.info("Sending daily summary notification")
        return self.send_message(message, user_id=user_id)

    def notify_tracking_stopped(
        self,
        symbol: str,
        reason: str,
        tracking_duration: str | None = None,
        user_id: int | None = None,
    ) -> bool:
        """
        Send notification when symbol tracking stops.

        Phase 3: Added user_id parameter for preference checking.

        Args:
            symbol: Trading symbol
            reason: Reason for stopping tracking
            tracking_duration: How long symbol was tracked
            user_id: Optional user ID for preference checking

        Returns:
            True if sent successfully
        """
        # Phase 3: Check preferences (use SYSTEM_INFO as tracking stopped is informational)
        if not self._should_send_notification(user_id, NotificationEventType.SYSTEM_INFO):
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = f"TRACKING STOPPED\n\nSymbol: `{symbol}`\nReason: {reason}\n"

        if tracking_duration:
            message += f"Duration: {tracking_duration}\n"

        message += f"Time: {timestamp}\n"

        logger.info(f"Sending tracking stopped notification for {symbol}")
        return self.send_message(message, user_id=user_id)

    def notify_order_placed(
        self,
        symbol: str,
        order_id: str,
        quantity: int,
        order_type: str = "MARKET",
        price: float | None = None,
        additional_info: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> bool:
        """
        Send notification for successfully placed order.

        Phase 9: Notification for order placement.
        Phase 3: Added user_id parameter for preference checking.

        Args:
            symbol: Trading symbol
            order_id: Order ID from broker
            quantity: Order quantity
            order_type: Order type (MARKET/LIMIT)
            price: Limit price (if applicable)
            additional_info: Optional additional details
            user_id: Optional user ID for preference checking

        Returns:
            True if sent successfully
        """
        # Phase 3: Check preferences
        if not self._should_send_notification(user_id, NotificationEventType.ORDER_PLACED):
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = (
            f"ORDER PLACED\n\n"
            f"Symbol: `{symbol}`\n"
            f"Order ID: `{order_id}`\n"
            f"Quantity: {quantity}\n"
            f"Type: {order_type}\n"
        )

        if price:
            message += f"Price: Rs {price:.2f}\n"

        message += f"Time: {timestamp}\n"

        if additional_info:
            message += "\n*Additional Info:*\n"
            for key, value in additional_info.items():
                message += f"  - {key}: {value}\n"

        logger.info(f"Sending order placed notification for {symbol}")
        return self.send_message(message, user_id=user_id)

    def notify_order_cancelled(
        self,
        symbol: str,
        order_id: str,
        cancellation_reason: str,
        additional_info: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> bool:
        """
        Send notification for cancelled order.

        Phase 9: Notification for order cancellation.
        Phase 3: Added user_id parameter for preference checking.

        Args:
            symbol: Trading symbol
            order_id: Order ID that was cancelled
            cancellation_reason: Reason for cancellation
            additional_info: Optional additional details
            user_id: Optional user ID for preference checking

        Returns:
            True if sent successfully
        """
        # Phase 3: Check preferences
        if not self._should_send_notification(user_id, NotificationEventType.ORDER_CANCELLED):
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = (
            f"ORDER CANCELLED\n\n"
            f"Symbol: `{symbol}`\n"
            f"Order ID: `{order_id}`\n"
            f"Reason: {cancellation_reason}\n"
            f"Time: {timestamp}\n"
        )

        if additional_info:
            message += "\n*Additional Info:*\n"
            for key, value in additional_info.items():
                message += f"  - {key}: {value}\n"

        logger.info(f"Sending cancellation notification for {symbol}")
        return self.send_message(message, user_id=user_id)

    def notify_order_modified(
        self,
        symbol: str,
        order_id: str,
        changes: dict[str, tuple[Any, Any]],
        additional_info: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> bool:
        """
        Send notification for manually modified order.

        Phase 4: Notification for order modifications.
        Phase 3: Added user_id parameter for preference checking.

        Args:
            symbol: Trading symbol
            order_id: Order ID that was modified
            changes: Dictionary of changes, e.g., {"quantity": (old, new), "price": (old, new)}
            additional_info: Optional additional details
            user_id: Optional user ID for preference checking

        Returns:
            True if sent successfully
        """
        # Phase 3: Check preferences
        if not self._should_send_notification(user_id, NotificationEventType.ORDER_MODIFIED):
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = (
            f"⚠️ ORDER MODIFIED\n\n"
            f"Symbol: `{symbol}`\n"
            f"Order ID: `{order_id}`\n"
            f"Time: {timestamp}\n\n"
            f"*Changes:*\n"
        )

        # Format changes
        for field, (old_value, new_value) in changes.items():
            if field == "price":
                message += f"  - Price: Rs {old_value:.2f} → Rs {new_value:.2f}\n"
            elif field == "quantity":
                message += f"  - Quantity: {old_value} → {new_value}\n"
            else:
                message += f"  - {field.capitalize()}: {old_value} → {new_value}\n"

        message += "\n_Order was modified manually in broker app._"

        if additional_info:
            message += "\n\n*Additional Info:*\n"
            for key, value in additional_info.items():
                message += f"  - {key}: {value}\n"

        logger.info(f"Sending order modification notification for {symbol}")
        return self.send_message(message, user_id=user_id)

    def notify_retry_queue_updated(
        self,
        symbol: str,
        action: str,
        retry_count: int | None = None,
        additional_info: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> bool:
        """
        Send notification when retry queue is updated.

        Phase 9: Notification for retry queue changes.
        Phase 3: Added user_id parameter for preference checking.

        Args:
            symbol: Trading symbol
            action: Action taken (e.g., "added", "retried", "removed", "updated")
            retry_count: Current retry count (if applicable)
            additional_info: Optional additional details
            user_id: Optional user ID for preference checking

        Returns:
            True if sent successfully
        """
        # Phase 3: Map action to event type and check preferences
        action_event_map = {
            "added": NotificationEventType.RETRY_QUEUE_ADDED,
            "updated": NotificationEventType.RETRY_QUEUE_UPDATED,
            "removed": NotificationEventType.RETRY_QUEUE_REMOVED,
            "retried": NotificationEventType.RETRY_QUEUE_RETRIED,
        }
        event_type = action_event_map.get(action.lower(), NotificationEventType.RETRY_QUEUE_UPDATED)

        if not self._should_send_notification(user_id, event_type):
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = f"RETRY QUEUE UPDATE\n\nSymbol: `{symbol}`\nAction: {action}\n"

        if retry_count is not None:
            message += f"Retry Count: {retry_count}\n"

        message += f"Time: {timestamp}\n"

        if additional_info:
            message += "\n*Additional Info:*\n"
            for key, value in additional_info.items():
                message += f"  - {key}: {value}\n"

        logger.info(f"Sending retry queue update notification for {symbol}")
        return self.send_message(message, user_id=user_id)

    def test_connection(self) -> bool:
        """
        Test Telegram connection by sending a test message.

        Returns:
            True if connection successful
        """
        if not self.enabled:
            logger.error("Telegram notifier is disabled. Cannot test connection.")
            return False

        test_message = (
            "Telegram Notifier Test\n\nConnection successful!\nYou will receive notifications here."
        )

        return self.send_message(test_message)


# Singleton instance
_notifier_instance: TelegramNotifier | None = None


def get_telegram_notifier(
    bot_token: str | None = None,
    chat_id: str | None = None,
    enabled: bool = True,
    db_session=None,
    preference_service=None,
) -> TelegramNotifier:
    """
    Get or create Telegram notifier singleton.

    Phase 3: Added db_session and preference_service parameters.

    Args:
        bot_token: Telegram bot token
        chat_id: Telegram chat ID
        enabled: Whether notifications are enabled
        db_session: Optional database session for preference checking
        preference_service: Optional NotificationPreferenceService instance

    Returns:
        TelegramNotifier instance
    """
    global _notifier_instance

    if _notifier_instance is None:
        _notifier_instance = TelegramNotifier(
            bot_token,
            chat_id,
            enabled,
            db_session=db_session,
            preference_service=preference_service,
        )

    return _notifier_instance
