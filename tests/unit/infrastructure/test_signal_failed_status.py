"""
Unit tests for signal FAILED status implementation

Tests cover:
- Real-time signal status updates when orders fail
- Edge cases (multiple orders, retries, etc.)
- Trading engine filtering
- Signal reactivation
"""

from unittest.mock import patch

import pytest

from src.infrastructure.db.models import Orders, OrderStatus, Signals, SignalStatus, Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.signals_repository import SignalsRepository


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = Users(
        email="test_failed@example.com",
        password_hash="test_hash",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_signal(db_session):
    """Create a test signal"""
    signal = Signals(
        symbol="RELIANCE",
        status=SignalStatus.ACTIVE,
        verdict="buy",
        final_verdict="buy",
        last_close=2500.0,
        ts=ist_now(),
    )
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)
    return signal


@pytest.fixture
def orders_repo(db_session):
    """Create OrdersRepository instance"""
    return OrdersRepository(db_session)


@pytest.fixture
def signals_repo(db_session, test_user):
    """Create SignalsRepository instance"""
    return SignalsRepository(db_session, user_id=test_user.id)


class TestOrderFailedMarksSignalAsFailed:
    """Test that order failures mark signals as FAILED"""

    def test_mark_failed_buy_order_marks_signal_as_failed(
        self, db_session, test_user, test_signal, orders_repo, signals_repo
    ):
        """Test that marking a buy order as FAILED marks the signal as FAILED"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Create buy order
        order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        # Mark order as FAILED
        orders_repo.mark_failed(order, failure_reason="Insufficient funds")

        # Verify signal is marked as FAILED
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.FAILED

    def test_mark_rejected_buy_order_marks_signal_as_failed(
        self, db_session, test_user, test_signal, orders_repo, signals_repo
    ):
        """Test that marking a buy order as REJECTED marks the signal as FAILED"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Create buy order
        order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        # Mark order as REJECTED
        orders_repo.mark_rejected(order, rejection_reason="Broker rejected")

        # Verify signal is marked as FAILED
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.FAILED

    def test_mark_cancelled_buy_order_marks_signal_as_failed(
        self, db_session, test_user, test_signal, orders_repo, signals_repo
    ):
        """Test that cancelling a buy order marks the signal as FAILED"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Create buy order
        order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        # Cancel order
        orders_repo.mark_cancelled(order, cancelled_reason="User cancelled")

        # Verify signal is marked as FAILED
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.FAILED

    def test_sell_order_failure_does_not_mark_signal_as_failed(
        self, db_session, test_user, test_signal, orders_repo, signals_repo
    ):
        """Test that sell order failures do NOT mark signals as FAILED"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Create sell order
        order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="sell",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2600.0,
            placed_at=ist_now(),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        # Mark sell order as FAILED
        orders_repo.mark_failed(order, failure_reason="Order failed")

        # Verify signal is still TRADED (not FAILED)
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.TRADED  # Should remain TRADED

    def test_order_failure_without_traded_signal_does_not_mark_as_failed(
        self, db_session, test_user, test_signal, orders_repo, signals_repo
    ):
        """Test that order failure doesn't mark signal as FAILED if signal is not TRADED"""
        # Signal is ACTIVE (not TRADED)
        # Create buy order
        order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        # Mark order as FAILED
        orders_repo.mark_failed(order, failure_reason="Order failed")

        # Verify signal is still ACTIVE (no user status override)
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status is None  # No user status override
        db_session.refresh(test_signal)
        assert test_signal.status == SignalStatus.ACTIVE


