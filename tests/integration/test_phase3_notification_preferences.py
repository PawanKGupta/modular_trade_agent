"""
Integration Tests for Phase 3: Notification Preferences

Tests the integration of NotificationPreferenceService with TelegramNotifier
to verify that notifications are filtered based on user preferences.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from sqlalchemy.orm import Session

from modules.kotak_neo_auto_trader.telegram_notifier import TelegramNotifier
from services.notification_preference_service import (
    NotificationEventType,
    NotificationPreferenceService,
)


class TestPhase3NotificationPreferences:
    """Integration tests for Phase 3 notification preferences"""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        session = Mock(spec=Session)
        session.query = Mock()
        return session

    @pytest.fixture
    def mock_preference_service(self):
        """Create a mock NotificationPreferenceService"""
        service = Mock(spec=NotificationPreferenceService)
        # Default behavior: allow all notifications
        service.should_notify = Mock(return_value=True)
        return service

    @pytest.fixture
    def telegram_notifier(self, mock_db_session, mock_preference_service):
        """Create TelegramNotifier with mocked preference service"""
        notifier = TelegramNotifier(
            bot_token="test_token",
            chat_id="test_chat_id",
            enabled=True,
            db_session=mock_db_session,
            preference_service=mock_preference_service,
        )
        # Mock the actual Telegram API call
        notifier.send_message = Mock(return_value=True)
        return notifier

    @pytest.fixture
    def telegram_notifier_no_preferences(self):
        """Create TelegramNotifier without preference service (backward compatibility)"""
        notifier = TelegramNotifier(
            bot_token="test_token",
            chat_id="test_chat_id",
            enabled=True,
        )
        notifier.send_message = Mock(return_value=True)
        return notifier

    def test_notify_order_placed_with_preferences_enabled(
        self, telegram_notifier, mock_preference_service
    ):
        """Test that order placed notification is sent when preferences allow it"""
        mock_preference_service.should_notify.return_value = True

        result = telegram_notifier.notify_order_placed(
            symbol="RELIANCE",
            order_id="12345",
            quantity=10,
            user_id=1,
        )

        assert result is True
        mock_preference_service.should_notify.assert_called_once_with(
            user_id=1, event_type=NotificationEventType.ORDER_PLACED, channel="telegram"
        )
        telegram_notifier.send_message.assert_called_once()

    def test_notify_order_placed_with_preferences_disabled(
        self, telegram_notifier, mock_preference_service
    ):
        """Test that order placed notification is NOT sent when preferences disable it"""
        mock_preference_service.should_notify.return_value = False

        result = telegram_notifier.notify_order_placed(
            symbol="RELIANCE",
            order_id="12345",
            quantity=10,
            user_id=1,
        )

        assert result is False
        mock_preference_service.should_notify.assert_called_once_with(
            user_id=1, event_type=NotificationEventType.ORDER_PLACED, channel="telegram"
        )
        telegram_notifier.send_message.assert_not_called()

    def test_notify_order_placed_backward_compatibility_no_user_id(
        self, telegram_notifier_no_preferences
    ):
        """Test backward compatibility: notification sent when user_id is None"""
        result = telegram_notifier_no_preferences.notify_order_placed(
            symbol="RELIANCE",
            order_id="12345",
            quantity=10,
            user_id=None,  # No user_id - should send
        )

        assert result is True
        telegram_notifier_no_preferences.send_message.assert_called_once()

    def test_notify_order_rejection_with_preferences(
        self, telegram_notifier, mock_preference_service
    ):
        """Test order rejection notification respects preferences"""
        mock_preference_service.should_notify.return_value = True

        result = telegram_notifier.notify_order_rejection(
            symbol="RELIANCE",
            order_id="12345",
            quantity=10,
            rejection_reason="Insufficient funds",
            user_id=1,
        )

        assert result is True
        mock_preference_service.should_notify.assert_called_once_with(
            user_id=1, event_type=NotificationEventType.ORDER_REJECTED, channel="telegram"
        )

    def test_notify_order_execution_with_preferences(
        self, telegram_notifier, mock_preference_service
    ):
        """Test order execution notification respects preferences"""
        mock_preference_service.should_notify.return_value = True

        result = telegram_notifier.notify_order_execution(
            symbol="RELIANCE",
            order_id="12345",
            quantity=10,
            executed_price=2500.50,
            user_id=1,
        )

        assert result is True
        mock_preference_service.should_notify.assert_called_once_with(
            user_id=1, event_type=NotificationEventType.ORDER_EXECUTED, channel="telegram"
        )

    def test_notify_order_cancelled_with_preferences(
        self, telegram_notifier, mock_preference_service
    ):
        """Test order cancellation notification respects preferences"""
        mock_preference_service.should_notify.return_value = True

        result = telegram_notifier.notify_order_cancelled(
            symbol="RELIANCE",
            order_id="12345",
            cancellation_reason="User cancelled",
            user_id=1,
        )

        assert result is True
        mock_preference_service.should_notify.assert_called_once_with(
            user_id=1, event_type=NotificationEventType.ORDER_CANCELLED, channel="telegram"
        )

    def test_notify_partial_fill_with_preferences(self, telegram_notifier, mock_preference_service):
        """Test partial fill notification respects preferences"""
        mock_preference_service.should_notify.return_value = True

        result = telegram_notifier.notify_partial_fill(
            symbol="RELIANCE",
            order_id="12345",
            filled_qty=5,
            total_qty=10,
            remaining_qty=5,
            user_id=1,
        )

        assert result is True
        mock_preference_service.should_notify.assert_called_once_with(
            user_id=1, event_type=NotificationEventType.PARTIAL_FILL, channel="telegram"
        )

    def test_notify_retry_queue_updated_maps_actions(
        self, telegram_notifier, mock_preference_service
    ):
        """Test that retry queue updated maps actions to correct event types"""
        mock_preference_service.should_notify.return_value = True

        # Test "added" action
        telegram_notifier.notify_retry_queue_updated(
            symbol="RELIANCE",
            action="added",
            user_id=1,
        )
        mock_preference_service.should_notify.assert_called_with(
            user_id=1, event_type=NotificationEventType.RETRY_QUEUE_ADDED, channel="telegram"
        )

        # Test "updated" action
        mock_preference_service.should_notify.reset_mock()
        telegram_notifier.notify_retry_queue_updated(
            symbol="RELIANCE",
            action="updated",
            user_id=1,
        )
        mock_preference_service.should_notify.assert_called_with(
            user_id=1, event_type=NotificationEventType.RETRY_QUEUE_UPDATED, channel="telegram"
        )

        # Test "removed" action
        mock_preference_service.should_notify.reset_mock()
        telegram_notifier.notify_retry_queue_updated(
            symbol="RELIANCE",
            action="removed",
            user_id=1,
        )
        mock_preference_service.should_notify.assert_called_with(
            user_id=1, event_type=NotificationEventType.RETRY_QUEUE_REMOVED, channel="telegram"
        )

        # Test "retried" action
        mock_preference_service.should_notify.reset_mock()
        telegram_notifier.notify_retry_queue_updated(
            symbol="RELIANCE",
            action="retried",
            user_id=1,
        )
        mock_preference_service.should_notify.assert_called_with(
            user_id=1, event_type=NotificationEventType.RETRY_QUEUE_RETRIED, channel="telegram"
        )

    def test_notify_system_alert_maps_severity(self, telegram_notifier, mock_preference_service):
        """Test that system alert maps severity to correct event types"""
        mock_preference_service.should_notify.return_value = True

        # Test ERROR severity
        telegram_notifier.notify_system_alert(
            alert_type="Database Error",
            message_text="Connection failed",
            severity="ERROR",
            user_id=1,
        )
        mock_preference_service.should_notify.assert_called_with(
            user_id=1, event_type=NotificationEventType.SYSTEM_ERROR, channel="telegram"
        )

        # Test WARNING severity
        mock_preference_service.should_notify.reset_mock()
        telegram_notifier.notify_system_alert(
            alert_type="Rate Limit",
            message_text="Approaching rate limit",
            severity="WARNING",
            user_id=1,
        )
        mock_preference_service.should_notify.assert_called_with(
            user_id=1, event_type=NotificationEventType.SYSTEM_WARNING, channel="telegram"
        )

        # Test INFO severity
        mock_preference_service.should_notify.reset_mock()
        telegram_notifier.notify_system_alert(
            alert_type="Service Started",
            message_text="Trading service started",
            severity="INFO",
            user_id=1,
        )
        mock_preference_service.should_notify.assert_called_with(
            user_id=1, event_type=NotificationEventType.SYSTEM_INFO, channel="telegram"
        )

    def test_preference_service_error_handling(self, telegram_notifier, mock_preference_service):
        """Test that preference service errors don't block notifications (fail open)"""
        # Simulate preference service error
        mock_preference_service.should_notify.side_effect = Exception("Database error")

        # Should still send notification (fail open)
        result = telegram_notifier.notify_order_placed(
            symbol="RELIANCE",
            order_id="12345",
            quantity=10,
            user_id=1,
        )

        assert result is True
        telegram_notifier.send_message.assert_called_once()

    def test_no_preference_service_backward_compatibility(self, telegram_notifier_no_preferences):
        """Test backward compatibility when preference service is not available"""
        # No preference service - should send notification
        result = telegram_notifier_no_preferences.notify_order_placed(
            symbol="RELIANCE",
            order_id="12345",
            quantity=10,
            user_id=1,  # user_id provided but no preference service
        )

        assert result is True
        telegram_notifier_no_preferences.send_message.assert_called_once()

    def test_all_notification_methods_respect_preferences(
        self, telegram_notifier, mock_preference_service
    ):
        """Test that all notification methods check preferences"""
        mock_preference_service.should_notify.return_value = False  # Disable all

        # All should return False without sending
        assert telegram_notifier.notify_order_placed("RELIANCE", "123", 10, user_id=1) is False
        assert (
            telegram_notifier.notify_order_rejection("RELIANCE", "123", 10, "Reason", user_id=1)
            is False
        )
        assert telegram_notifier.notify_order_execution("RELIANCE", "123", 10, user_id=1) is False
        assert (
            telegram_notifier.notify_order_cancelled("RELIANCE", "123", "Reason", user_id=1)
            is False
        )
        assert (
            telegram_notifier.notify_partial_fill("RELIANCE", "123", 5, 10, 5, user_id=1) is False
        )
        assert telegram_notifier.notify_retry_queue_updated("RELIANCE", "added", user_id=1) is False
        assert telegram_notifier.notify_system_alert("Test", "Message", "ERROR", user_id=1) is False

        # None should have called send_message
        assert telegram_notifier.send_message.call_count == 0

    def test_preference_service_auto_creation(self, mock_db_session):
        """Test that preference service is auto-created from db_session"""
        notifier = TelegramNotifier(
            bot_token="test_token",
            chat_id="test_chat_id",
            enabled=True,
            db_session=mock_db_session,
        )

        assert notifier.preference_service is not None
        assert isinstance(notifier.preference_service, NotificationPreferenceService)

    def test_preference_service_not_created_without_db_session(self):
        """Test that preference service is not created without db_session"""
        notifier = TelegramNotifier(
            bot_token="test_token",
            chat_id="test_chat_id",
            enabled=True,
        )

        assert notifier.preference_service is None

    def test_multiple_notifications_same_user(self, telegram_notifier, mock_preference_service):
        """Test multiple notifications for same user"""
        mock_preference_service.should_notify.return_value = True

        # Send multiple notifications
        telegram_notifier.notify_order_placed("RELIANCE", "123", 10, user_id=1)
        telegram_notifier.notify_order_execution("RELIANCE", "123", 10, user_id=1)
        telegram_notifier.notify_order_rejection("RELIANCE", "124", 10, "Reason", user_id=1)

        # Should check preferences for each
        assert mock_preference_service.should_notify.call_count == 3
        assert telegram_notifier.send_message.call_count == 3

    def test_different_users_different_preferences(
        self, telegram_notifier, mock_preference_service
    ):
        """Test that different users can have different preferences"""
        # User 1: allow notifications
        mock_preference_service.should_notify.side_effect = lambda user_id, **kwargs: user_id == 1

        assert telegram_notifier.notify_order_placed("RELIANCE", "123", 10, user_id=1) is True
        assert telegram_notifier.notify_order_placed("RELIANCE", "123", 10, user_id=2) is False

        # Only user 1's notification should be sent
        assert telegram_notifier.send_message.call_count == 1

    def test_notify_order_modified_with_preferences(
        self, telegram_notifier, mock_preference_service
    ):
        """Test order modification notification respects preferences"""
        mock_preference_service.should_notify.return_value = True

        changes = {
            "quantity": (10, 15),
            "price": (2500.0, 2550.0),
        }

        result = telegram_notifier.notify_order_modified(
            symbol="RELIANCE",
            order_id="12345",
            changes=changes,
            user_id=1,
        )

        assert result is True
        mock_preference_service.should_notify.assert_called_once_with(
            user_id=1, event_type=NotificationEventType.ORDER_MODIFIED, channel="telegram"
        )
        telegram_notifier.send_message.assert_called_once()

    def test_notify_order_modified_preferences_disabled(
        self, telegram_notifier, mock_preference_service
    ):
        """Test order modification notification is NOT sent when preferences disable it"""
        mock_preference_service.should_notify.return_value = False

        changes = {"quantity": (10, 15)}

        result = telegram_notifier.notify_order_modified(
            symbol="RELIANCE",
            order_id="12345",
            changes=changes,
            user_id=1,
        )

        assert result is False
        telegram_notifier.send_message.assert_not_called()

    def test_notify_order_modified_backward_compatibility(self, telegram_notifier_no_preferences):
        """Test backward compatibility: order modification sent when user_id is None"""
        changes = {"quantity": (10, 15)}

        result = telegram_notifier_no_preferences.notify_order_modified(
            symbol="RELIANCE",
            order_id="12345",
            changes=changes,
            user_id=None,
        )

        assert result is True
        telegram_notifier_no_preferences.send_message.assert_called_once()

    def test_notify_order_modified_formats_changes_correctly(
        self, telegram_notifier, mock_preference_service
    ):
        """Test that order modification notification formats changes correctly"""
        mock_preference_service.should_notify.return_value = True

        changes = {
            "quantity": (10, 15),
            "price": (2500.50, 2550.75),
        }

        telegram_notifier.notify_order_modified(
            symbol="RELIANCE",
            order_id="12345",
            changes=changes,
            user_id=1,
        )

        # Verify message was sent
        assert telegram_notifier.send_message.call_count == 1
        call_args = telegram_notifier.send_message.call_args
        message = call_args[0][0]  # First positional argument

        # Check message contains formatted changes
        assert "ORDER MODIFIED" in message
        assert "RELIANCE" in message
        assert "12345" in message
        assert "Quantity: 10 → 15" in message
        assert "Price: Rs 2500.50 → Rs 2550.75" in message

    def test_notify_order_modified_with_additional_info(
        self, telegram_notifier, mock_preference_service
    ):
        """Test order modification notification with additional info"""
        mock_preference_service.should_notify.return_value = True

        changes = {"quantity": (10, 15)}
        additional_info = {"reason": "User adjusted quantity", "source": "broker_app"}

        result = telegram_notifier.notify_order_modified(
            symbol="RELIANCE",
            order_id="12345",
            changes=changes,
            additional_info=additional_info,
            user_id=1,
        )

        assert result is True
        call_args = telegram_notifier.send_message.call_args
        message = call_args[0][0]
        assert "reason" in message
        assert "broker_app" in message
