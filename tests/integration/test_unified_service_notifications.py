"""
Integration tests for unified service notifications

Tests that notifications are properly created when unified service starts/stops.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


from src.application.services.multi_user_trading_service import (
    MultiUserTradingService,
)
from src.infrastructure.db.models import UserNotificationPreferences
from src.infrastructure.persistence.notification_repository import NotificationRepository


class TestUnifiedServiceNotifications:
    """Integration tests for unified service notifications"""

    def test_unified_service_started_creates_notification(self, db_session):
        """Test that unified service started creates an in-app notification"""
        # Create user and preferences
        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(
            email="unified_notif_test@example.com",
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
        service = MultiUserTradingService(db_session)

        # Trigger service started notification
        service._notify_service_started(user_id=user.id)

        # Verify notification was created
        notification_repo = NotificationRepository(db_session)
        notifications = notification_repo.list(user_id=user.id, type="service", limit=10)

        assert len(notifications) >= 1
        service_notification = next(
            (n for n in notifications if n.title == "Unified Service Started"), None
        )
        assert service_notification is not None
        assert service_notification.type == "service"
        assert service_notification.level == "info"
        assert service_notification.read is False
        assert "Unified Trading Service" in service_notification.message
        assert "Running" in service_notification.message

    def test_unified_service_started_respects_preferences(self, db_session):
        """Test that unified service started respects notification preferences"""
        # Create user and preferences
        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(
            email="unified_notif_test2@example.com",
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
        service = MultiUserTradingService(db_session)

        # Trigger service started notification
        service._notify_service_started(user_id=user.id)

        # Verify NO notification was created
        notification_repo = NotificationRepository(db_session)
        notifications = notification_repo.list(user_id=user.id, type="service", limit=10)

        service_notifications = [n for n in notifications if n.title == "Unified Service Started"]
        assert len(service_notifications) == 0

    def test_unified_service_stopped_creates_notification(self, db_session):
        """Test that unified service stopped creates an in-app notification"""
        # Create user and preferences
        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(
            email="unified_notif_test3@example.com",
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
        service = MultiUserTradingService(db_session)

        # Trigger service stopped notification
        service._notify_service_stopped(user_id=user.id)

        # Verify notification was created
        notification_repo = NotificationRepository(db_session)
        notifications = notification_repo.list(user_id=user.id, type="service", limit=10)

        service_notification = next(
            (n for n in notifications if n.title == "Unified Service Stopped"), None
        )
        assert service_notification is not None
        assert service_notification.type == "service"
        assert service_notification.level == "info"
        assert "Unified Trading Service" in service_notification.message
        assert "Stopped" in service_notification.message

    def test_unified_service_stopped_respects_preferences(self, db_session):
        """Test that unified service stopped respects notification preferences"""
        # Create user and preferences
        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(
            email="unified_notif_test4@example.com",
            password_hash="test_hash",
            role="user",
            created_at=ist_now(),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create preferences with service stopped DISABLED
        preferences = UserNotificationPreferences(
            user_id=user.id,
            in_app_enabled=True,
            notify_service_started=True,
            notify_service_stopped=False,  # Disabled
            notify_service_execution_completed=True,
        )
        db_session.add(preferences)
        db_session.commit()

        # Create service manager
        service = MultiUserTradingService(db_session)

        # Trigger service stopped notification
        service._notify_service_stopped(user_id=user.id)

        # Verify NO notification was created
        notification_repo = NotificationRepository(db_session)
        notifications = notification_repo.list(user_id=user.id, type="service", limit=10)

        service_notifications = [n for n in notifications if n.title == "Unified Service Stopped"]
        assert len(service_notifications) == 0
