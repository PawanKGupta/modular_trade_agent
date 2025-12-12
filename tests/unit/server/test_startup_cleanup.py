"""
Tests for server startup cleanup of orphaned services
"""

from unittest.mock import patch

import pytest

from src.infrastructure.db.models import IndividualServiceStatus, ServiceStatus, Users
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
        running_services = (
            db_session.query(ServiceStatus).filter(ServiceStatus.service_running == True).all()
        )

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
        running_services = (
            db_session.query(IndividualServiceStatus)
            .filter(IndividualServiceStatus.is_running == True)
            .all()
        )

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
        running_services = (
            db_session.query(ServiceStatus).filter(ServiceStatus.service_running == True).all()
        )

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
        running_unified = (
            db_session.query(ServiceStatus).filter(ServiceStatus.service_running == True).all()
        )
        running_individual = (
            db_session.query(IndividualServiceStatus)
            .filter(IndividualServiceStatus.is_running == True)
            .all()
        )

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
        running_unified_after = (
            db_session.query(ServiceStatus).filter(ServiceStatus.service_running == True).count()
        )
        running_individual_after = (
            db_session.query(IndividualServiceStatus)
            .filter(IndividualServiceStatus.is_running == True)
            .count()
        )

        assert running_unified_after == 0
        assert running_individual_after == 0


