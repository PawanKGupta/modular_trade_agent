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

import pytest  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from src.application.services.multi_user_trading_service import (
    MultiUserTradingService,  # noqa: E402
)
from src.infrastructure.db.models import Notification, UserNotificationPreferences  # noqa: E402


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
            patch.object(
                service,
                "_get_telegram_notifier",
                return_value=mock_telegram_notifier,
            ),
        ):
            service._notify_service_started(user_id=1)

        # Verify Telegram notification was sent
        mock_telegram_notifier.notify_system_alert.assert_called_once()
        call_args = mock_telegram_notifier.notify_system_alert.call_args
        assert call_args[1]["alert_type"] == "SERVICE_STARTED"
        assert "Unified Trading Service Started" in call_args[1]["message_text"]
        assert call_args[1]["user_id"] == 1
        assert call_args[1]["severity"] == "INFO"

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
            patch.object(
                service,
                "_get_telegram_notifier",
                return_value=mock_telegram_notifier,
            ),
        ):
            service._notify_service_stopped(user_id=1)

        # Verify Telegram notification was sent
        mock_telegram_notifier.notify_system_alert.assert_called_once()
        call_args = mock_telegram_notifier.notify_system_alert.call_args
        assert call_args[1]["alert_type"] == "SERVICE_STOPPED"
        assert "Unified Trading Service Stopped" in call_args[1]["message_text"]
        assert call_args[1]["user_id"] == 1
        assert call_args[1]["severity"] == "INFO"

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
            patch.object(
                service,
                "_get_telegram_notifier",
                return_value=mock_telegram_notifier,
            ),
            patch("src.application.services.multi_user_trading_service.get_user_logger"),
        ):
            service._notify_service_started(user_id=1)

        # Verify in-app notification was created
        mock_notification_repo.create.assert_called_once()

        # Verify Telegram notification was NOT sent
        mock_telegram_notifier.notify_system_alert.assert_not_called()


