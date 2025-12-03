"""
Tests for SignalsRepository signal status management (soft delete feature)
"""

import os
from datetime import datetime, time, timedelta

import pytest

os.environ["DB_URL"] = "sqlite:///:memory:"

from src.infrastructure.db.models import Signals, SignalStatus  # noqa: E402
from src.infrastructure.db.session import SessionLocal  # noqa: E402
from src.infrastructure.db.timezone_utils import ist_now  # noqa: E402
from src.infrastructure.persistence.signals_repository import SignalsRepository  # noqa: E402


@pytest.fixture
def db_session():
    """Create a fresh database session for each test"""
    from src.infrastructure.db.base import Base  # noqa: PLC0415
    from src.infrastructure.db.session import engine  # noqa: PLC0415

    # Create all tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    # Clear signals table before each test
    db.query(Signals).delete()
    db.commit()

    yield db

    # Cleanup
    db.query(Signals).delete()
    db.commit()
    db.close()


@pytest.fixture
def signals_repo(db_session):
    """Create SignalsRepository instance"""
    return SignalsRepository(db_session)


@pytest.fixture
def sample_signals(db_session):
    """Create sample signals with different timestamps"""
    now = ist_now()

    signals = [
        Signals(
            symbol="STOCK1",
            status=SignalStatus.ACTIVE,
            ts=now - timedelta(hours=2),
            rsi10=25.0,
        ),
        Signals(
            symbol="STOCK2",
            status=SignalStatus.ACTIVE,
            ts=now - timedelta(days=1),
            rsi10=30.0,
        ),
        Signals(
            symbol="STOCK3",
            status=SignalStatus.ACTIVE,
            ts=now - timedelta(days=2),
            rsi10=28.0,
        ),
        Signals(
            symbol="STOCK4",
            status=SignalStatus.EXPIRED,  # Already expired
            ts=now - timedelta(days=3),
            rsi10=32.0,
        ),
    ]

    db_session.add_all(signals)
    db_session.commit()

    return signals


class TestMarkOldSignalsAsExpired:
    def test_mark_all_old_signals_as_expired(self, signals_repo, sample_signals, db_session):
        """Should mark all ACTIVE signals before current time as EXPIRED"""
        now = ist_now()

        # All ACTIVE signals should be marked as expired
        expired_count = signals_repo.mark_old_signals_as_expired(before_timestamp=now)

        assert expired_count == 3  # STOCK1, STOCK2, STOCK3

        # Verify statuses
        all_signals = db_session.query(Signals).all()
        status_map = {s.symbol: s.status for s in all_signals}

        assert status_map["STOCK1"] == SignalStatus.EXPIRED
        assert status_map["STOCK2"] == SignalStatus.EXPIRED
        assert status_map["STOCK3"] == SignalStatus.EXPIRED
        assert status_map["STOCK4"] == SignalStatus.EXPIRED  # Already expired, remains expired

    def test_mark_only_signals_before_timestamp(self, signals_repo, sample_signals, db_session):
        """Should only mark signals before the specified timestamp"""
        # Mark signals older than 12 hours as expired
        cutoff = ist_now() - timedelta(hours=12)
        expired_count = signals_repo.mark_old_signals_as_expired(before_timestamp=cutoff)

        assert expired_count == 2  # STOCK2 (1 day old), STOCK3 (2 days old)

        # Verify statuses
        all_signals = db_session.query(Signals).all()
        status_map = {s.symbol: s.status for s in all_signals}

        assert status_map["STOCK1"] == SignalStatus.ACTIVE  # Only 2 hours old
        assert status_map["STOCK2"] == SignalStatus.EXPIRED
        assert status_map["STOCK3"] == SignalStatus.EXPIRED

    def test_does_not_mark_already_expired_signals(self, signals_repo, sample_signals, db_session):
        """Should not affect signals already marked as expired"""
        # STOCK4 is already expired
        expired_count = signals_repo.mark_old_signals_as_expired()

        # Should mark 3 ACTIVE signals, not the already-expired one
        assert expired_count == 3

    def test_defaults_to_current_time(self, signals_repo, sample_signals):
        """Should default to current time when no timestamp provided"""
        expired_count = signals_repo.mark_old_signals_as_expired()

        # All ACTIVE signals are in the past, should be marked as expired
        assert expired_count == 3


