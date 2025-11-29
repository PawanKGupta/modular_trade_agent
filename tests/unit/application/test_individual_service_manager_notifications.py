"""
Unit tests for IndividualServiceManager - Service Notifications

Tests for:
- Service started notifications with granular preferences
- Service stopped notifications with granular preferences
- Service execution completed notifications with granular preferences
- Multi-channel notification support (Telegram, Email, In-App)
"""

from unittest.mock import Mock, patch

import pytest

from services.notification_preference_service import (
    NotificationPreferenceService,
)
from src.application.services.individual_service_manager import (
    IndividualServiceManager,
)
from src.infrastructure.db.models import UserNotificationPreferences


class TestIndividualServiceManagerNotifications:
    """Test suite for IndividualServiceManager service notifications"""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        session = Mock()
        session.query = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.refresh = Mock()
        return session

    @pytest.fixture
    def sample_preferences(self):
        """Create sample notification preferences"""
        return UserNotificationPreferences(
            id=1,
            user_id=1,
            telegram_enabled=True,
            telegram_chat_id="123456789",
            email_enabled=True,
            email_address="test@example.com",
            in_app_enabled=True,
            notify_service_started=True,
            notify_service_stopped=True,
            notify_service_execution_completed=True,
        )

    @pytest.fixture
    def manager(self, mock_db_session):
        """Create IndividualServiceManager instance"""
        manager = IndividualServiceManager(mock_db_session)
        # Mock repositories
        manager._notification_repo = Mock()
        manager._notification_repo.create = Mock(return_value=Mock(id=1))
        manager._notification_repo.update_delivery_status = Mock()
        return manager

    @patch("src.application.services.individual_service_manager.EmailNotifier")
    @patch("src.application.services.individual_service_manager.EMAIL_NOTIFIER_AVAILABLE", True)
    def test_notify_service_started_respects_preferences(
        self, mock_email_notifier_class, manager, mock_db_session, sample_preferences
    ):
        """Test that service started notifications respect granular preferences"""
        # Setup preference service mock
        pref_service = Mock(spec=NotificationPreferenceService)
        pref_service.get_preferences = Mock(return_value=sample_preferences)
        pref_service.should_notify = Mock(return_value=True)

        # Mock telegram notifier - patch the method on the manager instance
        mock_telegram_notifier = Mock()
        mock_telegram_notifier.enabled = True
        mock_telegram_notifier.notify_system_alert = Mock()
        manager._get_telegram_notifier = Mock(return_value=mock_telegram_notifier)

        # Mock email notifier
        mock_email_notifier = Mock()
        mock_email_notifier.is_available.return_value = True
        mock_email_notifier.send_service_notification.return_value = True
        mock_email_notifier_class.return_value = mock_email_notifier

        # Patch NotificationPreferenceService where it's instantiated (inside the method)
        with patch(
            "services.notification_preference_service.NotificationPreferenceService",
            return_value=pref_service,
        ):
            manager._notify_service_started(user_id=1, task_name="analysis", process_id=12345)

        # Verify preference service was called with correct event type
        # Check that should_notify was called at least 3 times (once for each channel)
        assert (
            pref_service.should_notify.call_count >= 3
        ), f"should_notify should be called at least 3 times, got {pref_service.should_notify.call_count}"

        # Check that it was called for each channel by examining call arguments
        call_args_list = pref_service.should_notify.call_args_list
        channels_called = set()
        for call in call_args_list:
            # Check keyword arguments first (channel is passed as keyword arg)
            if "channel" in call[1]:
                channels_called.add(call[1]["channel"])
            # Also check positional arguments (in case channel is passed positionally)
            elif len(call[0]) > 2:
                channels_called.add(call[0][2])

        assert (
            "telegram" in channels_called
        ), f"should_notify should be called for telegram channel. Channels called: {channels_called}. All calls: {call_args_list}"
        assert (
            "in_app" in channels_called
        ), f"should_notify should be called for in_app channel. Channels called: {channels_called}. All calls: {call_args_list}"
        assert (
            "email" in channels_called
        ), f"should_notify should be called for email channel. Channels called: {channels_called}. All calls: {call_args_list}"

        # Verify notifications were sent
        mock_telegram_notifier.notify_system_alert.assert_called_once()
        mock_email_notifier.send_service_notification.assert_called_once()
        manager._notification_repo.create.assert_called_once()

    @patch("src.application.services.individual_service_manager.get_telegram_notifier")
    def test_notify_service_started_preference_disabled(
        self, mock_get_telegram_notifier, manager, mock_db_session, sample_preferences
    ):
        """Test that service started notifications are skipped when preference is disabled"""
        # Setup preference service mock to return False
        pref_service = Mock(spec=NotificationPreferenceService)
        pref_service.get_preferences = Mock(return_value=sample_preferences)
        pref_service.should_notify = Mock(return_value=False)  # Preference disabled

        # Patch NotificationPreferenceService where it's imported
        with patch(
            "services.notification_preference_service.NotificationPreferenceService",
            return_value=pref_service,
        ):
            manager._notify_service_started(user_id=1, task_name="analysis", process_id=12345)

        # Verify notifications were NOT sent
        mock_get_telegram_notifier.assert_not_called()
        manager._notification_repo.create.assert_not_called()

    @patch("src.application.services.individual_service_manager.EmailNotifier")
    @patch("src.application.services.individual_service_manager.EMAIL_NOTIFIER_AVAILABLE", True)
    def test_notify_service_stopped_respects_preferences(
        self, mock_email_notifier_class, manager, mock_db_session, sample_preferences
    ):
        """Test that service stopped notifications respect granular preferences"""
        # Setup preference service mock
        pref_service = Mock(spec=NotificationPreferenceService)
        pref_service.get_preferences = Mock(return_value=sample_preferences)
        pref_service.should_notify = Mock(return_value=True)

        # Mock telegram notifier - patch the method on the manager instance
        mock_telegram_notifier = Mock()
        mock_telegram_notifier.enabled = True
        mock_telegram_notifier.notify_system_alert = Mock()
        manager._get_telegram_notifier = Mock(return_value=mock_telegram_notifier)

        # Mock email notifier
        mock_email_notifier = Mock()
        mock_email_notifier.is_available.return_value = True
        mock_email_notifier.send_service_notification.return_value = True
        mock_email_notifier_class.return_value = mock_email_notifier

        # Patch NotificationPreferenceService where it's instantiated (inside the method)
        with patch(
            "services.notification_preference_service.NotificationPreferenceService",
            return_value=pref_service,
        ):
            manager._notify_service_stopped(user_id=1, task_name="analysis")

        # Verify preference service was called with correct event type
        # Check that should_notify was called at least 3 times (once for each channel)
        assert (
            pref_service.should_notify.call_count >= 3
        ), f"should_notify should be called at least 3 times, got {pref_service.should_notify.call_count}"

        # Check that it was called for each channel
        call_args_list = pref_service.should_notify.call_args_list
        channels_called = set()
        for call in call_args_list:
            # Check keyword arguments first (channel is passed as keyword arg)
            if "channel" in call[1]:
                channels_called.add(call[1]["channel"])
            # Also check positional arguments
            elif len(call[0]) > 2:
                channels_called.add(call[0][2])

        assert (
            "telegram" in channels_called
        ), f"should_notify should be called for telegram channel. Channels called: {channels_called}"
        assert (
            "in_app" in channels_called
        ), f"should_notify should be called for in_app channel. Channels called: {channels_called}"
        assert (
            "email" in channels_called
        ), f"should_notify should be called for email channel. Channels called: {channels_called}"

        # Verify notifications were sent
        mock_telegram_notifier.notify_system_alert.assert_called_once()
        mock_email_notifier.send_service_notification.assert_called_once()
        manager._notification_repo.create.assert_called_once()

    @patch("src.application.services.individual_service_manager.EmailNotifier")
    @patch("src.application.services.individual_service_manager.EMAIL_NOTIFIER_AVAILABLE", True)
    def test_notify_service_execution_completed_success(
        self, mock_email_notifier_class, manager, mock_db_session, sample_preferences
    ):
        """Test that service execution completed notifications respect granular preferences (success)"""
        # Setup preference service mock
        pref_service = Mock(spec=NotificationPreferenceService)
        pref_service.get_preferences = Mock(return_value=sample_preferences)
        pref_service.should_notify = Mock(return_value=True)

        # Mock telegram notifier - patch the method on the manager instance
        mock_telegram_notifier = Mock()
        mock_telegram_notifier.enabled = True
        mock_telegram_notifier.notify_system_alert = Mock()
        manager._get_telegram_notifier = Mock(return_value=mock_telegram_notifier)

        # Mock email notifier
        mock_email_notifier = Mock()
        mock_email_notifier.is_available.return_value = True
        mock_email_notifier.send_service_notification.return_value = True
        mock_email_notifier_class.return_value = mock_email_notifier

        # Patch NotificationPreferenceService where it's instantiated (inside the method)
        with patch(
            "services.notification_preference_service.NotificationPreferenceService",
            return_value=pref_service,
        ):
            manager._notify_service_execution_completed(
                user_id=1, task_name="analysis", status="success", duration=10.5
            )

        # Verify preference service was called with correct event type
        # Check that should_notify was called at least 3 times (once for each channel)
        assert (
            pref_service.should_notify.call_count >= 3
        ), f"should_notify should be called at least 3 times, got {pref_service.should_notify.call_count}"

        # Check that it was called for each channel
        call_args_list = pref_service.should_notify.call_args_list
        channels_called = set()
        for call in call_args_list:
            # Check keyword arguments first (channel is passed as keyword arg)
            if "channel" in call[1]:
                channels_called.add(call[1]["channel"])
            # Also check positional arguments
            elif len(call[0]) > 2:
                channels_called.add(call[0][2])

        assert (
            "telegram" in channels_called
        ), f"should_notify should be called for telegram channel. Channels called: {channels_called}"
        assert (
            "in_app" in channels_called
        ), f"should_notify should be called for in_app channel. Channels called: {channels_called}"
        assert (
            "email" in channels_called
        ), f"should_notify should be called for email channel. Channels called: {channels_called}"

        # Verify notifications were sent
        mock_telegram_notifier.notify_system_alert.assert_called_once()
        mock_email_notifier.send_service_notification.assert_called_once()
        manager._notification_repo.create.assert_called_once()

    @patch("src.application.services.individual_service_manager.EmailNotifier")
    @patch("src.application.services.individual_service_manager.EMAIL_NOTIFIER_AVAILABLE", True)
    def test_notify_service_execution_completed_failure(
        self, mock_email_notifier_class, manager, mock_db_session, sample_preferences
    ):
        """Test that service execution completed notifications respect granular preferences (failure)"""
        # Setup preference service mock
        pref_service = Mock(spec=NotificationPreferenceService)
        pref_service.get_preferences = Mock(return_value=sample_preferences)
        pref_service.should_notify = Mock(return_value=True)

        # Mock telegram notifier - patch the method on the manager instance
        mock_telegram_notifier = Mock()
        mock_telegram_notifier.enabled = True
        mock_telegram_notifier.notify_system_alert = Mock()
        manager._get_telegram_notifier = Mock(return_value=mock_telegram_notifier)

        # Mock email notifier
        mock_email_notifier = Mock()
        mock_email_notifier.is_available.return_value = True
        mock_email_notifier.send_service_notification.return_value = True
        mock_email_notifier_class.return_value = mock_email_notifier

        # Patch NotificationPreferenceService where it's instantiated (inside the method)
        with patch(
            "services.notification_preference_service.NotificationPreferenceService",
            return_value=pref_service,
        ):
            manager._notify_service_execution_completed(
                user_id=1, task_name="analysis", status="failed", duration=5.0, error="Test error"
            )

        # Verify preference service was called with correct event type
        # Check that should_notify was called at least once
        assert (
            pref_service.should_notify.call_count >= 1
        ), f"should_notify should be called at least once, got {pref_service.should_notify.call_count}"

        # Check that it was called for telegram channel
        call_args_list = pref_service.should_notify.call_args_list
        channels_called = set()
        for call in call_args_list:
            # Check keyword arguments first (channel is passed as keyword arg)
            if "channel" in call[1]:
                channels_called.add(call[1]["channel"])
            # Also check positional arguments
            elif len(call[0]) > 2:
                channels_called.add(call[0][2])

        assert (
            "telegram" in channels_called
        ), f"should_notify should be called for telegram channel. Channels called: {channels_called}"

        # Verify notifications were sent
        mock_telegram_notifier.notify_system_alert.assert_called_once()
        # Check that severity was ERROR
        call_args = mock_telegram_notifier.notify_system_alert.call_args
        assert call_args[1]["severity"] == "ERROR"

    def test_notify_service_started_channel_specific_preferences(
        self, manager, mock_db_session, sample_preferences
    ):
        """Test that service started notifications respect channel-specific preferences"""
        # Setup preference service mock
        pref_service = Mock(spec=NotificationPreferenceService)
        pref_service.get_preferences = Mock(return_value=sample_preferences)
        # Telegram enabled, but in-app and email disabled
        pref_service.should_notify = Mock(
            side_effect=lambda user_id, event_type, channel: channel == "telegram"
        )

        # Mock telegram notifier - patch the method on the manager instance
        mock_telegram_notifier = Mock()
        mock_telegram_notifier.enabled = True
        mock_telegram_notifier.notify_system_alert = Mock()
        manager._get_telegram_notifier = Mock(return_value=mock_telegram_notifier)

        # Patch NotificationPreferenceService where it's instantiated (inside the method)
        with patch(
            "services.notification_preference_service.NotificationPreferenceService",
            return_value=pref_service,
        ):
            manager._notify_service_started(user_id=1, task_name="analysis", process_id=12345)

        # Verify only Telegram was called
        mock_telegram_notifier.notify_system_alert.assert_called_once()
        # In-app and email should not be called
        manager._notification_repo.create.assert_not_called()
