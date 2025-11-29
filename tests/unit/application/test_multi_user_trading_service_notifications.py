"""
Unit tests for MultiUserTradingService notification methods

Tests that unified service notifications are sent correctly when service starts/stops.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from sqlalchemy.orm import Session

from src.application.services.multi_user_trading_service import MultiUserTradingService
from src.infrastructure.db.models import Notification, UserNotificationPreferences


class TestMultiUserTradingServiceNotifications:
    """Test suite for unified service notifications"""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        session = Mock(spec=Session)
        session.query = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.refresh = Mock()
        return session

    @pytest.fixture
    def service(self, mock_db_session):
        """Create a MultiUserTradingService instance"""
        return MultiUserTradingService(db=mock_db_session)

    @pytest.fixture
    def mock_preference_service(self):
        """Create a mock NotificationPreferenceService"""
        service = Mock()
        service.get_preferences.return_value = UserNotificationPreferences(
            user_id=1,
            telegram_enabled=True,
            telegram_chat_id="123",
            email_enabled=True,
            email_address="test@example.com",
            in_app_enabled=True,
            notify_service_started=True,
            notify_service_stopped=True,
            notify_service_execution_completed=True,
        )
        service.should_notify.side_effect = lambda user_id, event_type, channel: (
            (
                channel == "telegram"
                and service.get_preferences(user_id).telegram_enabled
                and getattr(service.get_preferences(user_id), f"notify_{event_type}", False)
            )
            or (
                channel == "email"
                and service.get_preferences(user_id).email_enabled
                and getattr(service.get_preferences(user_id), f"notify_{event_type}", False)
            )
            or (
                channel == "in_app"
                and service.get_preferences(user_id).in_app_enabled
                and getattr(service.get_preferences(user_id), f"notify_{event_type}", False)
            )
        )
        return service

    @pytest.fixture
    def mock_notification_repo(self):
        """Create a mock NotificationRepository"""
        repo = Mock()
        notification = Notification(
            id=1,
            user_id=1,
            type="service",
            level="info",
            title="Unified Service Started",
            message="Test message",
            read=False,
        )
        repo.create.return_value = notification
        return repo

    @pytest.fixture
    def mock_telegram_notifier(self):
        """Create a mock TelegramNotifier"""
        notifier = Mock()
        notifier.enabled = True
        notifier.notify_system_alert = Mock(return_value=True)
        return notifier

    @pytest.fixture
    def mock_email_notifier(self):
        """Create a mock EmailNotifier"""
        notifier = Mock()
        notifier.is_available = Mock(return_value=True)
        notifier.send_service_notification = Mock(return_value=True)
        return notifier

    def test_notify_service_started_creates_in_app_notification(
        self, service, mock_preference_service, mock_notification_repo
    ):
        """Test that service started creates an in-app notification"""
        service._notification_repo = mock_notification_repo

        with (
            patch(
                "src.application.services.multi_user_trading_service.NotificationPreferenceService",
                return_value=mock_preference_service,
            ),
            patch("src.application.services.multi_user_trading_service.get_user_logger"),
        ):
            service._notify_service_started(user_id=1)

        # Verify notification was created
        mock_notification_repo.create.assert_called_once()
        call_args = mock_notification_repo.create.call_args
        assert call_args[1]["user_id"] == 1
        assert call_args[1]["type"] == "service"
        assert call_args[1]["level"] == "info"
        assert call_args[1]["title"] == "Unified Service Started"
        assert "Unified Trading Service" in call_args[1]["message"]

        # Verify preference service was checked (at least once for in_app)
        in_app_calls = [
            call
            for call in mock_preference_service.should_notify.call_args_list
            if call[1].get("channel") == "in_app" or (len(call[0]) > 2 and call[0][2] == "in_app")
        ]
        assert len(in_app_calls) > 0

    def test_notify_service_started_respects_preferences(
        self, service, mock_preference_service, mock_notification_repo
    ):
        """Test that service started respects notification preferences"""
        service._notification_repo = mock_notification_repo

        # Disable in-app notifications
        mock_preference_service.should_notify.side_effect = (
            lambda user_id, event_type, channel: False
        )

        with patch(
            "src.application.services.multi_user_trading_service.NotificationPreferenceService",
            return_value=mock_preference_service,
        ):
            service._notify_service_started(user_id=1)

        # Verify notification was NOT created
        mock_notification_repo.create.assert_not_called()

    def test_notify_service_started_sends_telegram(
        self, service, mock_preference_service, mock_telegram_notifier
    ):
        """Test that service started sends Telegram notification"""
        with (
            patch(
                "src.application.services.multi_user_trading_service.NotificationPreferenceService",
                return_value=mock_preference_service,
            ),
            patch(
                "modules.kotak_neo_auto_trader.telegram_notifier.get_telegram_notifier",
                return_value=mock_telegram_notifier,
            ),
        ):
            service._notify_service_started(user_id=1)

        # Verify Telegram notification was sent
        mock_telegram_notifier.notify_system_alert.assert_called_once()
        call_args = mock_telegram_notifier.notify_system_alert.call_args
        assert "Unified Trading Service Started" in call_args[0][0]
        assert call_args[1]["user_id"] == 1

        # Verify preference service was checked for telegram
        telegram_calls = [
            call
            for call in mock_preference_service.should_notify.call_args_list
            if call[1].get("channel") == "telegram"
            or (len(call[0]) > 2 and call[0][2] == "telegram")
        ]
        assert len(telegram_calls) > 0

    def test_notify_service_started_sends_email(
        self, service, mock_preference_service, mock_email_notifier
    ):
        """Test that service started sends email notification"""
        with (
            patch(
                "src.application.services.multi_user_trading_service.NotificationPreferenceService",
                return_value=mock_preference_service,
            ),
            patch(
                "services.email_notifier.EmailNotifier",
                return_value=mock_email_notifier,
            ),
        ):
            service._notify_service_started(user_id=1)

        # Verify email notification was sent
        mock_email_notifier.send_service_notification.assert_called_once()
        call_args = mock_email_notifier.send_service_notification.call_args
        assert call_args[1]["email"] == "test@example.com"
        assert "Unified Trading Service Started" in call_args[1]["title"]
        assert call_args[1]["level"] == "info"

        # Verify preference service was checked for email
        email_calls = [
            call
            for call in mock_preference_service.should_notify.call_args_list
            if call[1].get("channel") == "email" or (len(call[0]) > 2 and call[0][2] == "email")
        ]
        assert len(email_calls) > 0

    def test_notify_service_stopped_creates_in_app_notification(
        self, service, mock_preference_service, mock_notification_repo
    ):
        """Test that service stopped creates an in-app notification"""
        service._notification_repo = mock_notification_repo

        with (
            patch(
                "src.application.services.multi_user_trading_service.NotificationPreferenceService",
                return_value=mock_preference_service,
            ),
            patch("src.application.services.multi_user_trading_service.get_user_logger"),
        ):
            service._notify_service_stopped(user_id=1)

        # Verify notification was created
        mock_notification_repo.create.assert_called_once()
        call_args = mock_notification_repo.create.call_args
        assert call_args[1]["user_id"] == 1
        assert call_args[1]["type"] == "service"
        assert call_args[1]["level"] == "info"
        assert call_args[1]["title"] == "Unified Service Stopped"
        assert "Unified Trading Service" in call_args[1]["message"]

        # Verify preference service was checked (at least once for in_app)
        in_app_calls = [
            call
            for call in mock_preference_service.should_notify.call_args_list
            if call[1].get("channel") == "in_app" or (len(call[0]) > 2 and call[0][2] == "in_app")
        ]
        assert len(in_app_calls) > 0

    def test_notify_service_stopped_respects_preferences(
        self, service, mock_preference_service, mock_notification_repo
    ):
        """Test that service stopped respects notification preferences"""
        service._notification_repo = mock_notification_repo

        # Disable in-app notifications
        mock_preference_service.should_notify.side_effect = (
            lambda user_id, event_type, channel: False
        )

        with patch(
            "src.application.services.multi_user_trading_service.NotificationPreferenceService",
            return_value=mock_preference_service,
        ):
            service._notify_service_stopped(user_id=1)

        # Verify notification was NOT created
        mock_notification_repo.create.assert_not_called()

    def test_notify_service_stopped_sends_telegram(
        self, service, mock_preference_service, mock_telegram_notifier
    ):
        """Test that service stopped sends Telegram notification"""
        with (
            patch(
                "src.application.services.multi_user_trading_service.NotificationPreferenceService",
                return_value=mock_preference_service,
            ),
            patch(
                "modules.kotak_neo_auto_trader.telegram_notifier.get_telegram_notifier",
                return_value=mock_telegram_notifier,
            ),
        ):
            service._notify_service_stopped(user_id=1)

        # Verify Telegram notification was sent
        mock_telegram_notifier.notify_system_alert.assert_called_once()
        call_args = mock_telegram_notifier.notify_system_alert.call_args
        assert "Unified Trading Service Stopped" in call_args[0][0]
        assert call_args[1]["user_id"] == 1

        # Verify preference service was checked for telegram
        telegram_calls = [
            call
            for call in mock_preference_service.should_notify.call_args_list
            if call[1].get("channel") == "telegram"
            or (len(call[0]) > 2 and call[0][2] == "telegram")
        ]
        assert len(telegram_calls) > 0

    def test_notify_service_stopped_sends_email(
        self, service, mock_preference_service, mock_email_notifier
    ):
        """Test that service stopped sends email notification"""
        with (
            patch(
                "src.application.services.multi_user_trading_service.NotificationPreferenceService",
                return_value=mock_preference_service,
            ),
            patch(
                "services.email_notifier.EmailNotifier",
                return_value=mock_email_notifier,
            ),
        ):
            service._notify_service_stopped(user_id=1)

        # Verify email notification was sent
        mock_email_notifier.send_service_notification.assert_called_once()
        call_args = mock_email_notifier.send_service_notification.call_args
        assert call_args[1]["email"] == "test@example.com"
        assert "Unified Trading Service Stopped" in call_args[1]["title"]
        assert call_args[1]["level"] == "info"

        # Verify preference service was checked for email
        email_calls = [
            call
            for call in mock_preference_service.should_notify.call_args_list
            if call[1].get("channel") == "email" or (len(call[0]) > 2 and call[0][2] == "email")
        ]
        assert len(email_calls) > 0

    def test_notify_service_started_handles_errors_gracefully(
        self, service, mock_preference_service
    ):
        """Test that notification errors don't crash the service"""
        # Make notification creation fail
        service._notification_repo = Mock()
        service._notification_repo.create.side_effect = Exception("Database error")

        with (
            patch(
                "src.application.services.multi_user_trading_service.NotificationPreferenceService",
                return_value=mock_preference_service,
            ),
            patch(
                "src.application.services.multi_user_trading_service.get_user_logger"
            ) as mock_logger,
        ):
            # Should not raise exception
            service._notify_service_started(user_id=1)

        # Verify error was logged
        mock_logger.return_value.error.assert_called()

    def test_notify_service_stopped_handles_errors_gracefully(
        self, service, mock_preference_service
    ):
        """Test that notification errors don't crash the service"""
        # Make notification creation fail
        service._notification_repo = Mock()
        service._notification_repo.create.side_effect = Exception("Database error")

        with (
            patch(
                "src.application.services.multi_user_trading_service.NotificationPreferenceService",
                return_value=mock_preference_service,
            ),
            patch(
                "src.application.services.multi_user_trading_service.get_user_logger"
            ) as mock_logger,
        ):
            # Should not raise exception
            service._notify_service_stopped(user_id=1)

        # Verify error was logged
        mock_logger.return_value.error.assert_called()

    def test_notify_service_started_channel_specific_preferences(
        self, service, mock_preference_service, mock_notification_repo, mock_telegram_notifier
    ):
        """Test that notifications respect channel-specific preferences"""
        service._notification_repo = mock_notification_repo

        # Disable Telegram, enable In-App
        mock_preference_service.get_preferences.return_value.telegram_enabled = False
        mock_preference_service.get_preferences.return_value.in_app_enabled = True
        mock_preference_service.should_notify.side_effect = lambda user_id, event_type, channel: (
            channel == "in_app"
        )

        with (
            patch(
                "src.application.services.multi_user_trading_service.NotificationPreferenceService",
                return_value=mock_preference_service,
            ),
            patch(
                "modules.kotak_neo_auto_trader.telegram_notifier.get_telegram_notifier",
                return_value=mock_telegram_notifier,
            ),
            patch("src.application.services.multi_user_trading_service.get_user_logger"),
        ):
            service._notify_service_started(user_id=1)

        # Verify in-app notification was created
        mock_notification_repo.create.assert_called_once()

        # Verify Telegram notification was NOT sent
        mock_telegram_notifier.notify_system_alert.assert_not_called()