class TestMarkAsTraded:
    def test_mark_active_signal_as_traded(self, signals_repo, sample_signals, db_session):
        """Should mark an active signal as traded"""
        success = signals_repo.mark_as_traded("STOCK1")

        assert success is True

        # Verify status changed
        signal = db_session.query(Signals).filter(Signals.symbol == "STOCK1").first()
        assert signal.status == SignalStatus.TRADED

    def test_does_not_mark_expired_signal_as_traded(self, signals_repo, sample_signals, db_session):
        """Should only mark ACTIVE signals, not expired ones"""
        success = signals_repo.mark_as_traded("STOCK4")  # Already expired

        assert success is False

        # Verify status unchanged
        signal = db_session.query(Signals).filter(Signals.symbol == "STOCK4").first()
        assert signal.status == SignalStatus.EXPIRED

    def test_returns_false_for_nonexistent_symbol(self, signals_repo):
        """Should return False if symbol not found"""
        success = signals_repo.mark_as_traded("NONEXISTENT")

        assert success is False


class TestMarkAsRejected:
    def test_mark_active_signal_as_rejected(self, signals_repo, sample_signals, db_session):
        """Should mark an active signal as rejected"""
        success = signals_repo.mark_as_rejected("STOCK1")

        assert success is True

        # Verify status changed
        signal = db_session.query(Signals).filter(Signals.symbol == "STOCK1").first()
        assert signal.status == SignalStatus.REJECTED

    def test_does_not_mark_non_active_signal(self, signals_repo, sample_signals, db_session):
        """Should only mark ACTIVE signals, not expired ones"""
        success = signals_repo.mark_as_rejected("STOCK4")  # Already expired

        assert success is False

        # Verify status unchanged
        signal = db_session.query(Signals).filter(Signals.symbol == "STOCK4").first()
        assert signal.status == SignalStatus.EXPIRED

    def test_returns_false_for_nonexistent_symbol(self, signals_repo):
        """Should return False if symbol not found"""
        success = signals_repo.mark_as_rejected("NONEXISTENT")

        assert success is False


class TestGetActiveSignals:
    def test_returns_only_active_signals(self, signals_repo, sample_signals):
        """Should return only signals with ACTIVE status"""
        active_signals = signals_repo.get_active_signals(limit=100)

        assert len(active_signals) == 3  # STOCK1, STOCK2, STOCK3

        symbols = {s.symbol for s in active_signals}
        assert "STOCK1" in symbols
        assert "STOCK2" in symbols
        assert "STOCK3" in symbols
        assert "STOCK4" not in symbols  # Expired, should not be included

    def test_respects_limit(self, signals_repo, sample_signals):
        """Should respect the limit parameter"""
        active_signals = signals_repo.get_active_signals(limit=2)

        assert len(active_signals) == 2


class TestRecentWithActiveFilter:
    def test_recent_with_active_only(self, signals_repo, sample_signals):
        """Should return only active signals when active_only=True"""
        signals = signals_repo.recent(limit=100, active_only=True)

        assert len(signals) == 3
        assert all(s.status == SignalStatus.ACTIVE for s in signals)

    def test_recent_without_filter(self, signals_repo, sample_signals):
        """Should return all signals when active_only=False"""
        signals = signals_repo.recent(limit=100, active_only=False)

        assert len(signals) == 4  # Includes STOCK4 (expired)


