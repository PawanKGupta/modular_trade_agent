"""
Unit tests for NotificationRepository

Tests the notification repository for creating, listing, and managing notifications.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Notification
from src.infrastructure.persistence.notification_repository import NotificationRepository


class TestNotificationRepository:
    """Test suite for NotificationRepository"""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        session = Mock(spec=Session)
        session.add = Mock()
        session.commit = Mock()
        session.refresh = Mock()
        session.get = Mock()
        session.execute = Mock()
        return session

    @pytest.fixture
    def repository(self, mock_db_session):
        """Create a NotificationRepository instance"""
        return NotificationRepository(db=mock_db_session)

    @pytest.fixture
    def sample_notification(self):
        """Create a sample notification"""
        from src.infrastructure.db.timezone_utils import ist_now

        return Notification(
            id=1,
            user_id=1,
            type="service",
            level="info",
            title="Service Started",
            message="Service: Analysis\nStatus: Running",
            read=False,
            read_at=None,
            created_at=ist_now(),
            telegram_sent=False,
            email_sent=False,
            in_app_delivered=True,
        )

    def test_create_notification(self, repository, mock_db_session, sample_notification):
        """Test creating a notification"""

        # Mock the session to return the notification after commit
        def set_id_and_defaults(obj):
            obj.id = 1
            # Set default values that would be set by the model
            if not hasattr(obj, "in_app_delivered") or obj.in_app_delivered is None:
                obj.in_app_delivered = True

        mock_db_session.refresh = Mock(side_effect=set_id_and_defaults)

        result = repository.create(
            user_id=1,
            type="service",
            level="info",
            title="Service Started",
            message="Service: Analysis\nStatus: Running",
        )

        assert result is not None
        assert result.user_id == 1
        assert result.type == "service"
        assert result.level == "info"
        assert result.title == "Service Started"
        assert result.read is False
        # in_app_delivered defaults to True in the model
        assert result.in_app_delivered is True
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_create_notification_truncates_long_fields(self, repository, mock_db_session):
        """Test that notification creation truncates long title and message"""
        long_title = "A" * 300  # Exceeds 255 char limit
        long_message = "B" * 1100  # Exceeds 1024 char limit

        mock_db_session.refresh = Mock(side_effect=lambda obj: setattr(obj, "id", 1))

        result = repository.create(
            user_id=1,
            type="service",
            level="info",
            title=long_title,
            message=long_message,
        )

        assert len(result.title) == 255
        assert len(result.message) == 1024
        assert result.title == "A" * 255
        assert result.message == "B" * 1024

    def test_get_notification(self, repository, mock_db_session, sample_notification):
        """Test getting a notification by ID"""
        mock_db_session.get.return_value = sample_notification

        result = repository.get(notification_id=1)

        assert result == sample_notification
        mock_db_session.get.assert_called_once_with(Notification, 1)

    def test_get_notification_not_found(self, repository, mock_db_session):
        """Test getting a non-existent notification"""
        mock_db_session.get.return_value = None

        result = repository.get(notification_id=999)

        assert result is None

    def test_list_notifications(self, repository, mock_db_session, sample_notification):
        """Test listing notifications"""

        # Mock the query execution
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [sample_notification]
        mock_db_session.execute.return_value = mock_result

        result = repository.list(user_id=1, limit=10)

        assert len(result) == 1
        assert result[0] == sample_notification
        mock_db_session.execute.assert_called_once()

    def test_list_notifications_with_filters(
        self, repository, mock_db_session, sample_notification
    ):
        """Test listing notifications with filters"""

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [sample_notification]
        mock_db_session.execute.return_value = mock_result

        # Test with type filter
        result = repository.list(user_id=1, type="service", limit=10)
        assert len(result) == 1

        # Test with level filter
        result = repository.list(user_id=1, level="info", limit=10)
        assert len(result) == 1

        # Test with read filter
        result = repository.list(user_id=1, read=False, limit=10)
        assert len(result) == 1

    def test_get_unread_notifications(self, repository, mock_db_session, sample_notification):
        """Test getting unread notifications"""

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [sample_notification]
        mock_db_session.execute.return_value = mock_result

        result = repository.get_unread(user_id=1, limit=10)

        assert len(result) == 1
        assert result[0].read is False

    def test_mark_notification_read(self, repository, mock_db_session, sample_notification):
        """Test marking a notification as read"""

        mock_db_session.get.return_value = sample_notification
        mock_db_session.refresh = Mock()

        result = repository.mark_read(notification_id=1)

        assert result.read is True
        assert result.read_at is not None
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once_with(result)

    def test_mark_notification_read_not_found(self, repository, mock_db_session):
        """Test marking a non-existent notification as read"""
        mock_db_session.get.return_value = None

        with pytest.raises(ValueError, match="Notification 999 not found"):
            repository.mark_read(notification_id=999)

    def test_mark_all_read(self, repository, mock_db_session, sample_notification):
        """Test marking all notifications as read"""

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [sample_notification]
        mock_db_session.execute.return_value = mock_result

        count = repository.mark_all_read(user_id=1)

        assert count == 1
        assert sample_notification.read is True
        mock_db_session.commit.assert_called_once()

    def test_count_unread(self, repository, mock_db_session, sample_notification):
        """Test counting unread notifications"""

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [sample_notification]
        mock_db_session.execute.return_value = mock_result

        count = repository.count_unread(user_id=1)

        assert count == 1

    def test_update_delivery_status(self, repository, mock_db_session, sample_notification):
        """Test updating notification delivery status"""
        mock_db_session.get.return_value = sample_notification
        mock_db_session.refresh = Mock()

        result = repository.update_delivery_status(
            notification_id=1,
            telegram_sent=True,
            email_sent=True,
            in_app_delivered=True,
        )

        assert result.telegram_sent is True
        assert result.email_sent is True
        assert result.in_app_delivered is True
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once_with(result)

    def test_update_delivery_status_partial(self, repository, mock_db_session, sample_notification):
        """Test updating only some delivery status fields"""
        mock_db_session.get.return_value = sample_notification
        mock_db_session.refresh = Mock()

        result = repository.update_delivery_status(
            notification_id=1,
            telegram_sent=True,
        )

        assert result.telegram_sent is True
        # Other fields should remain unchanged
        assert result.email_sent == sample_notification.email_sent
        assert result.in_app_delivered == sample_notification.in_app_delivered
