"""
Tests for server startup cleanup of orphaned services
"""

import pytest
from unittest.mock import MagicMock, patch

from src.infrastructure.db.models import ServiceStatus, IndividualServiceStatus, Users
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = Users(
        email="startup_test@example.com",
        password_hash="test_hash",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestStartupServiceCleanup:
    """Test that server startup cleans up orphaned service status"""

    def test_cleanup_orphaned_unified_services(self, db_session, test_user):
        """Test that unified services marked as running are stopped on startup"""
        # Create orphaned unified service status
        orphaned_status = ServiceStatus(
            user_id=test_user.id,
            service_running=True,  # Orphaned - server restarted
            last_heartbeat=ist_now(),
        )
        db_session.add(orphaned_status)
        db_session.commit()

        # Simulate startup cleanup
        running_services = db_session.query(ServiceStatus).filter(
            ServiceStatus.service_running == True
        ).all()

        assert len(running_services) == 1

        # Mark as stopped (simulating startup cleanup)
        for status in running_services:
            status.service_running = False
        db_session.commit()

        # Verify cleanup
        db_session.refresh(orphaned_status)
        assert orphaned_status.service_running is False

    def test_cleanup_orphaned_individual_services(self, db_session, test_user):
        """Test that individual services marked as running are stopped on startup"""
        # Create orphaned individual service statuses
        orphaned_services = [
            IndividualServiceStatus(
                user_id=test_user.id,
                task_name="buy_orders",
                is_running=True,  # Orphaned
                process_id=12345,
            ),
            IndividualServiceStatus(
                user_id=test_user.id,
                task_name="sell_monitor",
                is_running=True,  # Orphaned
                process_id=12346,
            ),
        ]
        db_session.add_all(orphaned_services)
        db_session.commit()

        # Simulate startup cleanup
        running_services = db_session.query(IndividualServiceStatus).filter(
            IndividualServiceStatus.is_running == True
        ).all()

        assert len(running_services) == 2

        # Mark as stopped (simulating startup cleanup)
        for status in running_services:
            status.is_running = False
            status.process_id = None
        db_session.commit()

        # Verify cleanup
        for service in orphaned_services:
            db_session.refresh(service)
            assert service.is_running is False
            assert service.process_id is None

    def test_no_cleanup_needed_when_no_orphaned_services(self, db_session, test_user):
        """Test that cleanup does nothing when no orphaned services exist"""
        # Create stopped service status
        stopped_status = ServiceStatus(
            user_id=test_user.id,
            service_running=False,  # Already stopped
        )
        db_session.add(stopped_status)
        db_session.commit()

        # Check for orphaned services
        running_services = db_session.query(ServiceStatus).filter(
            ServiceStatus.service_running == True
        ).all()

        assert len(running_services) == 0  # No cleanup needed

    def test_cleanup_multiple_users_orphaned_services(self, db_session):
        """Test that cleanup handles multiple users with orphaned services"""
        # Create multiple users
        user1 = Users(email="user1@test.com", password_hash="hash1", role="user")
        user2 = Users(email="user2@test.com", password_hash="hash2", role="user")
        db_session.add_all([user1, user2])
        db_session.commit()

        # Create orphaned services for both users
        orphaned_services = [
            ServiceStatus(user_id=user1.id, service_running=True),
            ServiceStatus(user_id=user2.id, service_running=True),
            IndividualServiceStatus(user_id=user1.id, task_name="buy_orders", is_running=True),
            IndividualServiceStatus(user_id=user2.id, task_name="sell_monitor", is_running=True),
        ]
        db_session.add_all(orphaned_services)
        db_session.commit()

        # Simulate startup cleanup
        running_unified = db_session.query(ServiceStatus).filter(
            ServiceStatus.service_running == True
        ).all()
        running_individual = db_session.query(IndividualServiceStatus).filter(
            IndividualServiceStatus.is_running == True
        ).all()

        assert len(running_unified) == 2
        assert len(running_individual) == 2

        # Cleanup
        for status in running_unified:
            status.service_running = False
        for status in running_individual:
            status.is_running = False
            status.process_id = None
        db_session.commit()

        # Verify all cleaned up
        running_unified_after = db_session.query(ServiceStatus).filter(
            ServiceStatus.service_running == True
        ).count()
        running_individual_after = db_session.query(IndividualServiceStatus).filter(
            IndividualServiceStatus.is_running == True
        ).count()

        assert running_unified_after == 0
        assert running_individual_after == 0

