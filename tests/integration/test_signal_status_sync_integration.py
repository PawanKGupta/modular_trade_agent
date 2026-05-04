"""
Integration tests for Signal Status Sync Implementation

Tests the integration of sync functionality with positions repository
and EOD cleanup workflows.
"""

import pytest

from src.infrastructure.db.models import (
    Orders,
    OrderStatus,
    Positions,
    Signals,
    SignalStatus,
    Users,
    UserSignalStatus,
)
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence import signals_repository
from src.infrastructure.persistence.positions_repository import PositionsRepository
from src.infrastructure.persistence.signals_repository import SignalsRepository


@pytest.fixture
def test_user(db_session):
    user = Users(email="sync_integration@example.com", password_hash="test_hash", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def signals_repo(db_session, test_user):
    return SignalsRepository(db_session, user_id=test_user.id)


@pytest.fixture
def positions_repo(db_session):
    return PositionsRepository(db_session)


class TestEventDrivenSyncIntegration:
    """Test event-driven sync in positions_repository.upsert()"""

    def test_position_creation_triggers_signal_sync(
        self, positions_repo, signals_repo, test_user, db_session
    ):
        """Test that creating a position automatically marks signal as TRADED"""
        # Create signal
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            verdict="buy",
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Create position (should trigger sync)
        _position = positions_repo.upsert(
            user_id=test_user.id,
            symbol="RELIANCE",
            quantity=10.0,
            avg_price=2500.0,
            auto_commit=True,  # Triggers sync
        )

        # Verify position was created
        assert _position is not None
        assert _position.quantity == 10.0

        # Verify signal was automatically marked as TRADED
        user_status = signals_repo.get_user_signal_status(signal.id, test_user.id)
        assert user_status == SignalStatus.TRADED

    def test_position_update_triggers_signal_sync(
        self, positions_repo, signals_repo, test_user, db_session
    ):
        """Test that updating a position automatically marks signal as TRADED"""
        # Create signal
        signal = Signals(
            symbol="TCS",
            status=SignalStatus.ACTIVE,
            verdict="buy",
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Create initial position
        _position = positions_repo.upsert(
            user_id=test_user.id,
            symbol="TCS",
            quantity=5.0,
            avg_price=3500.0,
            auto_commit=True,
        )

        # Update position (should trigger sync again)
        updated_position = positions_repo.upsert(
            user_id=test_user.id,
            symbol="TCS",
            quantity=15.0,  # Increased quantity
            avg_price=3600.0,
            auto_commit=True,
        )

        # Verify position was updated
        assert updated_position.quantity == 15.0

        # Verify signal is still TRADED (no double marking issue)
        user_status = signals_repo.get_user_signal_status(signal.id, test_user.id)
        assert user_status == SignalStatus.TRADED

        # Verify only one UserSignalStatus entry exists
        status_count = (
            db_session.query(UserSignalStatus)
            .filter(
                UserSignalStatus.user_id == test_user.id,
                UserSignalStatus.signal_id == signal.id,
            )
            .count()
        )
        assert status_count == 1

    def test_position_creation_without_auto_commit_does_not_sync(
        self, positions_repo, signals_repo, test_user, db_session
    ):
        """Test that sync only happens when auto_commit=True"""
        # Create signal
        signal = Signals(
            symbol="INFY",
            status=SignalStatus.ACTIVE,
            verdict="buy",
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Create position without auto_commit (inside transaction)
        position = positions_repo.upsert(
            user_id=test_user.id,
            symbol="INFY",
            quantity=20.0,
            avg_price=1500.0,
            auto_commit=False,  # No sync should happen
        )

        # Manually commit
        db_session.commit()

        # Verify position was created
        assert position is not None

        # Verify signal was NOT marked as TRADED (sync didn't run)
        user_status = signals_repo.get_user_signal_status(signal.id, test_user.id)
        assert user_status is None

    def test_position_creation_handles_sync_failure_gracefully(
        self, positions_repo, test_user, db_session, monkeypatch
    ):
        """Test that position creation succeeds even if sync fails"""
        # Create signal
        signal = Signals(
            symbol="WIPRO",
            status=SignalStatus.ACTIVE,
            verdict="buy",
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()

        # Mock sync to raise exception
        def mock_sync(*args, **kwargs):
            raise Exception("Sync failed")

        monkeypatch.setattr(
            signals_repository.SignalsRepository,
            "sync_traded_status_for_symbol",
            mock_sync,
        )

        # Create position (should succeed despite sync failure)
        position = positions_repo.upsert(
            user_id=test_user.id,
            symbol="WIPRO",
            quantity=10.0,
            avg_price=500.0,
            auto_commit=True,
        )

        # Verify position was created successfully
        assert position is not None
        assert position.quantity == 10.0

    def test_position_creation_with_zero_quantity_does_not_sync(
        self, positions_repo, signals_repo, test_user, db_session
    ):
        """Test that sync does not run for zero quantity positions"""
        # Create signal
        signal = Signals(
            symbol="SBIN",
            status=SignalStatus.ACTIVE,
            verdict="buy",
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Create position with zero quantity
        position = positions_repo.upsert(
            user_id=test_user.id,
            symbol="SBIN",
            quantity=0.0,  # Zero quantity
            avg_price=600.0,
            auto_commit=True,
        )

        # Verify position was created
        assert position is not None

        # Verify signal was NOT marked as TRADED (zero quantity)
        user_status = signals_repo.get_user_signal_status(signal.id, test_user.id)
        assert user_status is None

    def test_position_creation_with_symbol_variants(
        self, positions_repo, signals_repo, test_user, db_session
    ):
        """Test that sync handles symbol variants correctly"""
        # Create signal with .NS suffix
        signal = Signals(
            symbol="RELIANCE.NS",
            status=SignalStatus.ACTIVE,
            verdict="buy",
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Create position with -EQ suffix
        position = positions_repo.upsert(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            quantity=10.0,
            avg_price=2500.0,
            auto_commit=True,
        )

        # Verify position was created
        assert position is not None

        # Verify signal was marked as TRADED (symbol variant matching)
        user_status = signals_repo.get_user_signal_status(signal.id, test_user.id)
        assert user_status == SignalStatus.TRADED


class TestEODSyncIntegration:
    """Test EOD sync in cleanup workflows"""

    def test_eod_sync_marks_all_signals_with_positions(self, signals_repo, test_user, db_session):
        """Test that EOD sync marks all signals with positions as TRADED"""
        # Create multiple signals
        signal1 = Signals(
            symbol="RELIANCE", status=SignalStatus.ACTIVE, verdict="buy", ts=ist_now()
        )
        signal2 = Signals(symbol="TCS", status=SignalStatus.ACTIVE, verdict="buy", ts=ist_now())
        signal3 = Signals(symbol="INFY", status=SignalStatus.ACTIVE, verdict="buy", ts=ist_now())
        db_session.add_all([signal1, signal2, signal3])
        db_session.commit()

        # Create positions for all signals
        position1 = Positions(
            user_id=test_user.id,
            symbol="RELIANCE",
            quantity=10.0,
            avg_price=2500.0,
            closed_at=None,
        )
        position2 = Positions(
            user_id=test_user.id,
            symbol="TCS",
            quantity=5.0,
            avg_price=3500.0,
            closed_at=None,
        )
        position3 = Positions(
            user_id=test_user.id,
            symbol="INFY",
            quantity=20.0,
            avg_price=1500.0,
            closed_at=None,
        )
        db_session.add_all([position1, position2, position3])
        db_session.commit()

        # Run EOD sync
        count = signals_repo.sync_traded_status_from_positions_and_orders(user_id=test_user.id)
        assert count == 3

        # Verify all signals are marked as TRADED
        assert signals_repo.get_user_signal_status(signal1.id, test_user.id) == SignalStatus.TRADED
        assert signals_repo.get_user_signal_status(signal2.id, test_user.id) == SignalStatus.TRADED
        assert signals_repo.get_user_signal_status(signal3.id, test_user.id) == SignalStatus.TRADED

    def test_eod_sync_marks_signals_with_orders(self, signals_repo, test_user, db_session):
        """Test that EOD sync marks signals with active orders as TRADED"""
        # Create signal
        signal = Signals(
            symbol="WIPRO",
            status=SignalStatus.ACTIVE,
            verdict="buy",
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Create pending buy order
        order = Orders(
            user_id=test_user.id,
            symbol="WIPRO",
            side="buy",
            order_type="limit",
            quantity=10,
            price=500.0,
            status=OrderStatus.PENDING,
        )
        db_session.add(order)
        db_session.commit()

        # Run EOD sync
        count = signals_repo.sync_traded_status_from_positions_and_orders(user_id=test_user.id)
        assert count == 1

        # Verify signal is marked as TRADED
        assert signals_repo.get_user_signal_status(signal.id, test_user.id) == SignalStatus.TRADED

    def test_eod_sync_handles_mixed_positions_and_orders(self, signals_repo, test_user, db_session):
        """Test EOD sync with mix of positions and orders"""
        # Create signals
        signal1 = Signals(
            symbol="RELIANCE", status=SignalStatus.ACTIVE, verdict="buy", ts=ist_now()
        )
        signal2 = Signals(symbol="TCS", status=SignalStatus.ACTIVE, verdict="buy", ts=ist_now())
        db_session.add_all([signal1, signal2])
        db_session.commit()

        # Create position for signal1
        position1 = Positions(
            user_id=test_user.id,
            symbol="RELIANCE",
            quantity=10.0,
            avg_price=2500.0,
            closed_at=None,
        )
        # Create order for signal2
        order2 = Orders(
            user_id=test_user.id,
            symbol="TCS",
            side="buy",
            order_type="limit",
            quantity=5,
            price=3500.0,
            status=OrderStatus.PENDING,
        )
        db_session.add_all([position1, order2])
        db_session.commit()

        # Run EOD sync
        count = signals_repo.sync_traded_status_from_positions_and_orders(user_id=test_user.id)
        assert count == 2

        # Verify both signals are marked as TRADED
        assert signals_repo.get_user_signal_status(signal1.id, test_user.id) == SignalStatus.TRADED
        assert signals_repo.get_user_signal_status(signal2.id, test_user.id) == SignalStatus.TRADED

    def test_eod_sync_idempotent(self, signals_repo, test_user, db_session):
        """Test that EOD sync is idempotent (can run multiple times)"""
        # Create signal
        signal = Signals(
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,
            verdict="buy",
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Create position
        position = Positions(
            user_id=test_user.id,
            symbol="RELIANCE",
            quantity=10.0,
            avg_price=2500.0,
            closed_at=None,
        )
        db_session.add(position)
        db_session.commit()

        # Run EOD sync first time
        count1 = signals_repo.sync_traded_status_from_positions_and_orders(user_id=test_user.id)
        assert count1 == 1

        # Run EOD sync second time (should return 0, already TRADED)
        count2 = signals_repo.sync_traded_status_from_positions_and_orders(user_id=test_user.id)
        assert count2 == 0

        # Verify signal is still TRADED
        assert signals_repo.get_user_signal_status(signal.id, test_user.id) == SignalStatus.TRADED

        # Verify only one UserSignalStatus entry exists
        status_count = (
            db_session.query(UserSignalStatus)
            .filter(
                UserSignalStatus.user_id == test_user.id,
                UserSignalStatus.signal_id == signal.id,
            )
            .count()
        )
        assert status_count == 1
