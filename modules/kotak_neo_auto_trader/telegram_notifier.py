#!/usr/bin/env python3
"""
Telegram Notifier Module
Sends notifications to Telegram for order rejections, executions, and alerts.

SOLID Principles:
- Single Responsibility: Only handles Telegram notifications
- Open/Closed: Extensible for different notification types
- Dependency Inversion: Abstract notification interface

Phase 2 Feature: Telegram notifications for order status changes
"""

import os
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

# Use existing project logger
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger


class TelegramNotifier:
    """
    Sends notifications to Telegram for trading events.
    Handles order rejections, executions, and system alerts.
    """

    def __init__(
        self, bot_token: Optional[str] = None, chat_id: Optional[str] = None, enabled: bool = True
    ):
        """
        Initialize Telegram notifier.

        Args:
            bot_token: Telegram bot token (or reads from TELEGRAM_BOT_TOKEN env var)
            chat_id: Telegram chat ID (or reads from TELEGRAM_CHAT_ID env var)
            enabled: Whether notifications are enabled
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = enabled

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

    def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Send text message to Telegram.

        Args:
            message: Message text (supports Markdown)
            parse_mode: Parse mode ('Markdown', 'HTML', or None)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug(f"Telegram notification skipped (disabled): {message[:50]}...")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            payload = {"chat_id": self.chat_id, "text": message, "parse_mode": parse_mode}

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.debug("Telegram notification sent successfully")
                return True
            else:
                logger.error(
                    f"Telegram notification failed: "
                    f"HTTP {response.status_code} - {response.text}"
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
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send notification for rejected order.

        Args:
            symbol: Trading symbol
            order_id: Order ID that was rejected
            quantity: Order quantity
            rejection_reason: Reason for rejection
            additional_info: Optional additional details

        Returns:
            True if sent successfully
        """
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
        return self.send_message(message)

    def notify_order_execution(
        self,
        symbol: str,
        order_id: str,
        quantity: int,
        executed_price: Optional[float] = None,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send notification for successfully executed order.

        Args:
            symbol: Trading symbol
            order_id: Order ID that was executed
            quantity: Executed quantity
            executed_price: Execution price (if available)
            additional_info: Optional additional details

        Returns:
            True if sent successfully
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = (
            f"ORDER EXECUTED\n\n"
            f"Symbol: `{symbol}`\n"
            f"Order ID: `{order_id}`\n"
            f"Quantity: {quantity}\n"
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
        return self.send_message(message)

    def notify_partial_fill(
        self,
        symbol: str,
        order_id: str,
        filled_qty: int,
        total_qty: int,
        remaining_qty: int,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send notification for partially filled order.

        Args:
            symbol: Trading symbol
            order_id: Order ID
            filled_qty: Quantity filled so far
            total_qty: Total order quantity
            remaining_qty: Remaining unfilled quantity
            additional_info: Optional additional details

        Returns:
            True if sent successfully
        """
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
        return self.send_message(message)

    def notify_system_alert(
        self, alert_type: str, message_text: str, severity: str = "INFO"
    ) -> bool:
        """
        Send generic system alert notification.

        Args:
            alert_type: Type of alert (e.g., "ERROR", "WARNING", "INFO")
            message_text: Alert message
            severity: Severity level

        Returns:
            True if sent successfully
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Choose emoji based on severity
        emoji_map = {"ERROR": "", "WARNING": "", "INFO": "", "SUCCESS": ""}
        emoji = emoji_map.get(severity.upper(), "")

        message = (
            f"{emoji} SYSTEM ALERT: {alert_type}\n\n" f"{message_text}\n\n" f"Time: {timestamp}\n"
        )

        logger.info(f"Sending system alert: {alert_type}")
        return self.send_message(message)

    def notify_daily_summary(
        self,
        orders_placed: int,
        orders_executed: int,
        orders_rejected: int,
        orders_pending: int,
        tracked_symbols: int,
        additional_stats: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send end-of-day summary notification.

        Args:
            orders_placed: Total orders placed today
            orders_executed: Successfully executed orders
            orders_rejected: Rejected orders
            orders_pending: Still pending orders
            tracked_symbols: Number of symbols being tracked
            additional_stats: Optional additional statistics

        Returns:
            True if sent successfully
        """
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
        return self.send_message(message)

    def notify_tracking_stopped(
        self, symbol: str, reason: str, tracking_duration: Optional[str] = None
    ) -> bool:
        """
        Send notification when symbol tracking stops.

        Args:
            symbol: Trading symbol
            reason: Reason for stopping tracking
            tracking_duration: How long symbol was tracked

        Returns:
            True if sent successfully
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = f"TRACKING STOPPED\n\n" f"Symbol: `{symbol}`\n" f"Reason: {reason}\n"

        if tracking_duration:
            message += f"Duration: {tracking_duration}\n"

        message += f"Time: {timestamp}\n"

        logger.info(f"Sending tracking stopped notification for {symbol}")
        return self.send_message(message)

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
            "Telegram Notifier Test\n\n"
            "Connection successful!\n"
            "You will receive notifications here."
        )

        return self.send_message(test_message)


# Singleton instance
_notifier_instance: Optional[TelegramNotifier] = None


def get_telegram_notifier(
    bot_token: Optional[str] = None, chat_id: Optional[str] = None, enabled: bool = True
) -> TelegramNotifier:
    """
    Get or create Telegram notifier singleton.

    Args:
        bot_token: Telegram bot token
        chat_id: Telegram chat ID
        enabled: Whether notifications are enabled

    Returns:
        TelegramNotifier instance
    """
    global _notifier_instance

    if _notifier_instance is None:
        _notifier_instance = TelegramNotifier(bot_token, chat_id, enabled)

    return _notifier_instance