class TestGetTelegramNotifier:
    """Test suite for _get_telegram_notifier() method"""

    @pytest.fixture
    def service(self, db_session):
        """Create a MultiUserTradingService instance with real DB session"""
        return MultiUserTradingService(db=db_session)

    @pytest.fixture
    def sample_user(self, db_session):
        """Create a sample user"""
        from src.infrastructure.db.models import Users  # noqa: PLC0415
        from src.infrastructure.db.timezone_utils import ist_now  # noqa: PLC0415

        user = Users(
            email="test@example.com",
            password_hash="hashed_password",
            created_at=ist_now(),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    @pytest.fixture
    def user_with_telegram_prefs(self, db_session, sample_user):
        """Create user with Telegram preferences"""
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=True,
            telegram_chat_id="123456789",
            telegram_bot_token="test_bot_token_123",
        )
        db_session.add(prefs)
        db_session.commit()
        return sample_user

    def test_get_telegram_notifier_success_with_user_preferences(
        self, service, user_with_telegram_prefs
    ):
        """Test _get_telegram_notifier returns notifier when user has preferences"""
        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
        ) as mock_telegram_class:
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_telegram_class.return_value = mock_notifier

            notifier = service._get_telegram_notifier(user_with_telegram_prefs.id)

            assert notifier is not None
            assert notifier == mock_notifier
            mock_telegram_class.assert_called_once_with(
                bot_token="test_bot_token_123",
                chat_id="123456789",
                enabled=True,
                db_session=service.db,
            )

    def test_get_telegram_notifier_fallback_to_env_token(self, service, db_session, sample_user):
        """Test _get_telegram_notifier falls back to environment variable for bot token"""
        # Create preferences without bot_token
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=True,
            telegram_chat_id="123456789",
            telegram_bot_token=None,  # No user token
        )
        db_session.add(prefs)
        db_session.commit()

        with (
            patch(
                "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
            ) as mock_telegram_class,
            patch(
                "src.application.services.multi_user_trading_service.os.getenv",
                return_value="env_bot_token_456",
            ) as mock_getenv,
        ):
            mock_notifier = Mock()
            mock_notifier.enabled = True
            mock_telegram_class.return_value = mock_notifier

            notifier = service._get_telegram_notifier(sample_user.id)

            assert notifier is not None
            mock_getenv.assert_called_once_with("TELEGRAM_BOT_TOKEN")
            mock_telegram_class.assert_called_once_with(
                bot_token="env_bot_token_456",
                chat_id="123456789",
                enabled=True,
                db_session=service.db,
            )

    def test_get_telegram_notifier_returns_none_when_telegram_disabled(
        self, service, db_session, sample_user
    ):
        """Test _get_telegram_notifier returns None when Telegram is disabled"""
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=False,  # Disabled
            telegram_chat_id="123456789",
            telegram_bot_token="test_token",
        )
        db_session.add(prefs)
        db_session.commit()

        notifier = service._get_telegram_notifier(sample_user.id)

        assert notifier is None

    def test_get_telegram_notifier_returns_none_when_no_bot_token(
        self, service, db_session, sample_user
    ):
        """Test _get_telegram_notifier returns None when no bot token available"""
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=True,
            telegram_chat_id="123456789",
            telegram_bot_token=None,  # No user token
        )
        db_session.add(prefs)
        db_session.commit()

        with patch(
            "src.application.services.multi_user_trading_service.os.getenv",
            return_value=None,
        ):  # No env token either
            notifier = service._get_telegram_notifier(sample_user.id)

            assert notifier is None

    def test_get_telegram_notifier_returns_none_when_no_chat_id(
        self, service, db_session, sample_user
    ):
        """Test _get_telegram_notifier returns None when no chat ID"""
        prefs = UserNotificationPreferences(
            user_id=sample_user.id,
            telegram_enabled=True,
            telegram_chat_id=None,  # No chat ID
            telegram_bot_token="test_token",
        )
        db_session.add(prefs)
        db_session.commit()

        notifier = service._get_telegram_notifier(sample_user.id)

        assert notifier is None

    def test_get_telegram_notifier_returns_none_when_no_preferences(self, service, sample_user):
        """Test _get_telegram_notifier returns None when user has no preferences"""
        notifier = service._get_telegram_notifier(sample_user.id)

        assert notifier is None

    def test_get_telegram_notifier_handles_import_error(self, service, user_with_telegram_prefs):
        """Test _get_telegram_notifier handles ImportError gracefully"""
        with patch(
            "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier",
            side_effect=ImportError("Module not found"),
        ):
            notifier = service._get_telegram_notifier(user_with_telegram_prefs.id)

            assert notifier is None

    def test_get_telegram_notifier_handles_exceptions_gracefully(
        self, service, user_with_telegram_prefs
    ):
        """Test _get_telegram_notifier handles exceptions and logs warnings"""
        with (
            patch(
                "src.application.services.multi_user_trading_service.NotificationPreferenceService"
            ) as mock_pref_service,
            patch(
                "src.application.services.multi_user_trading_service.get_user_logger"
            ) as mock_logger,
        ):
            # Make get_preferences raise an exception
            mock_pref_service.return_value.get_preferences.side_effect = Exception("Database error")

            notifier = service._get_telegram_notifier(user_with_telegram_prefs.id)

            assert notifier is None
            # Verify error was logged
            mock_logger.return_value.warning.assert_called_once()
            assert "Failed to get Telegram notifier" in str(
                mock_logger.return_value.warning.call_args
            )

    def test_get_telegram_notifier_uses_user_bot_token_over_env(
        self, service, user_with_telegram_prefs
    ):
        """Test _get_telegram_notifier prefers user bot_token over environment variable"""
        with (
            patch(
                "modules.kotak_neo_auto_trader.telegram_notifier.TelegramNotifier"
            ) as mock_telegram_class,
            patch(
                "src.application.services.multi_user_trading_service.os.getenv",
                return_value="env_token_should_not_be_used",
            ),
        ):
            mock_notifier = Mock()
            mock_telegram_class.return_value = mock_notifier

            notifier = service._get_telegram_notifier(user_with_telegram_prefs.id)

            assert notifier is not None
            # Verify user token was used, not env token
            call_kwargs = mock_telegram_class.call_args[1]
            assert call_kwargs["bot_token"] == "test_bot_token_123"
            assert call_kwargs["bot_token"] != "env_token_should_not_be_used"
