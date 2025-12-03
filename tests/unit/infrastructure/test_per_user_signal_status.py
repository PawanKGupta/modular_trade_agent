"""
Tests for per-user signal status tracking

Tests that signal status (TRADED/REJECTED) is tracked per-user
while keeping base signals shared across users.
"""

from datetime import datetime, time, timedelta

import pytest

from src.infrastructure.db.models import Signals, SignalStatus, Users, UserSignalStatus
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.signals_repository import SignalsRepository


@pytest.fixture
def test_users(db_session):
    """Create test users"""
    user1 = Users(email="user1@test.com", password_hash="hash1", role="user")
    user2 = Users(email="user2@test.com", password_hash="hash2", role="user")
    db_session.add_all([user1, user2])
    db_session.commit()
    db_session.refresh(user1)
    db_session.refresh(user2)
    return user1, user2


@pytest.fixture
def test_signal(db_session):
    """Create a test signal"""
    signal = Signals(
        symbol="RELIANCE",
        status=SignalStatus.ACTIVE,
        rsi10=25.0,
        ema9=2600.0,
        last_close=2500.0,
        verdict="buy",
        ts=ist_now(),
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)
    return signal


class TestPerUserSignalStatus:
    """Test per-user signal status tracking"""

    def test_mark_as_traded_creates_user_status(self, db_session, test_users, test_signal):
        """Test that marking as traded creates user-specific status"""
        user1, user2 = test_users

        repo = SignalsRepository(db_session, user_id=user1.id)
        success = repo.mark_as_traded("RELIANCE", user_id=user1.id)

        assert success is True

        # Verify user status was created
        user_status = (
            db_session.query(UserSignalStatus)
            .filter_by(user_id=user1.id, signal_id=test_signal.id)
            .first()
        )

        assert user_status is not None
        assert user_status.status == SignalStatus.TRADED
        assert user_status.symbol == "RELIANCE"

        # Base signal should still be ACTIVE (not modified)
        db_session.refresh(test_signal)
        assert test_signal.status == SignalStatus.ACTIVE

    def test_mark_as_traded_does_not_affect_other_users(self, db_session, test_users, test_signal):
        """Test that one user marking as traded doesn't affect other users"""
        user1, user2 = test_users

        # User 1 marks as traded
        repo1 = SignalsRepository(db_session, user_id=user1.id)
        repo1.mark_as_traded("RELIANCE", user_id=user1.id)

        # User 2 should not have this status
        user2_status = (
            db_session.query(UserSignalStatus)
            .filter_by(user_id=user2.id, signal_id=test_signal.id)
            .first()
        )

        assert user2_status is None  # User 2 has no custom status

        # Base signal still ACTIVE
        db_session.refresh(test_signal)
        assert test_signal.status == SignalStatus.ACTIVE

    def test_mark_as_rejected_creates_user_status(self, db_session, test_users, test_signal):
        """Test that marking as rejected creates user-specific status"""
        user1, user2 = test_users

        repo = SignalsRepository(db_session, user_id=user1.id)
        success = repo.mark_as_rejected("RELIANCE", user_id=user1.id)

        assert success is True

        # Verify user status was created
        user_status = (
            db_session.query(UserSignalStatus)
            .filter_by(user_id=user1.id, signal_id=test_signal.id)
            .first()
        )

        assert user_status is not None
        assert user_status.status == SignalStatus.REJECTED

        # Base signal should still be ACTIVE
        db_session.refresh(test_signal)
        assert test_signal.status == SignalStatus.ACTIVE

    def test_different_users_can_have_different_statuses(self, db_session, test_users, test_signal):
        """Test that different users can have different statuses for same signal"""
        user1, user2 = test_users

        # User 1 marks as traded
        repo1 = SignalsRepository(db_session, user_id=user1.id)
        repo1.mark_as_traded("RELIANCE", user_id=user1.id)

        # User 2 marks as rejected
        repo2 = SignalsRepository(db_session, user_id=user2.id)
        repo2.mark_as_rejected("RELIANCE", user_id=user2.id)

        # Verify different statuses
        user1_status = (
            db_session.query(UserSignalStatus)
            .filter_by(user_id=user1.id, signal_id=test_signal.id)
            .first()
        )
        user2_status = (
            db_session.query(UserSignalStatus)
            .filter_by(user_id=user2.id, signal_id=test_signal.id)
            .first()
        )

        assert user1_status.status == SignalStatus.TRADED
        assert user2_status.status == SignalStatus.REJECTED

        # Base signal still ACTIVE
        db_session.refresh(test_signal)
        assert test_signal.status == SignalStatus.ACTIVE

    def test_get_user_signal_status_returns_custom_status(
        self, db_session, test_users, test_signal
    ):
        """Test that get_user_signal_status returns user's custom status"""
        user1, user2 = test_users

        # User 1 marks as traded
        repo = SignalsRepository(db_session, user_id=user1.id)
        repo.mark_as_traded("RELIANCE", user_id=user1.id)

        # Get status for user 1
        status1 = repo.get_user_signal_status(test_signal.id, user1.id)
        assert status1 == SignalStatus.TRADED

        # Get status for user 2 (no custom status)
        status2 = repo.get_user_signal_status(test_signal.id, user2.id)
        assert status2 is None  # No custom status, uses base signal status

    def test_expired_signals_remain_global(self, db_session, test_users, test_signal):
        """Test that EXPIRED status remains global (not per-user)"""
        user1, user2 = test_users

        # Mark signal as expired (global operation)
        test_signal.status = SignalStatus.EXPIRED
        db_session.commit()

        # Both users should see it as expired (no user-specific override)
        repo1 = SignalsRepository(db_session, user_id=user1.id)
        repo2 = SignalsRepository(db_session, user_id=user2.id)

        status1 = repo1.get_user_signal_status(test_signal.id, user1.id)
        status2 = repo2.get_user_signal_status(test_signal.id, user2.id)

        # Both should be None (no user override) - base signal is EXPIRED
        assert status1 is None
        assert status2 is None
        assert test_signal.status == SignalStatus.EXPIRED

    def test_get_signals_with_user_status_applies_user_overrides(
        self, db_session, test_users, test_signal
    ):
        """Test that get_signals_with_user_status returns correct effective status"""
        user1, user2 = test_users

        # User 1 marks as traded
        repo1 = SignalsRepository(db_session, user_id=user1.id)
        repo1.mark_as_traded("RELIANCE", user_id=user1.id)

        # Get signals for user 1 (should show as TRADED)
        signals_user1 = repo1.get_signals_with_user_status(user1.id, limit=100)
        assert len(signals_user1) == 1
        signal, effective_status = signals_user1[0]
        assert signal.id == test_signal.id
        assert effective_status == SignalStatus.TRADED  # User's custom status

        # Get signals for user 2 (should show as ACTIVE)
        repo2 = SignalsRepository(db_session, user_id=user2.id)
        signals_user2 = repo2.get_signals_with_user_status(user2.id, limit=100)
        assert len(signals_user2) == 1
        signal, effective_status = signals_user2[0]
        assert signal.id == test_signal.id
        assert effective_status == SignalStatus.ACTIVE  # Base signal status

    def test_status_filter_with_user_overrides(self, db_session, test_users, test_signal):
        """Test that status filtering works with user overrides"""
        user1, user2 = test_users

        # User 1 marks as traded
        repo1 = SignalsRepository(db_session, user_id=user1.id)
        repo1.mark_as_traded("RELIANCE", user_id=user1.id)

        # User 1 filters for ACTIVE signals (should get 0 results)
        active_signals_user1 = repo1.get_signals_with_user_status(
            user1.id, limit=100, status_filter=SignalStatus.ACTIVE
        )
        assert len(active_signals_user1) == 0  # Signal is TRADED for user1

        # User 1 filters for TRADED signals (should get 1 result)
        traded_signals_user1 = repo1.get_signals_with_user_status(
            user1.id, limit=100, status_filter=SignalStatus.TRADED
        )
        assert len(traded_signals_user1) == 1

        # User 2 filters for ACTIVE signals (should get 1 result)
        repo2 = SignalsRepository(db_session, user_id=user2.id)
        active_signals_user2 = repo2.get_signals_with_user_status(
            user2.id, limit=100, status_filter=SignalStatus.ACTIVE
        )
        assert len(active_signals_user2) == 1  # Signal is ACTIVE for user2

    def test_update_existing_user_status(self, db_session, test_users, test_signal):
        """Test that marking again updates existing user status"""
        user1, user2 = test_users

        repo = SignalsRepository(db_session, user_id=user1.id)

        # First mark as traded
        repo.mark_as_traded("RELIANCE", user_id=user1.id)

        # Then mark as rejected (should update, not create duplicate)
        repo.mark_as_rejected("RELIANCE", user_id=user1.id)

        # Should only have one user status entry
        user_statuses = (
            db_session.query(UserSignalStatus)
            .filter_by(user_id=user1.id, signal_id=test_signal.id)
            .all()
        )

        assert len(user_statuses) == 1
        assert user_statuses[0].status == SignalStatus.REJECTED  # Updated to REJECTED

    def test_mark_as_active_removes_user_status_override(self, db_session, test_users, test_signal):
        """Test that marking as active removes user-specific status override"""
        user1, user2 = test_users

        # User 1 marks as traded
        repo = SignalsRepository(db_session, user_id=user1.id)
        repo.mark_as_traded("RELIANCE", user_id=user1.id)

        # Verify user status exists
        user_status = (
            db_session.query(UserSignalStatus)
            .filter_by(user_id=user1.id, signal_id=test_signal.id)
            .first()
        )
        assert user_status is not None
        assert user_status.status == SignalStatus.TRADED

        # Reactivate
        success = repo.mark_as_active("RELIANCE", user_id=user1.id)
        assert success is True

        # User status override should be removed
        user_status = (
            db_session.query(UserSignalStatus)
            .filter_by(user_id=user1.id, signal_id=test_signal.id)
            .first()
        )
        assert user_status is None  # Override removed

        # Base signal should still be ACTIVE
        db_session.refresh(test_signal)
        assert test_signal.status == SignalStatus.ACTIVE

    def test_mark_as_active_cannot_reactivate_expired_base_signal(
        self, db_session, test_users, test_signal
    ):
        """Test that cannot reactivate if base signal is expired"""
        user1, user2 = test_users

        # Mark base signal as expired
        test_signal.status = SignalStatus.EXPIRED
        db_session.commit()

        # User 1 marks as traded (on expired base signal)
        repo = SignalsRepository(db_session, user_id=user1.id)
        # Note: mark_as_traded should fail for expired signals, but let's test the reactivation
        # First create a user status manually to simulate the scenario
        user_status = UserSignalStatus(
            user_id=user1.id,
            signal_id=test_signal.id,
            symbol="RELIANCE",
            status=SignalStatus.TRADED,
            marked_at=ist_now(),
        )
        db_session.add(user_status)
        db_session.commit()

        # Try to reactivate (should fail because base is expired)
        success = repo.mark_as_active("RELIANCE", user_id=user1.id)
        assert success is False

        # User status should still exist
        user_status = (
            db_session.query(UserSignalStatus)
            .filter_by(user_id=user1.id, signal_id=test_signal.id)
            .first()
        )
        assert user_status is not None

    def test_mark_as_active_cannot_reactivate_old_signal(self, db_session, test_users):
        """Test that cannot reactivate a signal from day before yesterday"""
        user1, user2 = test_users

        # Create signal from day before yesterday
        now = ist_now()
        day_before_yesterday = now.date() - timedelta(days=2)
        # Set to any time on day before yesterday
        signal_time = datetime.combine(day_before_yesterday, time(14, 0)).replace(tzinfo=now.tzinfo)
        old_signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            rsi10=25.0,
            ema9=2600.0,
            last_close=2500.0,
            verdict="buy",
            ts=signal_time,
        )
        db_session.add(old_signal)
        db_session.commit()
        db_session.refresh(old_signal)

        # User 1 marks as traded
        repo = SignalsRepository(db_session, user_id=user1.id)
        # Create user status manually since mark_as_traded might fail for old signals
        user_status = UserSignalStatus(
            user_id=user1.id,
            signal_id=old_signal.id,
            symbol="RELIANCE",
            status=SignalStatus.TRADED,
            marked_at=ist_now(),
        )
        db_session.add(user_status)
        db_session.commit()

        # Try to reactivate (should fail because signal is from previous day)
        success = repo.mark_as_active("RELIANCE", user_id=user1.id)
        assert success is False

        # User status should still exist
        user_status = (
            db_session.query(UserSignalStatus)
            .filter_by(user_id=user1.id, signal_id=old_signal.id)
            .first()
        )
        assert user_status is not None

    def test_mark_as_active_does_not_affect_other_users(self, db_session, test_users, test_signal):
        """Test that reactivating for one user doesn't affect other users"""
        user1, user2 = test_users

        # Both users mark as traded
        repo1 = SignalsRepository(db_session, user_id=user1.id)
        repo2 = SignalsRepository(db_session, user_id=user2.id)
        repo1.mark_as_traded("RELIANCE", user_id=user1.id)
        repo2.mark_as_traded("RELIANCE", user_id=user2.id)

        # User 1 reactivates
        success = repo1.mark_as_active("RELIANCE", user_id=user1.id)
        assert success is True

        # User 1's override should be removed
        user1_status = (
            db_session.query(UserSignalStatus)
            .filter_by(user_id=user1.id, signal_id=test_signal.id)
            .first()
        )
        assert user1_status is None

        # User 2's override should still exist
        user2_status = (
            db_session.query(UserSignalStatus)
            .filter_by(user_id=user2.id, signal_id=test_signal.id)
            .first()
        )
        assert user2_status is not None
        assert user2_status.status == SignalStatus.TRADED

    def test_mark_as_active_rejected_signal(self, db_session, test_users, test_signal):
        """Test reactivating a rejected signal"""
        user1, user2 = test_users

        # User 1 marks as rejected
        repo = SignalsRepository(db_session, user_id=user1.id)
        repo.mark_as_rejected("RELIANCE", user_id=user1.id)

        # Verify user status exists
        user_status = (
            db_session.query(UserSignalStatus)
            .filter_by(user_id=user1.id, signal_id=test_signal.id)
            .first()
        )
        assert user_status.status == SignalStatus.REJECTED

        # Reactivate
        success = repo.mark_as_active("RELIANCE", user_id=user1.id)
        assert success is True

        # User status override should be removed
        user_status = (
            db_session.query(UserSignalStatus)
            .filter_by(user_id=user1.id, signal_id=test_signal.id)
            .first()
        )
        assert user_status is None