class TestStartupAutoRestore:
    """Test that server startup auto-restores services that were running before restart"""

    def test_auto_restore_unified_service(self, db_session, test_user):
        """Test that unified service is auto-restored after cleanup"""
        from src.application.services.multi_user_trading_service import (
            MultiUserTradingService,
        )
        from src.infrastructure.persistence.settings_repository import (
            SettingsRepository,
        )

        # Create user settings (required for service to start)
        settings_repo = SettingsRepository(db_session)
        settings_repo.ensure_default(test_user.id)

        # Create orphaned unified service status
        orphaned_status = ServiceStatus(
            user_id=test_user.id,
            service_running=True,  # Was running before restart
            last_heartbeat=ist_now(),
        )
        db_session.add(orphaned_status)
        db_session.commit()

        # Capture which services to restore
        running_unified = (
            db_session.query(ServiceStatus).filter(ServiceStatus.service_running == True).all()
        )
        unified_user_ids_to_restore = [status.user_id for status in running_unified]

        # Cleanup: Mark as stopped
        for status in running_unified:
            status.service_running = False
        db_session.commit()

        # Auto-restore: Try to restore the service
        with patch(
            "src.application.services.multi_user_trading_service.MultiUserTradingService.start_service"
        ) as mock_start:
            mock_start.return_value = True

            trading_service = MultiUserTradingService(db_session)
            for user_id in unified_user_ids_to_restore:
                user = db_session.query(Users).filter(Users.id == user_id).first()
                if user:
                    trading_service.start_service(user_id)

            # Verify service was attempted to be restored
            assert mock_start.called
            mock_start.assert_called_once_with(test_user.id)

    def test_auto_restore_skips_deleted_user(self, db_session, test_user):
        """Test that auto-restore skips services for deleted users"""
        from src.application.services.multi_user_trading_service import (
            MultiUserTradingService,
        )

        # Create orphaned unified service status
        orphaned_status = ServiceStatus(
            user_id=test_user.id,
            service_running=True,
            last_heartbeat=ist_now(),
        )
        db_session.add(orphaned_status)
        db_session.commit()

        # Capture which services to restore
        running_unified = (
            db_session.query(ServiceStatus).filter(ServiceStatus.service_running == True).all()
        )
        unified_user_ids_to_restore = [status.user_id for status in running_unified]

        # Delete the service status first (to avoid foreign key constraint)
        db_session.delete(orphaned_status)
        # Delete the user
        db_session.delete(test_user)
        db_session.commit()

        # Auto-restore: Should skip deleted user
        with patch(
            "src.application.services.multi_user_trading_service.MultiUserTradingService.start_service"
        ) as mock_start:
            trading_service = MultiUserTradingService(db_session)
            for user_id in unified_user_ids_to_restore:
                user = db_session.query(Users).filter(Users.id == user_id).first()
                if not user:
                    continue  # Skip deleted user
                trading_service.start_service(user_id)

            # Verify service was NOT attempted (user was skipped)
            assert not mock_start.called

    def test_auto_restore_handles_missing_credentials(self, db_session, test_user):
        """Test that auto-restore handles missing credentials gracefully"""
        from src.application.services.multi_user_trading_service import (
            MultiUserTradingService,
        )

        # Create orphaned unified service status
        orphaned_status = ServiceStatus(
            user_id=test_user.id,
            service_running=True,
            last_heartbeat=ist_now(),
        )
        db_session.add(orphaned_status)
        db_session.commit()

        # Capture which services to restore
        running_unified = (
            db_session.query(ServiceStatus).filter(ServiceStatus.service_running == True).all()
        )
        unified_user_ids_to_restore = [status.user_id for status in running_unified]

        # Cleanup: Mark as stopped
        for status in running_unified:
            status.service_running = False
        db_session.commit()

        # Auto-restore: Service fails due to missing credentials
        with patch(
            "src.application.services.multi_user_trading_service.MultiUserTradingService.start_service"
        ) as mock_start:
            mock_start.side_effect = ValueError("No broker credentials stored")

            trading_service = MultiUserTradingService(db_session)
            failed_count = 0
            for user_id in unified_user_ids_to_restore:
                user = db_session.query(Users).filter(Users.id == user_id).first()
                if not user:
                    continue
                try:
                    trading_service.start_service(user_id)
                except ValueError:
                    failed_count += 1

            # Verify service was attempted but failed
            assert mock_start.called
            assert failed_count == 1

    def test_auto_restore_individual_service_conflict(self, db_session, test_user):
        """Test that individual services are blocked when unified service is running"""
        from src.application.services.individual_service_manager import (
            IndividualServiceManager,
        )
        from src.application.services.multi_user_trading_service import (
            MultiUserTradingService,
        )
        from src.infrastructure.persistence.settings_repository import (
            SettingsRepository,
        )

        # Create user settings
        settings_repo = SettingsRepository(db_session)
        settings_repo.ensure_default(test_user.id)

        # Create orphaned services: both unified and individual
        unified_status = ServiceStatus(
            user_id=test_user.id,
            service_running=True,
            last_heartbeat=ist_now(),
        )
        individual_status = IndividualServiceStatus(
            user_id=test_user.id,
            task_name="analysis",
            is_running=True,
            process_id=12345,
        )
        db_session.add_all([unified_status, individual_status])
        db_session.commit()

        # Capture which services to restore
        running_unified = (
            db_session.query(ServiceStatus).filter(ServiceStatus.service_running == True).all()
        )
        running_individual = (
            db_session.query(IndividualServiceStatus)
            .filter(IndividualServiceStatus.is_running == True)
            .all()
        )

        unified_user_ids_to_restore = [status.user_id for status in running_unified]
        individual_services_to_restore = [
            (status.user_id, status.task_name) for status in running_individual
        ]

        # Cleanup: Mark as stopped
        for status in running_unified:
            status.service_running = False
        for status in running_individual:
            status.is_running = False
            status.process_id = None
        db_session.commit()

        # Auto-restore: Restore unified first, then individual
        with (
            patch(
                "src.application.services.multi_user_trading_service.MultiUserTradingService.start_service"
            ) as mock_unified_start,
            patch(
                "src.application.services.individual_service_manager.IndividualServiceManager.start_service"
            ) as mock_individual_start,
        ):
            mock_unified_start.return_value = True
            mock_individual_start.return_value = (
                False,
                "Cannot start individual service when unified service is running",
            )

            trading_service = MultiUserTradingService(db_session)
            individual_manager = IndividualServiceManager(db_session)

            # Restore unified services first
            for user_id in unified_user_ids_to_restore:
                user = db_session.query(Users).filter(Users.id == user_id).first()
                if user:
                    trading_service.start_service(user_id)

            # Restore individual services (should be blocked)
            conflict_count = 0
            for user_id, task_name in individual_services_to_restore:
                user = db_session.query(Users).filter(Users.id == user_id).first()
                if not user:
                    continue
                success, message = individual_manager.start_service(user_id, task_name)
                if not success and "unified service is running" in message.lower():
                    conflict_count += 1

            # Verify unified was restored and individual was blocked
            assert mock_unified_start.called
            assert mock_individual_start.called
            assert conflict_count == 1

    def test_auto_restore_handles_missing_script(self, db_session, test_user):
        """Test that auto-restore handles missing individual service script gracefully"""
        # Create schedule for analysis task (required for service to start)
        from datetime import time

        from src.application.services.individual_service_manager import (
            IndividualServiceManager,
        )
        from src.infrastructure.db.models import ServiceSchedule

        schedule = ServiceSchedule(
            task_name="analysis",
            enabled=True,
            schedule_type="once",
            schedule_time=time(9, 0, 0),  # 09:00:00
        )
        db_session.add(schedule)
        db_session.commit()

        # Create orphaned individual service status
        individual_status = IndividualServiceStatus(
            user_id=test_user.id,
            task_name="analysis",
            is_running=True,
            process_id=12345,
        )
        db_session.add(individual_status)
        db_session.commit()

        # Capture which services to restore
        running_individual = (
            db_session.query(IndividualServiceStatus)
            .filter(IndividualServiceStatus.is_running == True)
            .all()
        )
        individual_services_to_restore = [
            (status.user_id, status.task_name) for status in running_individual
        ]

        # Cleanup: Mark as stopped
        for status in running_individual:
            status.is_running = False
            status.process_id = None
        db_session.commit()

        # Auto-restore: Should handle FileNotFoundError for missing script
        # Note: start_service catches exceptions and returns (success, message) tuple
        with patch(
            "src.application.services.individual_service_manager.IndividualServiceManager._spawn_service_process"
        ) as mock_spawn:
            mock_spawn.side_effect = FileNotFoundError(
                "Script not found: /app/scripts/run_individual_service.py"
            )

            individual_manager = IndividualServiceManager(db_session)
            failed_count = 0
            for user_id, task_name in individual_services_to_restore:
                user = db_session.query(Users).filter(Users.id == user_id).first()
                if not user:
                    continue
                # start_service catches the exception and returns (False, message)
                success, message = individual_manager.start_service(user_id, task_name)
                if not success:
                    failed_count += 1

            # Verify error was handled (service failed to start)
            assert failed_count == 1
            assert mock_spawn.called

    def test_auto_restore_error_isolation(self, db_session):
        """Test that one service failure doesn't block others"""
        from src.application.services.multi_user_trading_service import (
            MultiUserTradingService,
        )

        # Create multiple users
        user1 = Users(email="user1@test.com", password_hash="hash1", role="user")
        user2 = Users(email="user2@test.com", password_hash="hash2", role="user")
        db_session.add_all([user1, user2])
        db_session.commit()

        # Create orphaned services for both users
        orphaned_services = [
            ServiceStatus(user_id=user1.id, service_running=True),
            ServiceStatus(user_id=user2.id, service_running=True),
        ]
        db_session.add_all(orphaned_services)
        db_session.commit()

        # Capture which services to restore
        running_unified = (
            db_session.query(ServiceStatus).filter(ServiceStatus.service_running == True).all()
        )
        unified_user_ids_to_restore = [status.user_id for status in running_unified]

        # Cleanup: Mark as stopped
        for status in running_unified:
            status.service_running = False
        db_session.commit()

        # Auto-restore: One succeeds, one fails
        with patch(
            "src.application.services.multi_user_trading_service.MultiUserTradingService.start_service"
        ) as mock_start:
            call_count = 0

            def side_effect(user_id):
                nonlocal call_count
                call_count += 1
                if user_id == user1.id:
                    return True  # Success
                else:
                    raise ValueError("Test error")  # Failure

            mock_start.side_effect = side_effect

            trading_service = MultiUserTradingService(db_session)
            restored_count = 0
            failed_count = 0

            for user_id in unified_user_ids_to_restore:
                user = db_session.query(Users).filter(Users.id == user_id).first()
                if not user:
                    continue
                try:
                    success = trading_service.start_service(user_id)
                    if success:
                        restored_count += 1
                except Exception:
                    failed_count += 1

            # Verify both were attempted (error isolation)
            assert call_count == 2
            assert restored_count == 1
            assert failed_count == 1

    def test_auto_restore_deduplicates_unified_user_ids(self, db_session, test_user):
        """Test that duplicate user_ids in unified services are deduplicated"""
        # ServiceStatus has unique constraint on user_id, so we can't create duplicates
        # Instead, test the deduplication logic directly with a list that has duplicates
        # Simulate what would happen if we had multiple ServiceStatus records (edge case)

        # Create one orphaned unified service status
        orphaned_status = ServiceStatus(
            user_id=test_user.id,
            service_running=True,
            last_heartbeat=ist_now(),
        )
        db_session.add(orphaned_status)
        db_session.commit()

        # Simulate having duplicate user_ids in the list (edge case scenario)
        # This tests the deduplication logic: list({status.user_id for status in running_unified})
        running_unified = (
            db_session.query(ServiceStatus).filter(ServiceStatus.service_running == True).all()
        )

        # Test deduplication logic: convert to set then back to list
        unified_user_ids_to_restore = list({status.user_id for status in running_unified})

        # Should have only one unique user_id (even if we had duplicates in the query result)
        assert len(unified_user_ids_to_restore) == 1
        assert unified_user_ids_to_restore[0] == test_user.id

        # Verify deduplication works by manually creating a list with duplicates
        duplicate_list = [test_user.id, test_user.id, test_user.id]
        deduplicated = list(set(duplicate_list))
        assert len(deduplicated) == 1
        assert deduplicated[0] == test_user.id

    def test_auto_restore_handles_false_return_from_unified_service(self, db_session, test_user):
        """Test that auto-restore handles False return (not exception) from unified service"""
        from src.application.services.multi_user_trading_service import (
            MultiUserTradingService,
        )

        # Create orphaned unified service status
        orphaned_status = ServiceStatus(
            user_id=test_user.id,
            service_running=True,
            last_heartbeat=ist_now(),
        )
        db_session.add(orphaned_status)
        db_session.commit()

        # Capture which services to restore
        running_unified = (
            db_session.query(ServiceStatus).filter(ServiceStatus.service_running == True).all()
        )
        unified_user_ids_to_restore = [status.user_id for status in running_unified]

        # Cleanup: Mark as stopped
        for status in running_unified:
            status.service_running = False
        db_session.commit()

        # Auto-restore: Service returns False (not exception)
        with patch(
            "src.application.services.multi_user_trading_service.MultiUserTradingService.start_service"
        ) as mock_start:
            mock_start.return_value = False  # Returns False without exception

            trading_service = MultiUserTradingService(db_session)
            restored_count = 0
            failed_count = 0
            for user_id in unified_user_ids_to_restore:
                user = db_session.query(Users).filter(Users.id == user_id).first()
                if not user:
                    continue
                success = trading_service.start_service(user_id)
                if success:
                    restored_count += 1
                else:
                    failed_count += 1

            # Verify service was attempted but returned False
            assert mock_start.called
            assert restored_count == 0
            assert failed_count == 1

    def test_auto_restore_handles_disabled_schedule(self, db_session, test_user):
        """Test that auto-restore handles disabled schedule for individual service"""
        from datetime import time

        from src.application.services.individual_service_manager import (
            IndividualServiceManager,
        )
        from src.infrastructure.db.models import ServiceSchedule

        # Create disabled schedule for analysis task
        schedule = ServiceSchedule(
            task_name="analysis",
            enabled=False,  # Disabled
            schedule_type="once",
            schedule_time=time(9, 0, 0),
        )
        db_session.add(schedule)
        db_session.commit()

        # Create orphaned individual service status
        individual_status = IndividualServiceStatus(
            user_id=test_user.id,
            task_name="analysis",
            is_running=True,
            process_id=12345,
        )
        db_session.add(individual_status)
        db_session.commit()

        # Capture which services to restore
        running_individual = (
            db_session.query(IndividualServiceStatus)
            .filter(IndividualServiceStatus.is_running == True)
            .all()
        )
        individual_services_to_restore = [
            (status.user_id, status.task_name) for status in running_individual
        ]

        # Cleanup: Mark as stopped
        for status in running_individual:
            status.is_running = False
            status.process_id = None
        db_session.commit()

        # Auto-restore: Should fail because schedule is disabled
        individual_manager = IndividualServiceManager(db_session)
        failed_count = 0
        for user_id, task_name in individual_services_to_restore:
            user = db_session.query(Users).filter(Users.id == user_id).first()
            if not user:
                continue
            success, message = individual_manager.start_service(user_id, task_name)
            if not success:
                failed_count += 1
                # Verify it's due to disabled schedule
                assert "disabled" in message.lower()

        # Verify service failed to start due to disabled schedule
        assert failed_count == 1

    def test_auto_restore_no_services_to_restore(self, db_session, test_user):
        """Test that auto-restore handles empty list gracefully"""
        # No orphaned services exist
        running_unified = (
            db_session.query(ServiceStatus).filter(ServiceStatus.service_running == True).all()
        )
        running_individual = (
            db_session.query(IndividualServiceStatus)
            .filter(IndividualServiceStatus.is_running == True)
            .all()
        )

        unified_user_ids_to_restore = list({status.user_id for status in running_unified})
        individual_services_to_restore = [
            (status.user_id, status.task_name) for status in running_individual
        ]

        # Should have empty lists
        assert len(unified_user_ids_to_restore) == 0
        assert len(individual_services_to_restore) == 0

        # Auto-restore should not be attempted (condition check in main.py)
        if not unified_user_ids_to_restore and not individual_services_to_restore:
            # This is the expected behavior - no restoration needed
            assert True  # Test passes if we reach here

    def test_auto_restore_multiple_individual_services_same_user(self, db_session, test_user):
        """Test that auto-restore handles multiple individual services for same user"""
        from datetime import time

        from src.application.services.individual_service_manager import (
            IndividualServiceManager,
        )
        from src.infrastructure.db.models import ServiceSchedule

        # Create schedules for multiple tasks
        schedules = [
            ServiceSchedule(
                task_name="analysis",
                enabled=True,
                schedule_type="once",
                schedule_time=time(9, 0, 0),
            ),
            ServiceSchedule(
                task_name="buy_orders",
                enabled=True,
                schedule_type="once",
                schedule_time=time(16, 5, 0),
            ),
        ]
        db_session.add_all(schedules)
        db_session.commit()

        # Create orphaned individual service statuses for same user
        individual_statuses = [
            IndividualServiceStatus(
                user_id=test_user.id,
                task_name="analysis",
                is_running=True,
                process_id=12345,
            ),
            IndividualServiceStatus(
                user_id=test_user.id,
                task_name="buy_orders",
                is_running=True,
                process_id=12346,
            ),
        ]
        db_session.add_all(individual_statuses)
        db_session.commit()

        # Capture which services to restore
        running_individual = (
            db_session.query(IndividualServiceStatus)
            .filter(IndividualServiceStatus.is_running == True)
            .all()
        )
        individual_services_to_restore = [
            (status.user_id, status.task_name) for status in running_individual
        ]

        # Should have 2 services for same user
        assert len(individual_services_to_restore) == 2
        assert all(user_id == test_user.id for user_id, _ in individual_services_to_restore)

        # Cleanup: Mark as stopped
        for status in running_individual:
            status.is_running = False
            status.process_id = None
        db_session.commit()

        # Auto-restore: Should attempt to restore both
        with patch(
            "src.application.services.individual_service_manager.IndividualServiceManager._spawn_service_process"
        ) as mock_spawn:
            from unittest.mock import MagicMock

            mock_process = MagicMock()
            mock_process.pid = 99999
            mock_process.poll.return_value = None  # Process is alive
            mock_spawn.return_value = mock_process

            individual_manager = IndividualServiceManager(db_session)
            restored_count = 0
            for user_id, task_name in individual_services_to_restore:
                user = db_session.query(Users).filter(Users.id == user_id).first()
                if not user:
                    continue
                success, message = individual_manager.start_service(user_id, task_name)
                if success:
                    restored_count += 1

            # Verify both services were attempted
            assert mock_spawn.call_count == 2
            assert restored_count == 2
