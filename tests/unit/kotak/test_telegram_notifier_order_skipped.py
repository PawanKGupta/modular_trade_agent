"""
Tests for TelegramNotifier.notify_order_skipped() method

Tests verify that skipped order notifications are sent correctly
with proper preference checking.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.telegram_notifier import TelegramNotifier
from services.notification_preference_service import NotificationEventType


class TestTelegramNotifierOrderSkipped:
    """Test notify_order_skipped() method"""

    @pytest.fixture
    def telegram_notifier(self):
        """Create TelegramNotifier instance"""
        notifier = TelegramNotifier(
            bot_token="test_token",
            chat_id="test_chat_id",
            enabled=True,
        )
        notifier.send_message = Mock(return_value=True)
        return notifier

    @pytest.fixture
    def telegram_notifier_with_preferences(self):
        """Create TelegramNotifier with preference service"""
        mock_preference_service = Mock()
        mock_preference_service.should_notify = Mock(return_value=True)

        notifier = TelegramNotifier(
            bot_token="test_token",
            chat_id="test_chat_id",
            enabled=True,
            preference_service=mock_preference_service,
        )
        notifier.send_message = Mock(return_value=True)
        return notifier

    def test_notify_order_skipped_already_in_holdings(self, telegram_notifier):
        """Test notification for order skipped due to already in holdings"""
        result = telegram_notifier.notify_order_skipped(
            symbol="RELIANCE-EQ",
            reason="already_in_holdings",
            user_id=1,
        )

        assert result is True
        telegram_notifier.send_message.assert_called_once()
        message = telegram_notifier.send_message.call_args[0][0]

        assert "ORDER SKIPPED" in message
        assert "RELIANCE-EQ" in message
        assert "Already in Holdings" in message
        assert "You already own this stock" in message

    def test_notify_order_skipped_duplicate_order(self, telegram_notifier):
        """Test notification for order skipped due to duplicate order"""
        result = telegram_notifier.notify_order_skipped(
            symbol="TCS-EQ",
            reason="duplicate_order",
            user_id=1,
        )

        assert result is True
        telegram_notifier.send_message.assert_called_once()
        message = telegram_notifier.send_message.call_args[0][0]

        assert "ORDER SKIPPED" in message
        assert "TCS-EQ" in message
        assert "Duplicate Order" in message

    def test_notify_order_skipped_portfolio_limit(self, telegram_notifier):
        """Test notification for order skipped due to portfolio limit"""
        result = telegram_notifier.notify_order_skipped(
            symbol="INFY-EQ",
            reason="portfolio_limit_reached",
            user_id=1,
        )

        assert result is True
        telegram_notifier.send_message.assert_called_once()
        message = telegram_notifier.send_message.call_args[0][0]

        assert "ORDER SKIPPED" in message
        assert "INFY-EQ" in message
        assert "Portfolio Limit Reached" in message

    def test_notify_order_skipped_with_additional_info(self, telegram_notifier):
        """Test notification with additional info"""
        additional_info = {
            "base_symbol": "RELIANCE",
            "details": "Already in holdings: RELIANCE",
        }

        result = telegram_notifier.notify_order_skipped(
            symbol="RELIANCE-EQ",
            reason="already_in_holdings",
            additional_info=additional_info,
            user_id=1,
        )

        assert result is True
        message = telegram_notifier.send_message.call_args[0][0]

        assert "Additional Info" in message
        assert "base_symbol: RELIANCE" in message
        assert "details: Already in holdings: RELIANCE" in message

    def test_notify_order_skipped_respects_preferences_enabled(
        self, telegram_notifier_with_preferences
    ):
        """Test that notification respects preferences when enabled"""
        telegram_notifier_with_preferences.preference_service.should_notify.return_value = True

        result = telegram_notifier_with_preferences.notify_order_skipped(
            symbol="RELIANCE-EQ",
            reason="already_in_holdings",
            user_id=1,
        )

        assert result is True
        telegram_notifier_with_preferences.preference_service.should_notify.assert_called_once_with(
            user_id=1,
            event_type=NotificationEventType.ORDER_SKIPPED,
            channel="telegram",
        )
        telegram_notifier_with_preferences.send_message.assert_called_once()

    def test_notify_order_skipped_respects_preferences_disabled(
        self, telegram_notifier_with_preferences
    ):
        """Test that notification respects preferences when disabled"""
        telegram_notifier_with_preferences.preference_service.should_notify.return_value = False

        result = telegram_notifier_with_preferences.notify_order_skipped(
            symbol="RELIANCE-EQ",
            reason="already_in_holdings",
            user_id=1,
        )

        assert result is False
        telegram_notifier_with_preferences.preference_service.should_notify.assert_called_once_with(
            user_id=1,
            event_type=NotificationEventType.ORDER_SKIPPED,
            channel="telegram",
        )
        telegram_notifier_with_preferences.send_message.assert_not_called()

    def test_notify_order_skipped_backward_compatibility_no_user_id(self, telegram_notifier):
        """Test backward compatibility when user_id is not provided"""
        result = telegram_notifier.notify_order_skipped(
            symbol="RELIANCE-EQ",
            reason="already_in_holdings",
        )

        assert result is True
        telegram_notifier.send_message.assert_called_once()

    def test_notify_order_skipped_when_disabled(self):
        """Test that notification is skipped when notifier is disabled"""
        notifier = TelegramNotifier(
            bot_token="test_token",
            chat_id="test_chat_id",
            enabled=False,
        )
        # Don't mock send_message - let it check enabled flag naturally
        # send_message will return False when enabled=False

        result = notifier.notify_order_skipped(
            symbol="RELIANCE-EQ",
            reason="already_in_holdings",
        )

        assert result is False
        # send_message is called but returns False due to enabled=False check

    def test_notify_order_skipped_custom_reason(self, telegram_notifier):
        """Test notification with custom reason"""
        result = telegram_notifier.notify_order_skipped(
            symbol="STOCK-EQ",
            reason="custom_reason",
            user_id=1,
        )

        assert result is True
        message = telegram_notifier.send_message.call_args[0][0]

        assert "ORDER SKIPPED" in message
        assert "Custom Reason" in message  # Should be formatted

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.datetime")
    def test_notify_order_skipped_includes_timestamp(self, mock_datetime, telegram_notifier):
        """Test that notification includes timestamp"""
        mock_datetime.now.return_value = datetime(2025, 1, 22, 14, 30, 0)
        mock_datetime.strftime = datetime.strftime

        result = telegram_notifier.notify_order_skipped(
            symbol="RELIANCE-EQ",
            reason="already_in_holdings",
            user_id=1,
        )

        assert result is True
        message = telegram_notifier.send_message.call_args[0][0]

        assert "Time:" in message
        assert "2025-01-22" in message or "14:30" in message
