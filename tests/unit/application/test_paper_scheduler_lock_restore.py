"""Regression tests for paper scheduler lock handling on restore."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.application.services.multi_user_trading_service import MultiUserTradingService
from src.application.services.service_restore_snapshot import clear_scheduler_locks_for_users
from src.infrastructure.db.models import SchedulerLock, Users
from src.infrastructure.db.timezone_utils import ist_now


class TestClearSchedulerLocksForRestore:
    def test_clears_locks_for_target_users(self, db_session):
        user = Users(
            email="lock-restore@example.com",
            password_hash="hash",
            created_at=ist_now(),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        db_session.add(
            SchedulerLock(
                user_id=user.id,
                locked_at=ist_now(),
                lock_id="stale-lock",
                expires_at=ist_now(),
            )
        )
        db_session.commit()

        deleted = clear_scheduler_locks_for_users(db_session, [user.id])

        assert deleted >= 1
        assert db_session.query(SchedulerLock).filter(SchedulerLock.user_id == user.id).count() == 0


class TestPaperSchedulerLockFailureExit:
    def test_lock_failure_does_not_mark_service_stopped(self):
        paper_service = MagicMock()
        paper_service.running = False

        with (
            patch(
                "src.application.services.multi_user_trading_service.get_user_logger",
                return_value=MagicMock(),
            ),
            patch("src.infrastructure.db.session.SessionLocal") as mock_session_local,
            patch(
                "src.application.services.multi_user_trading_service._try_acquire_paper_scheduler_lock",
                return_value=(False, None),
            ),
            patch(
                "src.application.services.multi_user_trading_service._cleanup_stale_paper_scheduler_lock",
                return_value=True,
            ),
            patch("src.application.services.multi_user_trading_service.time.sleep"),
        ):
            service = MultiUserTradingService.__new__(MultiUserTradingService)
            service._lock_keys = {}
            mock_thread_db = MagicMock()
            mock_session_local.return_value = mock_thread_db

            with patch.object(
                service,
                "_apply_paper_scheduler_thread_exit_status",
            ) as mock_apply_exit:
                service._run_paper_trading_scheduler(paper_service, user_id=42, service_generation=1)

            mock_apply_exit.assert_not_called()