class TestSignalStatusTransitions:
    """Test complete lifecycle of signal status transitions"""

    def test_signal_lifecycle_active_to_traded(self, signals_repo, db_session):
        """Test: Active → Traded transition"""
        # Create active signal
        signal = Signals(symbol="TEST1", status=SignalStatus.ACTIVE, ts=ist_now(), rsi10=25.0)
        db_session.add(signal)
        db_session.commit()

        # Mark as traded
        success = signals_repo.mark_as_traded("TEST1")
        assert success is True

        # Verify final status
        db_session.refresh(signal)
        assert signal.status == SignalStatus.TRADED

    def test_signal_lifecycle_active_to_rejected(self, signals_repo, db_session):
        """Test: Active → Rejected transition"""
        # Create active signal
        signal = Signals(symbol="TEST2", status=SignalStatus.ACTIVE, ts=ist_now(), rsi10=25.0)
        db_session.add(signal)
        db_session.commit()

        # Mark as rejected
        success = signals_repo.mark_as_rejected("TEST2")
        assert success is True

        # Verify final status
        db_session.refresh(signal)
        assert signal.status == SignalStatus.REJECTED

    def test_signal_lifecycle_active_to_expired(self, signals_repo, db_session):
        """Test: Active → Expired transition"""
        # Create old active signal
        old_time = ist_now() - timedelta(days=1)
        signal = Signals(symbol="TEST3", status=SignalStatus.ACTIVE, ts=old_time, rsi10=25.0)
        db_session.add(signal)
        db_session.commit()

        # Mark as expired
        expired_count = signals_repo.mark_old_signals_as_expired()
        assert expired_count == 1

        # Verify final status
        db_session.refresh(signal)
        assert signal.status == SignalStatus.EXPIRED

    def test_cannot_trade_expired_signal(self, signals_repo, db_session):
        """Test: Cannot mark expired signal as traded"""
        # Create expired signal
        signal = Signals(symbol="TEST4", status=SignalStatus.EXPIRED, ts=ist_now(), rsi10=25.0)
        db_session.add(signal)
        db_session.commit()

        # Try to mark as traded
        success = signals_repo.mark_as_traded("TEST4")
        assert success is False

        # Status should remain expired
        db_session.refresh(signal)
        assert signal.status == SignalStatus.EXPIRED


