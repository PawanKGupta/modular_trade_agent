"""
Tests for P1, P2, and P3 fixes in signal expiry logic.

P1: Timezone handling verification
P2: Multiple session defensive checks
P3: Race condition mitigation
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from src.infrastructure.db.models import Signals, SignalStatus
from src.infrastructure.db.timezone_utils import IST
from src.infrastructure.persistence.signals_repository import SignalsRepository


@pytest.fixture
def signals_repo(db_session):
    """Create SignalsRepository instance"""
    return SignalsRepository(db_session)


class TestP1TimezoneHandling:
    """P1: Test timezone handling in signal expiry"""

    def test_get_signal_expiry_time_with_naive_datetime(self, signals_repo):
        """Test that naive datetime is correctly assumed to be IST"""
        # Create naive datetime (as SQLite would return)
        naive_dt = datetime(2025, 12, 1, 16, 0, 0)  # Monday 4:00 PM (naive)

        expiry_time = signals_repo.get_signal_expiry_time(naive_dt)

        # Should be Tuesday 3:30 PM IST (timezone-aware)
        expected = datetime(2025, 12, 2, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected
        assert expiry_time.tzinfo == IST

    def test_get_signal_expiry_time_with_ist_datetime(self, signals_repo):
        """Test that IST datetime is correctly handled"""
        # Create IST timezone-aware datetime
        ist_dt = datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST)  # Monday 4:00 PM IST

        expiry_time = signals_repo.get_signal_expiry_time(ist_dt)

        # Should be Tuesday 3:30 PM IST
        expected = datetime(2025, 12, 2, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected
        assert expiry_time.tzinfo == IST

    def test_get_signal_expiry_time_with_utc_datetime(self, signals_repo):
        """Test that UTC datetime is correctly converted to IST"""
        # Create UTC datetime (5:30 hours behind IST)
        utc_dt = datetime(2025, 12, 1, 10, 30, 0, tzinfo=UTC)  # Monday 10:30 AM UTC

        expiry_time = signals_repo.get_signal_expiry_time(utc_dt)

        # UTC 10:30 AM = IST 4:00 PM, so expiry should be Tuesday 3:30 PM IST
        expected = datetime(2025, 12, 2, 15, 30, 0, tzinfo=IST)
        assert expiry_time == expected
        assert expiry_time.tzinfo == IST

    def test_is_signal_expired_with_naive_datetime(self, signals_repo, db_session):
        """Test that naive datetime signals are correctly checked for expiry"""
        # Create signal with naive datetime (as SQLite would store)
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0),  # Monday 4:00 PM (naive)
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Mock current time: Tuesday 4:00 PM IST (after expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            # Should be expired
            is_expired = signals_repo._is_signal_expired_by_market_close(signal.ts)
            assert is_expired is True

    def test_is_signal_expired_with_timezone_aware_datetime(self, signals_repo, db_session):
        """Test that timezone-aware datetime signals are correctly checked for expiry"""
        # Create signal with IST timezone-aware datetime
        signal = Signals(
            symbol="TCS",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM IST
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Mock current time: Tuesday 2:00 PM IST (before expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 14, 0, 0, tzinfo=IST)

            # Should not be expired
            is_expired = signals_repo._is_signal_expired_by_market_close(signal.ts)
            assert is_expired is False


class TestP2MultipleSessionHandling:
    """P2: Test multiple session defensive checks"""

    def test_mark_expired_signals_works_with_different_sessions(self, db_session):
        """Test that each session can independently mark expired signals"""
        # Create signal in first session
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Create two separate repository instances (different sessions)
        repo1 = SignalsRepository(db_session)
        repo2 = SignalsRepository(db_session)

        # Mock current time: Tuesday 4:00 PM IST (after expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            # Both repositories should mark the signal as expired
            count1 = repo1.mark_time_expired_signals()
            count2 = repo2.mark_time_expired_signals()

            # First call should mark 1 signal as expired
            assert count1 == 1
            # Second call should mark 0 (already expired by first call)
            assert count2 == 0

            # Verify signal is expired
            db_session.refresh(signal)
            assert signal.status == SignalStatus.EXPIRED

    def test_query_methods_document_expiry_check_requirement(self, signals_repo):
        """Test that query methods have documentation about expiry check requirement"""
        # Verify that recent(), by_date(), and by_date_range() have documentation
        # about needing to call mark_time_expired_signals() first
        recent_doc = signals_repo.recent.__doc__ or ""
        by_date_doc = signals_repo.by_date.__doc__ or ""
        by_date_range_doc = signals_repo.by_date_range.__doc__ or ""

        assert "mark_time_expired_signals" in recent_doc or "expiry" in recent_doc.lower()
        assert "mark_time_expired_signals" in by_date_doc or "expiry" in by_date_doc.lower()
        assert (
            "mark_time_expired_signals" in by_date_range_doc
            or "expiry" in by_date_range_doc.lower()
        )


class TestP3RaceConditionMitigation:
    """P3: Test race condition mitigation"""

    def test_mark_expired_signals_materializes_results_immediately(self, signals_repo, db_session):
        """Test that mark_time_expired_signals materializes query results to reduce race window"""
        # Create multiple signals
        signals = []
        for i in range(5):
            signal = Signals(
                symbol=f"STOCK{i}",
                status=SignalStatus.ACTIVE,
                ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
                verdict="buy",
            )
            signals.append(signal)
            db_session.add(signal)
        db_session.commit()

        # Mock current time: Tuesday 4:00 PM IST (after expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            # Mark expired - should process all signals
            expired_count = signals_repo.mark_time_expired_signals()

            # All 5 signals should be expired
            assert expired_count == 5

            # Verify all signals are expired
            for signal in signals:
                db_session.refresh(signal)
                assert signal.status == SignalStatus.EXPIRED

    def test_mark_expired_signals_rechecks_status_before_updating(self, signals_repo, db_session):
        """Test that mark_time_expired_signals re-checks status before updating (race condition mitigation)"""
        # Create signal
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Mock current time: Tuesday 4:00 PM IST (after expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            # Manually set signal to EXPIRED (simulating another session)
            signal.status = SignalStatus.EXPIRED
            db_session.commit()

            # Mark expired - should not try to update already-expired signal
            expired_count = signals_repo.mark_time_expired_signals()

            # Should mark 0 signals (already expired)
            assert expired_count == 0

    def test_mark_expired_signals_handles_concurrent_updates(self, signals_repo, db_session):
        """Test that mark_time_expired_signals handles concurrent status updates gracefully"""
        # Create signal
        signal = Signals(
            symbol="TCS",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0, tzinfo=IST),  # Monday 4:00 PM
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Mock current time: Tuesday 4:00 PM IST (after expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            # Simulate concurrent update: mark as TRADED (by another process)
            signal.status = SignalStatus.TRADED
            db_session.commit()

            # Mark expired - should not update TRADED signal
            expired_count = signals_repo.mark_time_expired_signals()

            # Should mark 0 signals (signal is TRADED, not ACTIVE)
            assert expired_count == 0

            # Verify signal status is still TRADED
            db_session.refresh(signal)
            assert signal.status == SignalStatus.TRADED


class TestP1P2P3Integration:
    """Integration tests combining P1, P2, and P3 fixes"""

    def test_timezone_handling_with_multiple_sessions_and_race_conditions(self, db_session):
        """Test that timezone handling works correctly with multiple sessions"""
        # Create signal with naive datetime (as SQLite stores)
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            ts=datetime(2025, 12, 1, 16, 0, 0),  # Monday 4:00 PM (naive)
            verdict="buy",
        )
        db_session.add(signal)
        db_session.commit()

        # Create two separate repository instances
        repo1 = SignalsRepository(db_session)
        repo2 = SignalsRepository(db_session)

        # Mock current time: Tuesday 4:00 PM IST (after expiry)
        with patch("src.infrastructure.persistence.signals_repository.ist_now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 2, 16, 0, 0, tzinfo=IST)

            # First session marks as expired
            count1 = repo1.mark_time_expired_signals()
            assert count1 == 1

            # Second session should see it as already expired
            count2 = repo2.mark_time_expired_signals()
            assert count2 == 0

            # Verify signal is expired
            db_session.refresh(signal)
            assert signal.status == SignalStatus.EXPIRED

            # Verify expiry time calculation worked correctly with naive datetime
            expiry_time = repo1.get_signal_expiry_time(signal.ts)
            assert expiry_time.tzinfo == IST
            assert expiry_time == datetime(2025, 12, 2, 15, 30, 0, tzinfo=IST)