class TestMultipleOrdersEdgeCase:
    """Test edge case: Multiple orders for same symbol"""

    def test_one_order_fails_one_succeeds_signal_stays_traded(
        self, db_session, test_user, test_signal, orders_repo, signals_repo
    ):
        """Test that if one order fails but another succeeds, signal stays TRADED"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Create first buy order
        order1 = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order1)
        db_session.commit()
        db_session.refresh(order1)

        # Create second buy order (still PENDING)
        order2 = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=5,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order2)
        db_session.commit()
        db_session.refresh(order2)

        # Mark first order as FAILED
        orders_repo.mark_failed(order1, failure_reason="Order failed")

        # Verify signal is still TRADED (because order2 is still PENDING)
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.TRADED

    def test_one_order_fails_one_ongoing_signal_stays_traded(
        self, db_session, test_user, test_signal, orders_repo, signals_repo
    ):
        """Test that if one order fails but another is ONGOING, signal stays TRADED"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Create first buy order
        order1 = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order1)
        db_session.commit()
        db_session.refresh(order1)

        # Create second buy order (ONGOING)
        order2 = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.ONGOING,
            quantity=5,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order2)
        db_session.commit()
        db_session.refresh(order2)

        # Mark first order as FAILED
        orders_repo.mark_failed(order1, failure_reason="Order failed")

        # Verify signal is still TRADED (because order2 is ONGOING)
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.TRADED

    def test_all_orders_fail_signal_marked_as_failed(
        self, db_session, test_user, test_signal, orders_repo, signals_repo
    ):
        """Test that if all orders fail, signal is marked as FAILED"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Create first buy order
        order1 = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order1)
        db_session.commit()
        db_session.refresh(order1)

        # Create second buy order
        order2 = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=5,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order2)
        db_session.commit()
        db_session.refresh(order2)

        # Mark both orders as FAILED
        orders_repo.mark_failed(order1, failure_reason="Order failed")
        orders_repo.mark_failed(order2, failure_reason="Order failed")

        # Verify signal is marked as FAILED
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.FAILED


class TestOrderRetryEdgeCase:
    """Test edge case: Order retry after failure"""

    def test_order_retry_after_failure_updates_signal_to_traded(
        self, db_session, test_user, test_signal, orders_repo, signals_repo
    ):
        """Test that retrying an order after failure updates signal from FAILED to TRADED"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Create and fail first order
        order1 = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order1)
        db_session.commit()
        db_session.refresh(order1)

        # Mark order as FAILED (signal becomes FAILED)
        orders_repo.mark_failed(order1, failure_reason="Order failed")
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.FAILED

        # Create new order (retry)
        order2 = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order2)
        db_session.commit()
        db_session.refresh(order2)

        # Mark new order as ONGOING (success)
        orders_repo.mark_executed(order2, execution_price=2500.0, execution_qty=10)

        # Mark signal as TRADED again (simulating successful order placement)
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Verify signal is now TRADED (not FAILED)
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.TRADED


class TestSignalNotFoundEdgeCase:
    """Test edge case: Signal not found"""

    def test_order_failure_without_signal_does_not_error(self, db_session, test_user, orders_repo):
        """Test that order failure doesn't error if signal doesn't exist"""
        # Create order for symbol that has no signal
        order = Orders(
            user_id=test_user.id,
            symbol="NONEXISTENT",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=100.0,
            placed_at=ist_now(),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        # Mark order as FAILED - should not raise error
        try:
            orders_repo.mark_failed(order, failure_reason="Order failed")
        except Exception:
            pytest.fail("mark_failed() should not raise error when signal not found")

        # Verify order was updated
        db_session.refresh(order)
        assert order.status == OrderStatus.FAILED


class TestTransactionFailureEdgeCase:
    """Test edge case: Transaction failure"""

    def test_signal_marking_failure_does_not_prevent_order_update(
        self, db_session, test_user, test_signal, orders_repo, signals_repo
    ):
        """Test that if signal marking fails, order update still succeeds"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Create buy order
        order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        # Mock signal marking to fail
        with patch.object(signals_repo, "mark_as_failed", side_effect=Exception("DB error")):
            # Mark order as FAILED - should still succeed
            orders_repo.mark_failed(order, failure_reason="Order failed")

        # Verify order was updated despite signal marking failure
        db_session.refresh(order)
        assert order.status == OrderStatus.FAILED


class TestTradingEngineFiltering:
    """Test that FAILED signals are excluded from trading recommendations"""

    def test_failed_signals_have_correct_status(
        self, db_session, test_user, test_signal, signals_repo
    ):
        """Test that FAILED signals have correct status for filtering"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Mark signal as FAILED
        signals_repo.mark_as_failed(test_signal.id, test_user.id)

        # Get signals with user status
        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100
        )

        # Find our signal
        signal_found = False
        for sig, status in signals_with_status:
            if sig.id == test_signal.id:
                signal_found = True
                assert status == SignalStatus.FAILED
                break

        assert signal_found

        # Verify user status is FAILED
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.FAILED

    def test_failed_signals_excluded_from_active_recommendations(
        self, db_session, test_user, test_signal, signals_repo
    ):
        """Test that FAILED signals are excluded from active recommendations"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Mark signal as FAILED
        signals_repo.mark_as_failed(test_signal.id, test_user.id)

        # Get signals with user status (this checks user-specific overrides)
        signals_with_status = signals_repo.get_signals_with_user_status(
            user_id=test_user.id, limit=100
        )

        # Find our signal and verify it has FAILED status
        signal_found = False
        for sig, status in signals_with_status:
            if sig.id == test_signal.id:
                signal_found = True
                # Signal should have FAILED status, not ACTIVE
                assert status == SignalStatus.FAILED
                # This means it would be excluded from trading recommendations
                break

        assert signal_found, "Signal should be found in results"


class TestSignalReactivation:
    """Test that FAILED signals can be reactivated"""

    def test_failed_signal_can_be_reactivated(
        self, db_session, test_user, test_signal, signals_repo
    ):
        """Test that FAILED signals can be reactivated"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Mark signal as FAILED
        signals_repo.mark_as_failed(test_signal.id, test_user.id)

        # Verify signal is FAILED
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.FAILED

        # Reactivate signal
        success = signals_repo.mark_as_active("RELIANCE", user_id=test_user.id)

        # Verify reactivation succeeded
        assert success is True

        # Verify user status override is removed
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status is None  # No user override, reverts to base status

        # Verify base signal is still ACTIVE
        db_session.refresh(test_signal)
        assert test_signal.status == SignalStatus.ACTIVE


