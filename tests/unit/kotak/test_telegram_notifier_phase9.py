"""
Tests for Phase 9: Notification triggers in TelegramNotifier

Tests new notification methods and rate limiting functionality.
"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.telegram_notifier import TelegramNotifier, get_telegram_notifier


class TestTelegramNotifierPhase9(unittest.TestCase):
    """Test Phase 9 notification methods and rate limiting"""

    def setUp(self):
        """Set up test fixtures"""
        self.bot_token = "test_bot_token"
        self.chat_id = "test_chat_id"
        self.notifier = TelegramNotifier(
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            enabled=True,
            rate_limit_per_minute=5,
            rate_limit_per_hour=20,
        )

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.requests.post")
    def test_notify_order_placed_success(self, mock_post):
        """Test notify_order_placed with successful send"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = self.notifier.notify_order_placed(
            symbol="RELIANCE",
            order_id="ORDER123",
            quantity=10,
            order_type="MARKET",
            user_id=None,  # Phase 3: Test backward compatibility
        )

        self.assertTrue(result)
        self.assertEqual(len(self.notifier._notification_timestamps), 1)
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn("chat_id", call_args[1]["json"])
        self.assertEqual(call_args[1]["json"]["chat_id"], self.chat_id)

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.requests.post")
    def test_notify_order_placed_with_price(self, mock_post):
        """Test notify_order_placed with limit price"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = self.notifier.notify_order_placed(
            symbol="RELIANCE",
            order_id="ORDER123",
            quantity=10,
            order_type="LIMIT",
            price=2500.50,
        )

        self.assertTrue(result)
        mock_post.assert_called_once()
        message = mock_post.call_args[1]["json"]["text"]
        self.assertIn("RELIANCE", message)
        self.assertIn("ORDER123", message)
        self.assertIn("2500.50", message)
        self.assertIn("LIMIT", message)

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.requests.post")
    def test_notify_order_placed_with_additional_info(self, mock_post):
        """Test notify_order_placed with additional info"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        additional_info = {"source": "backtest", "score": 85.5}
        result = self.notifier.notify_order_placed(
            symbol="RELIANCE",
            order_id="ORDER123",
            quantity=10,
            additional_info=additional_info,
        )

        self.assertTrue(result)
        message = mock_post.call_args[1]["json"]["text"]
        self.assertIn("source", message)
        self.assertIn("85.5", message)

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.requests.post")
    def test_notify_order_cancelled_success(self, mock_post):
        """Test notify_order_cancelled with successful send"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = self.notifier.notify_order_cancelled(
            symbol="RELIANCE",
            order_id="ORDER123",
            cancellation_reason="User cancelled",
        )

        self.assertTrue(result)
        mock_post.assert_called_once()
        message = mock_post.call_args[1]["json"]["text"]
        self.assertIn("RELIANCE", message)
        self.assertIn("ORDER123", message)
        self.assertIn("User cancelled", message)

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.requests.post")
    def test_notify_order_cancelled_with_additional_info(self, mock_post):
        """Test notify_order_cancelled with additional info"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        additional_info = {"cancelled_by": "system", "timeout": True}
        result = self.notifier.notify_order_cancelled(
            symbol="RELIANCE",
            order_id="ORDER123",
            cancellation_reason="Timeout",
            additional_info=additional_info,
        )

        self.assertTrue(result)
        message = mock_post.call_args[1]["json"]["text"]
        self.assertIn("system", message)

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.requests.post")
    def test_notify_retry_queue_updated_added(self, mock_post):
        """Test notify_retry_queue_updated for added action"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = self.notifier.notify_retry_queue_updated(
            symbol="RELIANCE",
            action="added",
            retry_count=0,
        )

        self.assertTrue(result)
        message = mock_post.call_args[1]["json"]["text"]
        self.assertIn("RELIANCE", message)
        self.assertIn("added", message)
        self.assertIn("0", message)

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.requests.post")
    def test_notify_retry_queue_updated_retried(self, mock_post):
        """Test notify_retry_queue_updated for retried action"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        additional_info = {"order_id": "ORDER456"}
        result = self.notifier.notify_retry_queue_updated(
            symbol="RELIANCE",
            action="retried_successfully",
            retry_count=3,
            additional_info=additional_info,
        )

        self.assertTrue(result)
        message = mock_post.call_args[1]["json"]["text"]
        self.assertIn("retried_successfully", message)
        self.assertIn("3", message)

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.requests.post")
    def test_notify_retry_queue_updated_removed(self, mock_post):
        """Test notify_retry_queue_updated for removed action"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = self.notifier.notify_retry_queue_updated(
            symbol="RELIANCE",
            action="removed",
            retry_count=5,
        )

        self.assertTrue(result)
        message = mock_post.call_args[1]["json"]["text"]
        self.assertIn("removed", message)

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.requests.post")
    def test_rate_limit_per_minute(self, mock_post):
        """Test rate limiting per minute"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Send notifications up to limit
        for i in range(5):
            result = self.notifier.notify_order_placed(
                symbol=f"STOCK{i}",
                order_id=f"ORDER{i}",
                quantity=10,
            )
            self.assertTrue(result, f"Notification {i} should succeed")

        # Next notification should be rate limited
        result = self.notifier.notify_order_placed(
            symbol="STOCK6",
            order_id="ORDER6",
            quantity=10,
        )
        self.assertFalse(result, "Notification should be rate limited")
        self.assertEqual(mock_post.call_count, 5)

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.requests.post")
    def test_rate_limit_cleanup(self, mock_post):
        """Test that old timestamps are cleaned up"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Add old timestamps
        old_time = datetime.now() - timedelta(hours=2)
        self.notifier._notification_timestamps = [old_time] * 25

        # Check rate limit should clean up old timestamps
        can_send = self.notifier._check_rate_limit()
        self.assertTrue(can_send, "Should be able to send after cleanup")

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.requests.post")
    def test_rate_limit_per_hour(self, mock_post):
        """Test rate limiting per hour"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Add recent timestamps (within last hour) up to limit
        recent_time = datetime.now() - timedelta(minutes=30)
        self.notifier._notification_timestamps = [recent_time] * 20

        # Next notification should be rate limited
        result = self.notifier.notify_order_placed(
            symbol="STOCK",
            order_id="ORDER",
            quantity=10,
        )
        self.assertFalse(result, "Notification should be rate limited by hourly limit")

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.requests.post")
    def test_rate_limit_only_applies_to_successful_sends(self, mock_post):
        """Test that rate limit only tracks successful sends"""
        # First call fails
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_post.return_value = mock_response_fail

        result1 = self.notifier.notify_order_placed(
            symbol="STOCK1",
            order_id="ORDER1",
            quantity=10,
        )
        self.assertFalse(result1)
        self.assertEqual(len(self.notifier._notification_timestamps), 0)

        # Second call succeeds
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_post.return_value = mock_response_success

        result2 = self.notifier.notify_order_placed(
            symbol="STOCK2",
            order_id="ORDER2",
            quantity=10,
        )
        self.assertTrue(result2)
        self.assertEqual(len(self.notifier._notification_timestamps), 1)

    def test_notify_when_disabled(self):
        """Test that notifications are skipped when disabled"""
        notifier = TelegramNotifier(enabled=False)
        result = notifier.notify_order_placed(
            symbol="RELIANCE",
            order_id="ORDER123",
            quantity=10,
        )
        self.assertFalse(result)

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.requests.post")
    def test_notify_on_http_error(self, mock_post):
        """Test notification handling on HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        result = self.notifier.notify_order_placed(
            symbol="RELIANCE",
            order_id="ORDER123",
            quantity=10,
        )

        self.assertFalse(result)
        self.assertEqual(len(self.notifier._notification_timestamps), 0)

    @patch("modules.kotak_neo_auto_trader.telegram_notifier.requests.post")
    def test_notify_on_exception(self, mock_post):
        """Test notification handling on exception"""
        mock_post.side_effect = Exception("Network error")

        result = self.notifier.notify_order_placed(
            symbol="RELIANCE",
            order_id="ORDER123",
            quantity=10,
        )

        self.assertFalse(result)
        self.assertEqual(len(self.notifier._notification_timestamps), 0)

    def test_get_telegram_notifier_singleton(self):
        """Test singleton pattern for get_telegram_notifier"""
        # Clear singleton
        import modules.kotak_neo_auto_trader.telegram_notifier as mod

        mod._notifier_instance = None

        notifier1 = get_telegram_notifier()
        notifier2 = get_telegram_notifier()

        self.assertIs(notifier1, notifier2, "Should return same instance")


if __name__ == "__main__":
    unittest.main()
