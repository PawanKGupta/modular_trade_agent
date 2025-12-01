"""
Integration tests for notification creation

Tests that notifications are properly created when services start/stop/complete.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


from src.application.services.individual_service_manager import (
    IndividualServiceManager,
)
from src.infrastructure.db.models import UserNotificationPreferences
from src.infrastructure.persistence.notification_repository import NotificationRepository


class TestNotificationCreation:
    """Integration tests for notification creation"""

    def test_service_started_creates_notification(self, db_session):
        """Test that service started creates an in-app notification"""
        # Create user and preferences
        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(
            email="notif_test@example.com",
            password_hash="test_hash",
            role="user",
            created_at=ist_now(),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create preferences with service started enabled
        preferences = UserNotificationPreferences(
            user_id=user.id,
            in_app_enabled=True,
            notify_service_started=True,
            notify_service_stopped=True,
            notify_service_execution_completed=True,
        )
        db_session.add(preferences)
        db_session.commit()

        # Create service manager
        manager = IndividualServiceManager(db_session)

        # Trigger service started notification
        manager._notify_service_started(user_id=user.id, task_name="analysis", process_id=12345)

        # Verify notification was created
        notification_repo = NotificationRepository(db_session)
        notifications = notification_repo.list(user_id=user.id, type="service", limit=10)

        assert len(notifications) >= 1
        service_notification = next(
            (n for n in notifications if n.title == "Service Started"), None
        )
        assert service_notification is not None
        assert service_notification.type == "service"
        assert service_notification.level == "info"
        assert service_notification.read is False
        assert "Analysis" in service_notification.message
        assert "Running" in service_notification.message

    def test_service_started_respects_preferences(self, db_session):
        """Test that service started respects notification preferences"""
        # Create user and preferences
        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(
            email="notif_test2@example.com",
            password_hash="test_hash",
            role="user",
            created_at=ist_now(),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create preferences with service started DISABLED
        preferences = UserNotificationPreferences(
            user_id=user.id,
            in_app_enabled=True,
            notify_service_started=False,  # Disabled
            notify_service_stopped=True,
            notify_service_execution_completed=True,
        )
        db_session.add(preferences)
        db_session.commit()

        # Create service manager
        manager = IndividualServiceManager(db_session)

        # Trigger service started notification
        manager._notify_service_started(user_id=user.id, task_name="analysis", process_id=12345)

        # Verify NO notification was created
        notification_repo = NotificationRepository(db_session)
        notifications = notification_repo.list(user_id=user.id, type="service", limit=10)

        service_notifications = [n for n in notifications if n.title == "Service Started"]
        assert len(service_notifications) == 0

    def test_service_stopped_creates_notification(self, db_session):
        """Test that service stopped creates an in-app notification"""
        # Create user and preferences
        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(
            email="notif_test3@example.com",
            password_hash="test_hash",
            role="user",
            created_at=ist_now(),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create preferences
        preferences = UserNotificationPreferences(
            user_id=user.id,
            in_app_enabled=True,
            notify_service_started=True,
            notify_service_stopped=True,
            notify_service_execution_completed=True,
        )
        db_session.add(preferences)
        db_session.commit()

        # Create service manager
        manager = IndividualServiceManager(db_session)

        # Trigger service stopped notification
        manager._notify_service_stopped(user_id=user.id, task_name="analysis")

        # Verify notification was created
        notification_repo = NotificationRepository(db_session)
        notifications = notification_repo.list(user_id=user.id, type="service", limit=10)

        service_notification = next(
            (n for n in notifications if n.title == "Service Stopped"), None
        )
        assert service_notification is not None
        assert service_notification.type == "service"
        assert service_notification.level == "info"
        assert "Analysis" in service_notification.message
        assert "Stopped" in service_notification.message

    def test_service_execution_completed_creates_notification(self, db_session):
        """Test that service execution completed creates an in-app notification"""
        # Create user and preferences
        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(
            email="notif_test4@example.com",
            password_hash="test_hash",
            role="user",
            created_at=ist_now(),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create preferences
        preferences = UserNotificationPreferences(
            user_id=user.id,
            in_app_enabled=True,
            notify_service_started=True,
            notify_service_stopped=True,
            notify_service_execution_completed=True,
        )
        db_session.add(preferences)
        db_session.commit()

        # Create service manager
        manager = IndividualServiceManager(db_session)

        # Trigger service execution completed notification (success)
        manager._notify_service_execution_completed(
            user_id=user.id, task_name="analysis", status="success", duration=10.5
        )

        # Verify notification was created
        notification_repo = NotificationRepository(db_session)
        notifications = notification_repo.list(user_id=user.id, type="service", limit=10)

        service_notification = next(
            (n for n in notifications if n.title == "Service Execution Completed"), None
        )
        assert service_notification is not None
        assert service_notification.type == "service"
        assert service_notification.level == "info"
        assert "Analysis" in service_notification.message
        assert "Success" in service_notification.message

    def test_service_execution_failed_creates_notification(self, db_session):
        """Test that service execution failed creates an in-app notification"""
        # Create user and preferences
        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(
            email="notif_test5@example.com",
            password_hash="test_hash",
            role="user",
            created_at=ist_now(),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create preferences
        preferences = UserNotificationPreferences(
            user_id=user.id,
            in_app_enabled=True,
            notify_service_started=True,
            notify_service_stopped=True,
            notify_service_execution_completed=True,
        )
        db_session.add(preferences)
        db_session.commit()

        # Create service manager
        manager = IndividualServiceManager(db_session)

        # Trigger service execution completed notification (failed)
        manager._notify_service_execution_completed(
            user_id=user.id, task_name="analysis", status="failed", duration=5.0, error="Test error"
        )

        # Verify notification was created
        notification_repo = NotificationRepository(db_session)
        notifications = notification_repo.list(user_id=user.id, type="service", limit=10)

        service_notification = next(
            (n for n in notifications if n.title == "Service Execution Failed"), None
        )
        assert service_notification is not None
        assert service_notification.type == "service"
        assert service_notification.level == "error"
        assert "Analysis" in service_notification.message
        assert "Failed" in service_notification.message
