"""
Tests for signal exclusion when user has open positions (Phase 1/2 enhancement)

Tests verify that:
1. Signals with open positions are excluded from active signals list
2. Symbol normalization works correctly across variants
3. Signals with open positions are treated as TRADED (effective status)
4. Explicitly marked signals are still shown even with open positions
"""

import pytest
from datetime import datetime, timedelta

from src.infrastructure.db.models import (
    OrderStatus,
    Orders,
    Positions,
    SignalStatus,
    Signals,
    UserRole,
    Users,
)
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.signals_repository import SignalsRepository


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = Users(
        email="test@example.com",
        name="Test User",
        password_hash="dummy",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def active_signal(db_session, test_user):
    """Create an active signal"""
    signal = Signals(
        symbol="MIRZAINT.NS",
        status=SignalStatus.ACTIVE,
        ts=ist_now() - timedelta(hours=1),
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)
    return signal


@pytest.fixture
def active_signal_different_symbol(db_session, test_user):
    """Create an active signal for a different symbol"""
    signal = Signals(
        symbol="RELIANCE.NS",
        status=SignalStatus.ACTIVE,
        ts=ist_now() - timedelta(hours=1),
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)
    return signal


class TestSignalExclusionWithPositions:
    """Test that signals with open positions are excluded from active signals"""

    def test_signal_with_open_position_excluded_from_active(
        self, db_session, test_user, active_signal
    ):
        """Test that signal is excluded from active list when user has open position"""
        signals_repo = SignalsRepository(db_session, user_id=test_user.id)

        # Create open position for MIRZAINT
        position = Positions(
            user_id=test_user.id,
            symbol="MIRZAINT-EQ",  # Different variant
            quantity=10.0,
            avg_price=35.0,
            opened_at=ist_now() - timedelta(days=1),
        )
        db_session.add(position)
        db_session.commit()

        # Get active signals - should exclude MIRZAINT
        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100, status_filter=SignalStatus.ACTIVE
        )

        # MIRZAINT signal should not be in active list
        signal_symbols = {s.symbol for s, _ in signals_with_status}
        assert "MIRZAINT.NS" not in signal_symbols

    def test_signal_with_open_position_shown_as_traded(
        self, db_session, test_user, active_signal
    ):
        """Test that signal with open position is shown as TRADED when filtering for all"""
        signals_repo = SignalsRepository(db_session, user_id=test_user.id)

        # Create open position for MIRZAINT
        position = Positions(
            user_id=test_user.id,
            symbol="MIRZAINT-EQ",
            quantity=10.0,
            avg_price=35.0,
            opened_at=ist_now() - timedelta(days=1),
        )
        db_session.add(position)
        db_session.commit()

        # Get all signals (no status filter) - should show MIRZAINT as TRADED
        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100, status_filter=None
        )

        # Find MIRZAINT signal
        mirzaint_signal = None
        for signal, status in signals_with_status:
            if signal.symbol == "MIRZAINT.NS":
                mirzaint_signal = (signal, status)
                break

        # Should be found and shown as TRADED
        assert mirzaint_signal is not None
        assert mirzaint_signal[1] == SignalStatus.TRADED

    def test_signal_without_position_shown_as_active(
        self, db_session, test_user, active_signal_different_symbol
    ):
        """Test that signal without open position is shown as ACTIVE"""
        signals_repo = SignalsRepository(db_session, user_id=test_user.id)

        # Get active signals
        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100, status_filter=SignalStatus.ACTIVE
        )

        # RELIANCE signal should be in active list
        signal_symbols = {s.symbol for s, _ in signals_with_status}
        assert "RELIANCE.NS" in signal_symbols

        # Find RELIANCE signal and verify status
        reliance_signal = None
        for signal, status in signals_with_status:
            if signal.symbol == "RELIANCE.NS":
                reliance_signal = (signal, status)
                break

        assert reliance_signal is not None
        assert reliance_signal[1] == SignalStatus.ACTIVE

    def test_symbol_normalization_works_across_variants(
        self, db_session, test_user, active_signal
    ):
        """Test that symbol normalization works for different variants"""
        signals_repo = SignalsRepository(db_session, user_id=test_user.id)

        # Create position with different symbol variant (MIRZAINT-EQ)
        position = Positions(
            user_id=test_user.id,
            symbol="MIRZAINT-EQ",  # EQ variant
            quantity=10.0,
            avg_price=35.0,
            opened_at=ist_now() - timedelta(days=1),
        )
        db_session.add(position)
        db_session.commit()

        # Signal is MIRZAINT.NS - should still be excluded
        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100, status_filter=SignalStatus.ACTIVE
        )

        signal_symbols = {s.symbol for s, _ in signals_with_status}
        assert "MIRZAINT.NS" not in signal_symbols

    def test_explicitly_traded_signal_shown_even_with_position(
        self, db_session, test_user, active_signal
    ):
        """Test that explicitly marked TRADED signal is shown even with open position"""
        signals_repo = SignalsRepository(db_session, user_id=test_user.id)

        # Create open position
        position = Positions(
            user_id=test_user.id,
            symbol="MIRZAINT-EQ",
            quantity=10.0,
            avg_price=35.0,
            opened_at=ist_now() - timedelta(days=1),
        )
        db_session.add(position)
        db_session.commit()

        # Explicitly mark signal as TRADED
        signals_repo.mark_as_traded("MIRZAINT.NS", user_id=test_user.id, reason="order_placed")
        db_session.commit()

        # Get traded signals - should include MIRZAINT
        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100, status_filter=SignalStatus.TRADED
        )

        # MIRZAINT should be in traded list
        signal_symbols = {s.symbol for s, _ in signals_with_status}
        assert "MIRZAINT.NS" in signal_symbols

        # Verify status is TRADED
        for signal, status in signals_with_status:
            if signal.symbol == "MIRZAINT.NS":
                assert status == SignalStatus.TRADED
                break

    def test_multiple_positions_same_base_symbol(
        self, db_session, test_user, active_signal
    ):
        """Test that multiple positions with same base symbol exclude signal"""
        signals_repo = SignalsRepository(db_session, user_id=test_user.id)

        # Create multiple positions with different variants
        position1 = Positions(
            user_id=test_user.id,
            symbol="MIRZAINT-EQ",
            quantity=10.0,
            avg_price=35.0,
            opened_at=ist_now() - timedelta(days=2),
        )
        position2 = Positions(
            user_id=test_user.id,
            symbol="MIRZAINT-BE",  # Different variant
            quantity=5.0,
            avg_price=34.0,
            opened_at=ist_now() - timedelta(days=1),
        )
        db_session.add(position1)
        db_session.add(position2)
        db_session.commit()

        # Signal should be excluded from active list
        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100, status_filter=SignalStatus.ACTIVE
        )

        signal_symbols = {s.symbol for s, _ in signals_with_status}
        assert "MIRZAINT.NS" not in signal_symbols

    def test_closed_position_does_not_exclude_signal(
        self, db_session, test_user, active_signal
    ):
        """Test that closed positions don't exclude signals"""
        signals_repo = SignalsRepository(db_session, user_id=test_user.id)

        # Create closed position (not open)
        position = Positions(
            user_id=test_user.id,
            symbol="MIRZAINT-EQ",
            quantity=10.0,
            avg_price=35.0,
            opened_at=ist_now() - timedelta(days=5),
            closed_at=ist_now() - timedelta(days=1),  # Position is closed
        )
        db_session.add(position)
        db_session.commit()

        # Signal should still be in active list (position is closed)
        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100, status_filter=SignalStatus.ACTIVE
        )

        signal_symbols = {s.symbol for s, _ in signals_with_status}
        assert "MIRZAINT.NS" in signal_symbols

    def test_zero_quantity_position_does_not_exclude_signal(
        self, db_session, test_user, active_signal
    ):
        """Test that positions with zero quantity don't exclude signals"""
        signals_repo = SignalsRepository(db_session, user_id=test_user.id)

        # Create position with zero quantity
        position = Positions(
            user_id=test_user.id,
            symbol="MIRZAINT-EQ",
            quantity=0.0,  # Zero quantity
            avg_price=35.0,
            opened_at=ist_now() - timedelta(days=1),
        )
        db_session.add(position)
        db_session.commit()

        # Signal should still be in active list (position has zero quantity)
        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100, status_filter=SignalStatus.ACTIVE
        )

        signal_symbols = {s.symbol for s, _ in signals_with_status}
        assert "MIRZAINT.NS" in signal_symbols

    def test_position_different_user_does_not_exclude_signal(
        self, db_session, test_user, active_signal
    ):
        """Test that positions from different users don't exclude signals"""
        signals_repo = SignalsRepository(db_session, user_id=test_user.id)

        # Create another user
        other_user = Users(
            email="other@example.com",
            name="Other User",
            password_hash="dummy",
            role=UserRole.USER,
            is_active=True,
        )
        db_session.add(other_user)
        db_session.commit()

        # Create position for other user
        position = Positions(
            user_id=other_user.id,  # Different user
            symbol="MIRZAINT-EQ",
            quantity=10.0,
            avg_price=35.0,
            opened_at=ist_now() - timedelta(days=1),
        )
        db_session.add(position)
        db_session.commit()

        # Signal should still be in active list for test_user (other user's position doesn't matter)
        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100, status_filter=SignalStatus.ACTIVE
        )

        signal_symbols = {s.symbol for s, _ in signals_with_status}
        assert "MIRZAINT.NS" in signal_symbols