class TestSymbolVariations:
    """Test that symbol variations (with -EQ, -BE suffixes) are handled correctly"""

    def test_order_with_eq_suffix_matches_signal(
        self, db_session, test_user, test_signal, orders_repo, signals_repo
    ):
        """Test that order with -EQ suffix matches signal without suffix"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Create order with -EQ suffix
        order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        # Mark order as FAILED
        orders_repo.mark_failed(order, failure_reason="Order failed")

        # Verify signal is marked as FAILED (symbol matching should work)
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.FAILED

    def test_order_with_be_suffix_matches_signal(
        self, db_session, test_user, test_signal, orders_repo, signals_repo
    ):
        """Test that order with -BE suffix matches signal without suffix"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Create order with -BE suffix
        order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE-BE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        # Mark order as FAILED
        orders_repo.mark_failed(order, failure_reason="Order failed")

        # Verify signal is marked as FAILED (symbol matching should work)
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.FAILED


class TestRejectedSignalStatus:
    """Test that REJECTED signals are handled correctly"""

    def test_order_failure_does_not_affect_rejected_signal(
        self, db_session, test_user, test_signal, orders_repo, signals_repo
    ):
        """Test that order failure doesn't change REJECTED signal status"""
        # Mark signal as REJECTED (not TRADED)
        signals_repo.mark_as_rejected("RELIANCE", user_id=test_user.id)

        # Create buy order
        order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        # Mark order as FAILED
        orders_repo.mark_failed(order, failure_reason="Order failed")

        # Verify signal is still REJECTED (not changed to FAILED)
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.REJECTED  # Should remain REJECTED


class TestAlreadyFailedSignal:
    """Test that already FAILED signals are handled correctly"""

    def test_order_failure_on_already_failed_signal(
        self, db_session, test_user, test_signal, orders_repo, signals_repo
    ):
        """Test that order failure on already FAILED signal doesn't cause issues"""
        # Mark signal as TRADED first
        signals_repo.mark_as_traded("RELIANCE", user_id=test_user.id)

        # Mark signal as FAILED
        signals_repo.mark_as_failed(test_signal.id, test_user.id)

        # Create new buy order
        order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="MARKET",
            status=OrderStatus.PENDING,
            quantity=10,
            price=2500.0,
            placed_at=ist_now(),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        # Mark order as FAILED
        orders_repo.mark_failed(order, failure_reason="Order failed")

        # Verify signal is still FAILED (shouldn't cause issues)
        user_status = signals_repo.get_user_signal_status(test_signal.id, test_user.id)
        assert user_status == SignalStatus.FAILED
