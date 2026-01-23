"""
Unit tests for signal expiry logic

Tests cover:
- Time-based expiry calculation (next trading day)
- Weekend handling
- Holiday handling (when implemented)
- Database status updates
- Edge cases
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from src.infrastructure.db.models import Signals, SignalStatus, UserSignalStatus
from src.infrastructure.db.timezone_utils import IST
from src.infrastructure.persistence.signals_repository import SignalsRepository


@pytest.fixture
def signals_repo(db_session):
    """Create SignalsRepository instance"""
    return SignalsRepository(db_session)


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    from src.infrastructure.db.models import Users

    user = Users(
        email="test_expiry@example.com",
        password_hash="test_hash",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestSignalExpiryTimeCalculation:
    """Test get_signal_expiry_time() function"""

    def test_monday_signal_expires_tuesday(self, signals_repo):
        """Signal from Monday should expire on Tuesday at 3:30 PM"""
        # Monday, Dec 1, 2025 at 4:00 PM IST
        signal_time = datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST)

        expiry_time = signals_repo.get_signal_expiry_time(signal_time)

        # Should expire on Tuesday, Dec 2, 2025 at 3:30 PM IST
        expected_expiry = datetime(2025, 12, 2, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected_expiry

    def test_friday_signal_expires_monday(self, signals_repo):
        """Signal from Friday should expire on Monday (skip weekend)"""
        # Friday, Dec 5, 2025 at 4:00 PM IST
        signal_time = datetime(2025, 12, 5, 16, 0, 0, tzinfo=IST)

        expiry_time = signals_repo.get_signal_expiry_time(signal_time)

        # Should expire on Monday, Dec 8, 2025 at 3:30 PM IST (skip Sat/Sun)
        expected_expiry = datetime(2025, 12, 8, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected_expiry

    def test_thursday_signal_expires_friday(self, signals_repo):
        """Signal from Thursday should expire on Friday"""
        # Thursday, Dec 4, 2025 at 4:00 PM IST
        signal_time = datetime(2025, 12, 4, 16, 0, 0, tzinfo=IST)

        expiry_time = signals_repo.get_signal_expiry_time(signal_time)

        # Should expire on Friday, Dec 5, 2025 at 3:30 PM IST
        expected_expiry = datetime(2025, 12, 5, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected_expiry

    def test_saturday_signal_expires_monday(self, signals_repo):
        """Signal from Saturday should expire on Monday (skip Sunday)"""
        # Saturday, Dec 6, 2025 at 10:00 AM IST
        signal_time = datetime(2025, 12, 6, 10, 0, 0, tzinfo=IST)

        expiry_time = signals_repo.get_signal_expiry_time(signal_time)

        # Should expire on Monday, Dec 8, 2025 at 3:30 PM IST
        expected_expiry = datetime(2025, 12, 8, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected_expiry

    def test_sunday_signal_expires_monday(self, signals_repo):
        """Signal from Sunday should expire on Monday"""
        # Sunday, Dec 7, 2025 at 10:00 AM IST
        signal_time = datetime(2025, 12, 7, 10, 0, 0, tzinfo=IST)

        expiry_time = signals_repo.get_signal_expiry_time(signal_time)

        # Should expire on Monday, Dec 8, 2025 at 3:30 PM IST
        expected_expiry = datetime(2025, 12, 8, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected_expiry

    def test_signal_created_during_market_hours(self, signals_repo):
        """Signal created during market hours should still expire next trading day"""
        # Monday, Dec 1, 2025 at 2:00 PM IST (during market hours)
        signal_time = datetime(2025, 12, 1, 14, 0, 0, tzinfo=IST)

        expiry_time = signals_repo.get_signal_expiry_time(signal_time)

        # Should expire on Tuesday, Dec 2, 2025 at 3:30 PM IST (not Monday)
        expected_expiry = datetime(2025, 12, 2, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected_expiry

    def test_signal_created_after_market_close(self, signals_repo):
        """Signal created after market close should expire next trading day"""
        # Monday, Dec 1, 2025 at 4:00 PM IST (after market close)
        signal_time = datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST)

        expiry_time = signals_repo.get_signal_expiry_time(signal_time)

        # Should expire on Tuesday, Dec 2, 2025 at 3:30 PM IST
        expected_expiry = datetime(2025, 12, 2, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected_expiry

    def test_naive_datetime_handling(self, signals_repo):
        """Should handle naive datetime (assume IST)"""
        # Naive datetime (no timezone)
        signal_time = datetime(2025, 12, 1, 16, 0, 0)

        expiry_time = signals_repo.get_signal_expiry_time(signal_time)

        # Should still calculate correctly (assumes IST)
        expected_expiry = datetime(2025, 12, 2, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected_expiry
        assert expiry_time.tzinfo == IST  # Should be timezone-aware

    def test_holiday_handling_signal_before_holiday(self, signals_repo):
        """Signal before holiday should expire after holiday"""
        # Signal from Thursday, Apr 2, 2026 (next day is holiday: Apr 3 - Good Friday)
        signal_time = datetime(2026, 4, 2, 16, 0, 0, tzinfo=IST)

        expiry_time = signals_repo.get_signal_expiry_time(signal_time)

        # Should expire on Monday, Apr 6, 2026 at 3:30 PM IST (skip Good Friday + weekend)
        expected_expiry = datetime(2026, 4, 6, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected_expiry

    def test_holiday_handling_signal_on_friday_before_holiday_weekend(self, signals_repo):
        """Signal on Thursday before holiday weekend should skip holiday and weekend"""
        # Signal from Thursday, Apr 2, 2026 (next day is holiday: Apr 3 - Good Friday)
        signal_time = datetime(2026, 4, 2, 16, 0, 0, tzinfo=IST)

        expiry_time = signals_repo.get_signal_expiry_time(signal_time)

        # Should expire on Monday, Apr 6, 2026 at 3:30 PM IST (skip Good Friday + weekend)
        expected_expiry = datetime(2026, 4, 6, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected_expiry

    def test_holiday_handling_diwali_holidays(self, signals_repo):
        """Signal before Diwali holiday should skip the holiday"""
        # Signal from Monday, Nov 9, 2026 (next day is holiday: Nov 10 - Diwali-Balipratipada)
        signal_time = datetime(2026, 11, 9, 16, 0, 0, tzinfo=IST)

        expiry_time = signals_repo.get_signal_expiry_time(signal_time)

        # Should expire on Wednesday, Nov 11, 2026 at 3:30 PM IST (skip Nov 10 holiday)
        expected_expiry = datetime(2026, 11, 11, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected_expiry

    def test_holiday_handling_signal_on_holiday(self, signals_repo):
        """Signal created on holiday should expire on next trading day"""
        # Signal from holiday: Tuesday, Mar 31, 2026 (Shri Mahavir Jayanti)
        signal_time = datetime(2026, 3, 31, 16, 0, 0, tzinfo=IST)

        expiry_time = signals_repo.get_signal_expiry_time(signal_time)

        # Should expire on Wednesday, Apr 1, 2026 at 3:30 PM IST
        expected_expiry = datetime(2026, 4, 1, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected_expiry


class TestSignalExpiryCheck:
    """Test _is_signal_expired_by_market_close() function"""

    def test_signal_before_expiry_time_is_active(self, signals_repo):
        """Signal before expiry time should be active"""
        # Signal created Monday 4:00 PM, expires Tuesday 3:30 PM
        signal_time = datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST)

        # Mock current time: Tuesday 2:00 PM (before expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 14, 0, 0, tzinfo=IST)

            is_expired = signals_repo._is_signal_expired_by_market_close(signal_time)
            assert is_expired is False

    def test_signal_at_expiry_time_is_expired(self, signals_repo):
        """Signal exactly at expiry time should be expired"""
        # Signal created Monday 4:00 PM, expires Tuesday 3:30 PM
        signal_time = datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST)

        # Mock current time: Tuesday 3:30 PM (exactly at expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 15, 30, 0, tzinfo=IST)

            is_expired = signals_repo._is_signal_expired_by_market_close(signal_time)
            assert is_expired is True

    def test_signal_after_expiry_time_is_expired(self, signals_repo):
        """Signal after expiry time should be expired"""
        # Signal created Monday 4:00 PM, expires Tuesday 3:30 PM
        signal_time = datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST)

        # Mock current time: Tuesday 4:00 PM (after expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            is_expired = signals_repo._is_signal_expired_by_market_close(signal_time)
            assert is_expired is True

    def test_friday_signal_expires_after_weekend(self, signals_repo):
        """Friday signal should expire after weekend (Monday 3:30 PM)"""
        # Signal created Friday 4:00 PM, expires Monday 3:30 PM
        signal_time = datetime(2025, 12, 5, 16, 0, 0, tzinfo=IST)

        # Mock current time: Monday 3:31 PM (after expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 8, 15, 31, 0, tzinfo=IST)

            is_expired = signals_repo._is_signal_expired_by_market_close(signal_time)
            assert is_expired is True

    def test_friday_signal_active_during_weekend(self, signals_repo):
        """Friday signal should be active during weekend"""
        # Signal created Friday 4:00 PM, expires Monday 3:30 PM
        signal_time = datetime(2025, 12, 5, 16, 0, 0, tzinfo=IST)

        # Mock current time: Saturday 10:00 AM (weekend, but before expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 6, 10, 0, 0, tzinfo=IST)

            is_expired = signals_repo._is_signal_expired_by_market_close(signal_time)
            assert is_expired is False


class TestDatabaseStatusUpdate:
    """Test mark_time_expired_signals() function"""

    def test_mark_expired_signals_updates_status(self, db_session, signals_repo):
        """Should update ACTIVE signals to EXPIRED when past expiry time"""
        # Create signal from Monday (expires Tuesday 3:30 PM)
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Mock current time: Tuesday 4:00 PM (after expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            expired_count = signals_repo.mark_time_expired_signals()

            assert expired_count == 1
            db_session.refresh(signal)
            assert signal.status == SignalStatus.EXPIRED

    def test_mark_expired_signals_skips_active_signals(self, db_session, signals_repo):
        """Should not update signals that are still active"""
        # Create signal from Monday (expires Tuesday 3:30 PM)
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Mock current time: Tuesday 2:00 PM (before expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 14, 0, 0, tzinfo=IST)

            expired_count = signals_repo.mark_time_expired_signals()

            assert expired_count == 0
            db_session.refresh(signal)
            assert signal.status == SignalStatus.ACTIVE

    def test_mark_expired_signals_skips_already_expired(self, db_session, signals_repo):
        """Should not update signals that are already EXPIRED"""
        # Create already expired signal
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.EXPIRED,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        expired_count = signals_repo.mark_time_expired_signals()

        assert expired_count == 0
        db_session.refresh(signal)
        assert signal.status == SignalStatus.EXPIRED

    def test_mark_expired_signals_skips_traded_signals(self, db_session, signals_repo):
        """Should not update TRADED signals"""
        # Create traded signal
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.TRADED,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        expired_count = signals_repo.mark_time_expired_signals()

        assert expired_count == 0
        db_session.refresh(signal)
        assert signal.status == SignalStatus.TRADED

    def test_mark_expired_signals_expires_rejected_signals(self, db_session, signals_repo):
        """Should update REJECTED signals to EXPIRED when past expiry time"""
        # Create rejected signal from Monday (expires Tuesday 3:30 PM)
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.REJECTED,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Mock current time: Tuesday 4:00 PM (after expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            expired_count = signals_repo.mark_time_expired_signals()

            assert expired_count == 1
            db_session.refresh(signal)
            assert signal.status == SignalStatus.EXPIRED

    def test_mark_expired_signals_skips_rejected_signals_before_expiry(
        self, db_session, signals_repo
    ):
        """Should not update REJECTED signals that are still within expiry window"""
        # Create rejected signal from Monday (expires Tuesday 3:30 PM)
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.REJECTED,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Mock current time: Tuesday 2:00 PM (before expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 14, 0, 0, tzinfo=IST)

            expired_count = signals_repo.mark_time_expired_signals()

            assert expired_count == 0
            db_session.refresh(signal)
            assert signal.status == SignalStatus.REJECTED

    def test_mark_expired_signals_handles_multiple_signals(self, db_session, signals_repo):
        """Should handle multiple signals with different expiry times"""
        # Signal 1: Monday, Dec 1, 2025 (expires Tuesday, Dec 2, 3:30 PM)
        signal1 = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday
            verdict="buy",
        )
        # Signal 2: Tuesday, Dec 2, 2025 (expires Wednesday, Dec 3, 3:30 PM)
        signal2 = Signals(
            symbol="TCS",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST),  # Tuesday
            verdict="buy",
        )
        db_session.add_all([signal1, signal2])
        db_session.commit()

        # Mock current time: Wednesday, Dec 3, 4:00 PM (both expired)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 3, 16, 0, 0, tzinfo=IST)

            expired_count = signals_repo.mark_time_expired_signals()

            assert expired_count == 2
            db_session.refresh(signal1)
            db_session.refresh(signal2)
            assert signal1.status == SignalStatus.EXPIRED
            assert signal2.status == SignalStatus.EXPIRED

    def test_mark_expired_signals_partial_expiry(self, db_session, signals_repo):
        """Should only expire signals that have passed expiry time"""
        # Signal 1: Monday (expires Tuesday 3:30 PM)
        signal1 = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday
            verdict="buy",
        )
        # Signal 2: Tuesday (expires Wednesday 3:30 PM)
        signal2 = Signals(
            symbol="TCS",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST),  # Tuesday
            verdict="buy",
        )
        db_session.add_all([signal1, signal2])
        db_session.commit()

        # Mock current time: Tuesday 4:00 PM (only signal1 expired)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            expired_count = signals_repo.mark_time_expired_signals()

            assert expired_count == 1
            db_session.refresh(signal1)
            db_session.refresh(signal2)
            assert signal1.status == SignalStatus.EXPIRED
            assert signal2.status == SignalStatus.ACTIVE

    def test_mark_expired_signals_handles_active_and_rejected_together(
        self, db_session, signals_repo
    ):
        """Should expire both ACTIVE and REJECTED signals that are past expiry"""
        # Signal 1: ACTIVE from Monday (expires Tuesday 3:30 PM)
        signal1 = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
            verdict="buy",
        )
        # Signal 2: REJECTED from Monday (expires Tuesday 3:30 PM)
        signal2 = Signals(
            symbol="TCS",
            status=SignalStatus.REJECTED,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
            verdict="buy",
        )
        db_session.add_all([signal1, signal2])
        db_session.commit()

        # Mock current time: Tuesday 4:00 PM (after expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            expired_count = signals_repo.mark_time_expired_signals()

            assert expired_count == 2
            db_session.refresh(signal1)
            db_session.refresh(signal2)
            assert signal1.status == SignalStatus.EXPIRED
            assert signal2.status == SignalStatus.EXPIRED


class TestGetActiveSignalsIntegration:
    """Test get_active_signals() with expiry check integration"""

    def test_get_active_signals_expires_old_signals(self, db_session, signals_repo):
        """get_active_signals should expire old signals before returning"""
        # Create expired signal
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Mock current time: Tuesday 4:00 PM (after expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            active_signals = signals_repo.get_active_signals()

            # Should not return expired signal
            assert len(active_signals) == 0
            # Database status should be updated
            db_session.refresh(signal)
            assert signal.status == SignalStatus.EXPIRED

    def test_get_active_signals_returns_active_signals(self, db_session, signals_repo):
        """get_active_signals should return signals that are still active"""
        # Create active signal
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Mock current time: Tuesday 2:00 PM (before expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 14, 0, 0, tzinfo=IST)

            active_signals = signals_repo.get_active_signals()

            # Should return active signal
            assert len(active_signals) == 1
            assert active_signals[0].symbol == "RELIANCE"
            assert active_signals[0].status == SignalStatus.ACTIVE


class TestGetSignalsWithUserStatusExpiryCheck:
    """Test get_signals_with_user_status() with expiry check integration"""

    def test_get_signals_with_user_status_expires_old_signals(
        self, db_session, signals_repo, test_user
    ):
        """get_signals_with_user_status should expire old signals before returning"""
        # Create expired signal
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Mock current time: Tuesday 4:00 PM (after expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            signals_with_status = signals_repo.get_signals_with_user_status(
                user_id=test_user.id, limit=100
            )

            # Database status should be updated to EXPIRED
            db_session.refresh(signal)
            assert signal.status == SignalStatus.EXPIRED

            # Signal should be returned with EXPIRED status
            signal_found = False
            for sig, status in signals_with_status:
                if sig.id == signal.id:
                    signal_found = True
                    assert status == SignalStatus.EXPIRED
                    break
            assert signal_found

    def test_get_signals_with_user_status_returns_active_signals(
        self, db_session, signals_repo, test_user
    ):
        """get_signals_with_user_status should return signals that are still active"""
        # Create active signal
        signal = Signals(
            symbol="TCS",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Mock current time: Tuesday 2:00 PM (before expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 14, 0, 0, tzinfo=IST)

            signals_with_status = signals_repo.get_signals_with_user_status(
                user_id=test_user.id, limit=100
            )

            # Signal should still be ACTIVE
            db_session.refresh(signal)
            assert signal.status == SignalStatus.ACTIVE

            # Signal should be returned with ACTIVE status
            signal_found = False
            for sig, status in signals_with_status:
                if sig.id == signal.id:
                    signal_found = True
                    assert status == SignalStatus.ACTIVE
                    break
            assert signal_found

    def test_get_signals_with_user_status_traded_takes_precedence_over_expired(
        self, db_session, signals_repo, test_user
    ):
        """TRADED user status should take precedence over EXPIRED base status"""
        # Create signal with EXPIRED base status
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.EXPIRED,  # Base status is EXPIRED
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # User has TRADED override
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="RELIANCE",
            status=SignalStatus.TRADED,  # User status is TRADED
        )
        db_session.add(user_status)
        db_session.commit()

        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100
        )

        # Should return TRADED as effective status (not EXPIRED)
        signal_found = False
        for sig, status in signals_with_status:
            if sig.id == signal.id:
                signal_found = True
                assert status == SignalStatus.TRADED, "TRADED should take precedence over EXPIRED"
                break
        assert signal_found

    def test_get_signals_with_user_status_rejected_takes_precedence_over_expired(
        self, db_session, signals_repo, test_user
    ):
        """REJECTED user status should take precedence over EXPIRED base status"""
        # Create signal with EXPIRED base status
        signal = Signals(
            symbol="TCS",
            status=SignalStatus.EXPIRED,  # Base status is EXPIRED
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # User has REJECTED override
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="TCS",
            status=SignalStatus.REJECTED,  # User status is REJECTED
        )
        db_session.add(user_status)
        db_session.commit()

        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100
        )

        # Should return REJECTED as effective status (not EXPIRED)
        signal_found = False
        for sig, status in signals_with_status:
            if sig.id == signal.id:
                signal_found = True
                assert (
                    status == SignalStatus.REJECTED
                ), "REJECTED should take precedence over EXPIRED"
                break
        assert signal_found

    def test_get_signals_with_user_status_expired_when_no_user_action(
        self, db_session, signals_repo, test_user
    ):
        """EXPIRED base status should be returned when no user action (TRADED/REJECTED)"""
        # Create signal with EXPIRED base status
        signal = Signals(
            symbol="INFY",
            status=SignalStatus.EXPIRED,  # Base status is EXPIRED
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100
        )

        # Should return EXPIRED as effective status
        signal_found = False
        for sig, status in signals_with_status:
            if sig.id == signal.id:
                signal_found = True
                assert status == SignalStatus.EXPIRED
                break
        assert signal_found

    def test_get_signals_with_user_status_calls_expiry_check(
        self, db_session, signals_repo, test_user
    ):
        """Test that get_signals_with_user_status calls mark_time_expired_signals"""
        # Create a signal
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Mock mark_time_expired_signals to track calls
        with patch.object(signals_repo, "mark_time_expired_signals") as mock_expiry_check:
            mock_expiry_check.return_value = 0

            # Call get_signals_with_user_status
            signals_repo.get_signals_with_user_status(user_id=test_user.id, limit=100)

            # Verify mark_time_expired_signals was called
            mock_expiry_check.assert_called_once()

    def test_get_signals_with_user_status_traded_takes_precedence_over_expired(
        self, db_session, signals_repo, test_user
    ):
        """TRADED user status should take precedence over EXPIRED base status"""
        # Create signal with EXPIRED base status
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.EXPIRED,  # Base status is EXPIRED
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # User has TRADED override
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="RELIANCE",
            status=SignalStatus.TRADED,  # User status is TRADED
        )
        db_session.add(user_status)
        db_session.commit()

        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100
        )

        # Should return TRADED as effective status (not EXPIRED)
        signal_found = False
        for sig, status in signals_with_status:
            if sig.id == signal.id:
                signal_found = True
                assert status == SignalStatus.TRADED, "TRADED should take precedence over EXPIRED"
                break
        assert signal_found

    def test_get_signals_with_user_status_rejected_takes_precedence_over_expired(
        self, db_session, signals_repo, test_user
    ):
        """REJECTED user status should take precedence over EXPIRED base status"""
        # Create signal with EXPIRED base status
        signal = Signals(
            symbol="TCS",
            status=SignalStatus.EXPIRED,  # Base status is EXPIRED
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # User has REJECTED override
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="TCS",
            status=SignalStatus.REJECTED,  # User status is REJECTED
        )
        db_session.add(user_status)
        db_session.commit()

        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100
        )

        # Should return REJECTED as effective status (not EXPIRED)
        signal_found = False
        for sig, status in signals_with_status:
            if sig.id == signal.id:
                signal_found = True
                assert (
                    status == SignalStatus.REJECTED
                ), "REJECTED should take precedence over EXPIRED"
                break
        assert signal_found

    def test_get_signals_with_user_status_expired_when_no_user_action(
        self, db_session, signals_repo, test_user
    ):
        """EXPIRED base status should be returned when no user action (TRADED/REJECTED)"""
        # Create signal with EXPIRED base status
        signal = Signals(
            symbol="INFY",
            status=SignalStatus.EXPIRED,  # Base status is EXPIRED
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100
        )

        # Should return EXPIRED as effective status
        signal_found = False
        for sig, status in signals_with_status:
            if sig.id == signal.id:
                signal_found = True
                assert status == SignalStatus.EXPIRED
                break
        assert signal_found