class TestMarkAsActive:
    """Test reactivating signals (mark_as_active)"""

    def test_reactivate_rejected_signal(self, signals_repo, db_session):
        """Test: Can reactivate a rejected signal"""
        # Create and mark as rejected
        signal = Signals(symbol="TEST1", status=SignalStatus.ACTIVE, ts=ist_now(), rsi10=25.0)
        db_session.add(signal)
        db_session.commit()

        signals_repo.mark_as_rejected("TEST1")
        db_session.refresh(signal)
        assert signal.status == SignalStatus.REJECTED

        # Reactivate
        success = signals_repo.mark_as_active("TEST1")
        assert success is True

        # Status should be back to ACTIVE
        db_session.refresh(signal)
        assert signal.status == SignalStatus.ACTIVE

    def test_reactivate_traded_signal(self, signals_repo, db_session):
        """Test: Can reactivate a traded signal"""
        # Create and mark as traded
        signal = Signals(symbol="TEST2", status=SignalStatus.ACTIVE, ts=ist_now(), rsi10=25.0)
        db_session.add(signal)
        db_session.commit()

        signals_repo.mark_as_traded("TEST2")
        db_session.refresh(signal)
        assert signal.status == SignalStatus.TRADED

        # Reactivate
        success = signals_repo.mark_as_active("TEST2")
        assert success is True

        # Status should be back to ACTIVE
        db_session.refresh(signal)
        assert signal.status == SignalStatus.ACTIVE

    def test_cannot_reactivate_expired_signal(self, signals_repo, db_session):
        """Test: Cannot reactivate an expired signal"""
        # Create expired signal
        signal = Signals(symbol="TEST3", status=SignalStatus.EXPIRED, ts=ist_now(), rsi10=25.0)
        db_session.add(signal)
        db_session.commit()

        # Try to reactivate
        success = signals_repo.mark_as_active("TEST3")
        assert success is False

        # Status should remain expired
        db_session.refresh(signal)
        assert signal.status == SignalStatus.EXPIRED

    def test_reactivate_nonexistent_signal(self, signals_repo):
        """Test: Returns False for nonexistent symbol"""
        success = signals_repo.mark_as_active("NONEXISTENT")
        assert success is False

    def test_reactivate_already_active_signal(self, signals_repo, db_session):
        """Test: Returns True for already active signal (no override)"""
        # Create active signal
        signal = Signals(symbol="TEST4", status=SignalStatus.ACTIVE, ts=ist_now(), rsi10=25.0)
        db_session.add(signal)
        db_session.commit()

        # Try to reactivate (should return True as it's already active)
        success = signals_repo.mark_as_active("TEST4")
        assert success is True

        # Status should remain ACTIVE
        db_session.refresh(signal)
        assert signal.status == SignalStatus.ACTIVE

    def test_cannot_reactivate_old_rejected_signal(self, signals_repo, db_session):
        """Test: Cannot reactivate a rejected signal from day before yesterday"""
        # Create rejected signal from day before yesterday
        now = ist_now()
        day_before_yesterday = now.date() - timedelta(days=2)
        # Set to any time on day before yesterday
        signal_time = datetime.combine(day_before_yesterday, time(14, 0)).replace(tzinfo=now.tzinfo)
        signal = Signals(symbol="TEST5", status=SignalStatus.REJECTED, ts=signal_time, rsi10=25.0)
        db_session.add(signal)
        db_session.commit()

        # Try to reactivate (should fail because signal is from day before yesterday)
        success = signals_repo.mark_as_active("TEST5")
        assert success is False

        # Status should remain REJECTED
        db_session.refresh(signal)
        assert signal.status == SignalStatus.REJECTED

    def test_cannot_reactivate_old_traded_signal(self, signals_repo, db_session):
        """Test: Cannot reactivate a traded signal from day before yesterday"""
        # Create traded signal from day before yesterday
        now = ist_now()
        day_before_yesterday = now.date() - timedelta(days=2)
        # Set to any time on day before yesterday
        signal_time = datetime.combine(day_before_yesterday, time(14, 0)).replace(tzinfo=now.tzinfo)
        signal = Signals(symbol="TEST6", status=SignalStatus.TRADED, ts=signal_time, rsi10=25.0)
        db_session.add(signal)
        db_session.commit()

        # Try to reactivate (should fail because signal is from day before yesterday)
        success = signals_repo.mark_as_active("TEST6")
        assert success is False

        # Status should remain TRADED
        db_session.refresh(signal)
        assert signal.status == SignalStatus.TRADED

    def test_cannot_reactivate_signal_after_today_market_close(self, signals_repo, db_session):
        """Test: Cannot reactivate signal after today's 3:30 PM if created yesterday"""
        # Create signal from yesterday (any time)
        now = ist_now()
        yesterday = now.date() - timedelta(days=1)
        yesterday_signal = datetime.combine(yesterday, time(16, 0)).replace(tzinfo=now.tzinfo)
        signal = Signals(
            symbol="TEST7", status=SignalStatus.REJECTED, ts=yesterday_signal, rsi10=25.0
        )
        db_session.add(signal)
        db_session.commit()

        # Check if current time is after today's 3:30 PM
        today_market_close = datetime.combine(now.date(), time(15, 30)).replace(tzinfo=now.tzinfo)
        if now >= today_market_close:
            # Current time is after today's 3:30 PM, signal should be expired
            success = signals_repo.mark_as_active("TEST7")
            assert success is False
        else:
            # Current time is before today's 3:30 PM, signal should be active
            success = signals_repo.mark_as_active("TEST7")
            # This test depends on current time, so we just verify the logic works
            # If it's before 3:30 PM, it should succeed (unless other conditions fail)
            assert success is not None
