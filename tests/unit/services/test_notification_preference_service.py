"""
Unit tests for NotificationPreferenceService (Phase 2: Notification Preferences)

Tests the notification preference service for managing and checking user preferences.
"""

import sys
from datetime import time
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from sqlalchemy.orm import Session

from services.notification_preference_service import (
    NotificationEventType,
    NotificationPreferenceService,
)
from src.infrastructure.db.models import UserNotificationPreferences


class TestNotificationPreferenceService:
    """Test suite for NotificationPreferenceService"""

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
        """Create a NotificationPreferenceService instance"""
        return NotificationPreferenceService(db_session=mock_db_session)

    @pytest.fixture
    def sample_preferences(self):
        """Create sample notification preferences"""
        return UserNotificationPreferences(
            id=1,
            user_id=1,
            telegram_enabled=True,
            telegram_chat_id="123456789",
            email_enabled=False,
            email_address=None,
            in_app_enabled=True,
            notify_service_events=True,
            notify_trading_events=True,
            notify_system_events=True,
            notify_errors=True,
            notify_order_placed=True,
            notify_order_rejected=True,
            notify_order_executed=True,
            notify_order_cancelled=True,
            notify_order_modified=False,
            notify_retry_queue_added=True,
            notify_retry_queue_updated=True,
            notify_retry_queue_removed=True,
            notify_retry_queue_retried=True,
            notify_partial_fill=True,
            notify_system_errors=True,
            notify_system_warnings=False,
            notify_system_info=False,
            notify_service_started=True,
            notify_service_stopped=True,
            notify_service_execution_completed=True,
            quiet_hours_start=None,
            quiet_hours_end=None,
        )

    def test_initialization(self, service):
        """Test that NotificationPreferenceService initializes correctly"""
        assert service is not None
        assert service.db is not None
        assert service._preference_cache == {}

    def test_get_preferences_existing(self, service, mock_db_session, sample_preferences):
        """Test getting existing preferences"""
        # Setup query chain properly
        mock_query_result = Mock()
        mock_query_result.first.return_value = sample_preferences
        mock_query = Mock()
        mock_query.filter.return_value = mock_query_result
        mock_db_session.query.return_value = mock_query

        result = service.get_preferences(user_id=1)

        assert result == sample_preferences
        assert 1 in service._preference_cache
        mock_db_session.query.assert_called_once_with(UserNotificationPreferences)

    def test_get_preferences_not_found(self, service, mock_db_session):
        """Test getting preferences when user has none"""
        # Setup query chain properly
        mock_query_result = Mock()
        mock_query_result.first.return_value = None
        mock_query = Mock()
        mock_query.filter.return_value = mock_query_result
        mock_db_session.query.return_value = mock_query

        result = service.get_preferences(user_id=1)

        assert result is None
        assert 1 not in service._preference_cache

    def test_get_preferences_cached(self, service, sample_preferences):
        """Test that cached preferences are returned"""
        service._preference_cache[1] = sample_preferences

        result = service.get_preferences(user_id=1)

        assert result == sample_preferences
        # Should not query database when cached
        assert service.db.query.call_count == 0

    def test_get_or_create_default_preferences_existing(self, service, sample_preferences):
        """Test getting or creating when preferences exist"""
        service._preference_cache[1] = sample_preferences

        result = service.get_or_create_default_preferences(user_id=1)

        assert result == sample_preferences
        service.db.add.assert_not_called()

    def test_get_or_create_default_preferences_new(self, service, mock_db_session):
        """Test creating default preferences when none exist"""
        # Setup query chain properly
        mock_query_result = Mock()
        mock_query_result.first.return_value = None
        mock_query = Mock()
        mock_query.filter.return_value = mock_query_result
        mock_db_session.query.return_value = mock_query

        result = service.get_or_create_default_preferences(user_id=1)

        assert result is not None
        assert result.user_id == 1
        assert result.in_app_enabled is True
        assert result.telegram_enabled is False
        assert result.email_enabled is False
        assert result.notify_order_placed is True
        assert result.notify_order_modified is False
        assert result.notify_system_warnings is False
        assert result.notify_service_started is True
        assert result.notify_service_stopped is True
        assert result.notify_service_execution_completed is True
        service.db.add.assert_called_once()
        service.db.commit.assert_called_once()

    def test_get_or_create_default_preferences_commit_failure(self, service, mock_db_session):
        """Test handling of commit failure when creating preferences"""
        # Setup query chain properly
        mock_query_result = Mock()
        mock_query_result.first.return_value = None
        mock_query = Mock()
        mock_query.filter.return_value = mock_query_result
        mock_db_session.query.return_value = mock_query
        mock_db_session.commit.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            service.get_or_create_default_preferences(user_id=1)

        service.db.rollback.assert_called_once()

    def test_update_preferences(self, service, sample_preferences):
        """Test updating preferences"""
        service._preference_cache[1] = sample_preferences

        updates = {
            "telegram_enabled": False,
            "notify_order_placed": False,
            "notify_system_warnings": True,
        }

        result = service.update_preferences(user_id=1, preferences_dict=updates)

        assert result.telegram_enabled is False
        assert result.notify_order_placed is False
        assert result.notify_system_warnings is True
        service.db.commit.assert_called_once()
        assert 1 in service._preference_cache

    def test_update_preferences_unknown_field(self, service, sample_preferences, caplog):
        """Test updating preferences with unknown field"""
        service._preference_cache[1] = sample_preferences

        updates = {"unknown_field": "value"}

        result = service.update_preferences(user_id=1, preferences_dict=updates)

        # Should not raise, but log warning
        assert "Unknown preference field" in caplog.text

    def test_should_notify_channel_disabled(self, service, sample_preferences):
        """Test should_notify when channel is disabled"""
        sample_preferences.telegram_enabled = False
        service._preference_cache[1] = sample_preferences

        result = service.should_notify(
            user_id=1, event_type=NotificationEventType.ORDER_PLACED, channel="telegram"
        )

        assert result is False

    def test_should_notify_event_disabled(self, service, sample_preferences):
        """Test should_notify when event type is disabled"""
        sample_preferences.notify_order_placed = False
        service._preference_cache[1] = sample_preferences

        result = service.should_notify(
            user_id=1, event_type=NotificationEventType.ORDER_PLACED, channel="telegram"
        )

        assert result is False

    def test_should_notify_quiet_hours(self, service, sample_preferences):
        """Test should_notify during quiet hours"""
        sample_preferences.quiet_hours_start = time(22, 0)  # 10 PM
        sample_preferences.quiet_hours_end = time(8, 0)  # 8 AM
        service._preference_cache[1] = sample_preferences

        # Mock current time to be 11 PM (within quiet hours)
        with patch("services.notification_preference_service.datetime") as mock_datetime:
            mock_datetime.now.return_value.time.return_value = time(23, 0)

            result = service.should_notify(
                user_id=1, event_type=NotificationEventType.ORDER_PLACED, channel="telegram"
            )

            assert result is False

    def test_should_notify_all_conditions_met(self, service, sample_preferences):
        """Test should_notify when all conditions are met"""
        service._preference_cache[1] = sample_preferences

        result = service.should_notify(
            user_id=1, event_type=NotificationEventType.ORDER_PLACED, channel="telegram"
        )

        assert result is True

    def test_should_notify_no_preferences_defaults(self, service, mock_db_session):
        """Test should_notify when no preferences exist (should default to enabled)"""
        # Setup query chain properly
        mock_query_result = Mock()
        mock_query_result.first.return_value = None
        mock_query = Mock()
        mock_query.filter.return_value = mock_query_result
        mock_db_session.query.return_value = mock_query

        result = service.should_notify(
            user_id=1, event_type=NotificationEventType.ORDER_PLACED, channel="telegram"
        )

        # Should default to True for backward compatibility
        assert result is True

    def test_is_quiet_hours_no_preferences(self, service, mock_db_session):
        """Test is_quiet_hours when no preferences exist"""
        # Setup query chain properly
        mock_query_result = Mock()
        mock_query_result.first.return_value = None
        mock_query = Mock()
        mock_query.filter.return_value = mock_query_result
        mock_db_session.query.return_value = mock_query

        result = service.is_quiet_hours(user_id=1)

        assert result is False

    def test_is_quiet_hours_not_set(self, service, sample_preferences):
        """Test is_quiet_hours when quiet hours are not set"""
        sample_preferences.quiet_hours_start = None
        sample_preferences.quiet_hours_end = None
        service._preference_cache[1] = sample_preferences

        result = service.is_quiet_hours(user_id=1)

        assert result is False

    def test_is_quiet_hours_same_day(self, service, sample_preferences):
        """Test is_quiet_hours for quiet hours within same day"""
        sample_preferences.quiet_hours_start = time(22, 0)  # 10 PM
        sample_preferences.quiet_hours_end = time(23, 0)  # 11 PM
        service._preference_cache[1] = sample_preferences

        # Test within quiet hours
        with patch("services.notification_preference_service.datetime") as mock_datetime:
            mock_datetime.now.return_value.time.return_value = time(22, 30)
            assert service.is_quiet_hours(user_id=1) is True

        # Test outside quiet hours
        with patch("services.notification_preference_service.datetime") as mock_datetime:
            mock_datetime.now.return_value.time.return_value = time(21, 0)
            assert service.is_quiet_hours(user_id=1) is False

    def test_is_quiet_hours_spanning_midnight(self, service, sample_preferences):
        """Test is_quiet_hours for quiet hours spanning midnight"""
        sample_preferences.quiet_hours_start = time(22, 0)  # 10 PM
        sample_preferences.quiet_hours_end = time(8, 0)  # 8 AM
        service._preference_cache[1] = sample_preferences

        # Test within quiet hours (after start)
        with patch("services.notification_preference_service.datetime") as mock_datetime:
            mock_datetime.now.return_value.time.return_value = time(23, 0)
            assert service.is_quiet_hours(user_id=1) is True

        # Test within quiet hours (before end)
        with patch("services.notification_preference_service.datetime") as mock_datetime:
            mock_datetime.now.return_value.time.return_value = time(7, 0)
            assert service.is_quiet_hours(user_id=1) is True

        # Test outside quiet hours
        with patch("services.notification_preference_service.datetime") as mock_datetime:
            mock_datetime.now.return_value.time.return_value = time(12, 0)
            assert service.is_quiet_hours(user_id=1) is False

    def test_get_enabled_channels_all_enabled(self, service, sample_preferences):
        """Test get_enabled_channels when all channels are enabled"""
        sample_preferences.telegram_enabled = True
        sample_preferences.email_enabled = True
        sample_preferences.in_app_enabled = True
        service._preference_cache[1] = sample_preferences

        result = service.get_enabled_channels(user_id=1)

        assert "telegram" in result
        assert "email" in result
        assert "in_app" in result
        assert len(result) == 3

    def test_get_enabled_channels_partial(self, service, sample_preferences):
        """Test get_enabled_channels when only some channels are enabled"""
        sample_preferences.telegram_enabled = True
        sample_preferences.email_enabled = False
        sample_preferences.in_app_enabled = True
        service._preference_cache[1] = sample_preferences

        result = service.get_enabled_channels(user_id=1)

        assert "telegram" in result
        assert "email" not in result
        assert "in_app" in result
        assert len(result) == 2

    def test_get_enabled_channels_no_preferences(self, service, mock_db_session):
        """Test get_enabled_channels when no preferences exist"""
        # Setup query chain properly
        mock_query_result = Mock()
        mock_query_result.first.return_value = None
        mock_query = Mock()
        mock_query.filter.return_value = mock_query_result
        mock_db_session.query.return_value = mock_query

        result = service.get_enabled_channels(user_id=1)

        # Should default to in_app only
        assert result == ["in_app"]

    def test_clear_cache_specific_user(self, service, sample_preferences):
        """Test clearing cache for a specific user"""
        service._preference_cache[1] = sample_preferences
        service._preference_cache[2] = sample_preferences

        service.clear_cache(user_id=1)

        assert 1 not in service._preference_cache
        assert 2 in service._preference_cache

    def test_clear_cache_all_users(self, service, sample_preferences):
        """Test clearing cache for all users"""
        service._preference_cache[1] = sample_preferences
        service._preference_cache[2] = sample_preferences

        service.clear_cache()

        assert len(service._preference_cache) == 0

    def test_event_type_constants(self):
        """Test that all event type constants are defined"""
        assert NotificationEventType.ORDER_PLACED == "order_placed"
        assert NotificationEventType.ORDER_REJECTED == "order_rejected"
        assert NotificationEventType.ORDER_EXECUTED == "order_executed"
        assert NotificationEventType.ORDER_CANCELLED == "order_cancelled"
        assert NotificationEventType.ORDER_MODIFIED == "order_modified"
        assert NotificationEventType.RETRY_QUEUE_ADDED == "retry_queue_added"
        assert NotificationEventType.RETRY_QUEUE_UPDATED == "retry_queue_updated"
        assert NotificationEventType.RETRY_QUEUE_REMOVED == "retry_queue_removed"
        assert NotificationEventType.RETRY_QUEUE_RETRIED == "retry_queue_retried"
        assert NotificationEventType.PARTIAL_FILL == "partial_fill"
        assert NotificationEventType.SYSTEM_ERROR == "system_error"
        assert NotificationEventType.SYSTEM_WARNING == "system_warning"
        assert NotificationEventType.SYSTEM_INFO == "system_info"

    def test_all_event_types_method(self):
        """Test that all_event_types returns all event types"""
        event_types = NotificationEventType.all_event_types()

        assert (
            len(event_types) == 17
        )  # 10 order/retry + 3 system + 3 service + 1 legacy SERVICE_EVENT
        assert NotificationEventType.ORDER_PLACED in event_types
        assert NotificationEventType.SYSTEM_INFO in event_types
        assert NotificationEventType.SERVICE_STARTED in event_types
        assert NotificationEventType.SERVICE_STOPPED in event_types
        assert NotificationEventType.SERVICE_EXECUTION_COMPLETED in event_types
        assert NotificationEventType.SERVICE_EVENT in event_types  # Legacy event type

    def test_should_notify_all_event_types(self, service, sample_preferences):
        """Test should_notify for all event types"""
        service._preference_cache[1] = sample_preferences

        # Test all granular event types
        event_types = [
            NotificationEventType.ORDER_PLACED,
            NotificationEventType.ORDER_REJECTED,
            NotificationEventType.ORDER_EXECUTED,
            NotificationEventType.ORDER_CANCELLED,
            NotificationEventType.ORDER_MODIFIED,
            NotificationEventType.RETRY_QUEUE_ADDED,
            NotificationEventType.RETRY_QUEUE_UPDATED,
            NotificationEventType.RETRY_QUEUE_REMOVED,
            NotificationEventType.RETRY_QUEUE_RETRIED,
            NotificationEventType.PARTIAL_FILL,
            NotificationEventType.SYSTEM_ERROR,
            NotificationEventType.SYSTEM_WARNING,
            NotificationEventType.SYSTEM_INFO,
            NotificationEventType.SERVICE_STARTED,
            NotificationEventType.SERVICE_STOPPED,
            NotificationEventType.SERVICE_EXECUTION_COMPLETED,
        ]

        for event_type in event_types:
            result = service.should_notify(user_id=1, event_type=event_type, channel="telegram")
            # Should return True or False based on preference, not raise exception
            assert isinstance(result, bool)

    def test_should_notify_legacy_event_types(self, service, sample_preferences):
        """Test should_notify for legacy event types (backward compatibility)"""
        service._preference_cache[1] = sample_preferences

        legacy_types = [
            NotificationEventType.SERVICE_EVENT,
            NotificationEventType.TRADING_EVENT,
            NotificationEventType.SYSTEM_EVENT,
            NotificationEventType.ERROR,
        ]

        for event_type in legacy_types:
            result = service.should_notify(user_id=1, event_type=event_type, channel="telegram")
            assert isinstance(result, bool)

    def test_should_notify_unknown_event_type(self, service, sample_preferences):
        """Test should_notify for unknown event type (should default to enabled)"""
        service._preference_cache[1] = sample_preferences

        result = service.should_notify(user_id=1, event_type="unknown_event", channel="telegram")

        # Should default to True for backward compatibility
        assert result is True
