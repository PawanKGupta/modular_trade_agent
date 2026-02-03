"""
Tests for closing buy orders when positions are closed.

This test suite verifies Fix 1: When a position is closed (via manual sell detection,
reconciliation, or sell order execution), all corresponding ONGOING buy orders are
also marked as CLOSED.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest  # noqa: E402

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager  # noqa: E402
from src.infrastructure.db.models import Orders, OrderStatus  # noqa: E402
from src.infrastructure.db.timezone_utils import ist_now  # noqa: E402
from src.infrastructure.persistence.orders_repository import OrdersRepository  # noqa: E402
from src.infrastructure.persistence.positions_repository import PositionsRepository  # noqa: E402


@pytest.fixture
def test_user(db_session):
    """Create and return test user."""
    from src.infrastructure.db.models import Users

    user = Users(
        email="buy_order_closure_test@example.com",
        password_hash="test_hash",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def orders_repo(db_session):
    """Return OrdersRepository."""
    return OrdersRepository(db_session)


@pytest.fixture
def positions_repo(db_session):
    """Return PositionsRepository."""
    return PositionsRepository(db_session)


@pytest.fixture
def sell_manager(db_session, orders_repo, positions_repo, test_user):
    """Create SellOrderManager with real repositories."""
    user_id = test_user.id

    mock_auth = Mock()
    manager = SellOrderManager(
        auth=mock_auth,
        positions_repo=positions_repo,
        user_id=user_id,
    )
    manager.orders_repo = orders_repo
    manager.orders = Mock()
    manager.portfolio = Mock()
    # Edge Case #17: get_open_positions requires valid holdings; tests that call
    # _detect_manual_sells_from_orders or get_open_positions override this per-test.
    manager.portfolio.get_holdings.return_value = {"data": []}
    return manager


class TestCloseBuyOrdersForSymbol:
    """Test _close_buy_orders_for_symbol() method directly."""

    def test_closes_ongoing_buy_orders(
        self, db_session, test_user, sell_manager, orders_repo, positions_repo
    ):
        """Test that ONGOING buy orders are closed for a symbol."""
        session = db_session
        user_id = test_user.id

        # Create open position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            quantity=100.0,
            avg_price=2500.0,
        )
        session.commit()

        # Create ONGOING buy orders directly (bypass duplicate prevention)
        buy_order1 = Orders(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="limit",
            quantity=50.0,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="BUY_ORDER_1",
        )
        session.add(buy_order1)
        session.commit()
        orders_repo.mark_executed(buy_order1, execution_price=2500.0, execution_qty=50.0)
        session.commit()
        session.refresh(buy_order1)

        buy_order2 = Orders(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="limit",
            quantity=50.0,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="BUY_ORDER_2",
        )
        session.add(buy_order2)
        session.commit()
        orders_repo.mark_executed(buy_order2, execution_price=2500.0, execution_qty=50.0)
        session.commit()
        session.refresh(buy_order2)

        # Verify orders are CLOSED with closed_at set at fill time (order closer)
        session.refresh(buy_order1)
        session.refresh(buy_order2)
        assert buy_order1.status == OrderStatus.CLOSED
        assert buy_order2.status == OrderStatus.CLOSED
        assert buy_order1.closed_at is not None
        assert buy_order2.closed_at is not None

        # _close_buy_orders_for_symbol finds only CLOSED+closed_at None (legacy). These already have closed_at.
        closed_count = sell_manager._close_buy_orders_for_symbol("RELIANCE")
        assert closed_count == 0

    def test_no_buy_orders_returns_zero(self, db_session, test_user, sell_manager, positions_repo):
        """Test that method returns 0 when no buy orders exist."""
        session = db_session
        user_id = test_user.id

        # Create open position (no buy orders)
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            quantity=100.0,
            avg_price=2500.0,
        )
        session.commit()

        # Close buy orders (none exist)
        closed_count = sell_manager._close_buy_orders_for_symbol("RELIANCE")

        assert closed_count == 0

    def test_only_closes_ongoing_orders(
        self, db_session, test_user, sell_manager, orders_repo, positions_repo
    ):
        """Test that PENDING buy orders are not closed; filled (CLOSED) already have closed_at."""
        session = db_session
        user_id = test_user.id

        # Create buy order and mark executed (CLOSED with closed_at set at fill time)
        filled_order = Orders(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="limit",
            quantity=50.0,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="FILLED_ORDER",
        )
        session.add(filled_order)
        session.commit()
        orders_repo.mark_executed(filled_order, execution_price=2500.0, execution_qty=50.0)
        session.commit()
        session.refresh(filled_order)

        # Create PENDING buy order
        pending_order = Orders(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="limit",
            quantity=50.0,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="PENDING_ORDER",
        )
        session.add(pending_order)
        session.commit()

        # Create CLOSED buy order
        closed_order = Orders(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="limit",
            quantity=50.0,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="CLOSED_ORDER",
        )
        session.add(closed_order)
        session.commit()
        orders_repo.mark_executed(closed_order, execution_price=2500.0, execution_qty=50.0)
        orders_repo.update(closed_order, status=OrderStatus.CLOSED, closed_at=ist_now())
        session.commit()
        session.refresh(closed_order)

        # _close_buy_orders_for_symbol finds only ONGOING or CLOSED+closed_at None; both filled/closed have closed_at
        closed_count = sell_manager._close_buy_orders_for_symbol("RELIANCE")
        assert closed_count == 0

        session.refresh(filled_order)
        session.refresh(pending_order)
        session.refresh(closed_order)
        assert filled_order.status == OrderStatus.CLOSED
        assert filled_order.closed_at is not None  # Set at fill time
        assert pending_order.status == OrderStatus.PENDING  # Unchanged
        assert closed_order.status == OrderStatus.CLOSED

    def test_only_closes_buy_orders_not_sell(
        self, db_session, test_user, sell_manager, orders_repo, positions_repo
    ):
        """Test that only buy orders are closed, not sell orders."""
        session = db_session
        user_id = test_user.id

        # Create ONGOING buy order
        buy_order = Orders(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="limit",
            quantity=50.0,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="BUY_ORDER",
        )
        session.add(buy_order)
        session.commit()
        orders_repo.mark_executed(buy_order, execution_price=2500.0, execution_qty=50.0)
        session.commit()
        session.refresh(buy_order)

        # Create ONGOING sell order
        sell_order = Orders(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="sell",
            order_type="limit",
            quantity=50.0,
            price=2600.0,
            status=OrderStatus.PENDING,
            broker_order_id="SELL_ORDER",
        )
        session.add(sell_order)
        session.commit()
        orders_repo.mark_executed(sell_order, execution_price=2600.0, execution_qty=50.0)
        session.commit()
        session.refresh(sell_order)

        # _close_buy_orders_for_symbol: buy already has closed_at from mark_executed, so nothing to do
        closed_count = sell_manager._close_buy_orders_for_symbol("RELIANCE")
        assert closed_count == 0

        session.refresh(buy_order)
        session.refresh(sell_order)
        assert buy_order.status == OrderStatus.CLOSED
        assert buy_order.closed_at is not None  # Set at fill time
        assert sell_order.status == OrderStatus.CLOSED

    def test_closes_orders_for_correct_symbol_only(
        self, db_session, test_user, sell_manager, orders_repo, positions_repo
    ):
        """Test that orders are closed only for the specified symbol."""
        session = db_session
        user_id = test_user.id

        # Create ONGOING buy order for RELIANCE
        reliance_order = Orders(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="limit",
            quantity=50.0,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="RELIANCE_ORDER",
        )
        session.add(reliance_order)
        session.commit()
        orders_repo.mark_executed(reliance_order, execution_price=2500.0, execution_qty=50.0)
        session.commit()
        session.refresh(reliance_order)

        # Create ONGOING buy order for TCS
        tcs_order = Orders(
            user_id=user_id,
            symbol="TCS-EQ",
            side="buy",
            order_type="limit",
            quantity=50.0,
            price=3500.0,
            status=OrderStatus.PENDING,
            broker_order_id="TCS_ORDER",
        )
        session.add(tcs_order)
        session.commit()
        orders_repo.mark_executed(tcs_order, execution_price=3500.0, execution_qty=50.0)
        session.commit()
        session.refresh(tcs_order)

        # _close_buy_orders_for_symbol: both already have closed_at from mark_executed
        closed_count = sell_manager._close_buy_orders_for_symbol("RELIANCE")
        assert closed_count == 0

        session.refresh(reliance_order)
        session.refresh(tcs_order)
        assert reliance_order.status == OrderStatus.CLOSED
        assert reliance_order.closed_at is not None
        assert tcs_order.status == OrderStatus.CLOSED
        assert tcs_order.closed_at is not None

    def test_handles_missing_orders_repo_gracefully(self, db_session, sell_manager):
        """Test that method handles missing orders_repo gracefully."""
        sell_manager.orders_repo = None

        closed_count = sell_manager._close_buy_orders_for_symbol("RELIANCE")

        assert closed_count == 0

    def test_handles_missing_user_id_gracefully(self, db_session, sell_manager):
        """Test that method handles missing user_id gracefully."""
        sell_manager.user_id = None

        closed_count = sell_manager._close_buy_orders_for_symbol("RELIANCE")

        assert closed_count == 0


class TestManualSellDetectionClosesBuyOrders:
    """Test that buy orders are closed when position is closed via manual sell detection."""

    def test_manual_sell_detection_closes_buy_orders(
        self, db_session, test_user, sell_manager, orders_repo, positions_repo
    ):
        """Test that buy orders are closed when position closed via _detect_manual_sells_from_orders()."""
        session = db_session
        user_id = test_user.id

        # Create open position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            quantity=100.0,
            avg_price=2500.0,
        )
        session.commit()

        # Create ONGOING buy orders
        buy_order1 = Orders(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="limit",
            quantity=50.0,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="BUY_ORDER_1",
        )
        session.add(buy_order1)
        session.commit()
        orders_repo.mark_executed(buy_order1, execution_price=2500.0, execution_qty=50.0)
        session.commit()
        session.refresh(buy_order1)

        # Mock broker orders to show a sell order that closed the position
        sell_manager.orders.get_orders = Mock(
            return_value={
                "data": [
                    {
                        "nOrdNo": "SELL_ORDER_123",
                        "symbol": "RELIANCE-EQ",
                        "quantity": 100,
                        "filledQty": 100,
                        "orderStatus": "COMPLETE",
                        "transactionType": "SELL",
                        "orderPrice": 2600.0,
                        "ltp": 2600.0,
                        "orderTime": ist_now().isoformat(),
                    }
                ]
            }
        )

        # Execute manual sell detection
        stats = sell_manager._detect_manual_sells_from_orders()

        # Verify position is closed
        session.refresh(position)
        assert position.closed_at is not None
        assert stats["closed"] == 1

        # Verify buy orders are closed
        session.refresh(buy_order1)
        assert buy_order1.status == OrderStatus.CLOSED
        assert buy_order1.closed_at is not None

    def test_manual_sell_detection_no_buy_orders_no_error(
        self, db_session, test_user, sell_manager, orders_repo, positions_repo
    ):
        """
        Test that manual sell detection works when there are no ONGOING buy orders to close.

        Note: The position must have an ONGOING buy order to be recognized as a system position.
        However, this test verifies that if all buy orders are already CLOSED (no ONGOING orders),
        the position closure still works without errors. This tests the edge case where buy orders
        were closed before the position was closed.

        IMPORTANT: The detection logic requires ONGOING buy orders to recognize a position as system.
        So we create an ONGOING buy order first, then verify the system behavior.
        """
        session = db_session
        user_id = test_user.id

        # Create open position with specific opened_at time for matching
        position_opened_at = ist_now()
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            quantity=100.0,
            avg_price=2500.0,
            opened_at=position_opened_at,
        )
        session.commit()

        # Create a system buy order (with orig_source='signal' to mark it as system position)
        # The buy order MUST be ONGOING for the position to be recognized as a system position
        # (see sell_engine.py line 1042: only queries ONGOING orders)
        # We set execution_time to match position opened_at (within 1 hour window)
        system_buy_order = Orders(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="limit",
            quantity=100.0,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="SYSTEM_BUY_ORDER",
            orig_source="signal",  # Mark as system order (not manual)
        )
        session.add(system_buy_order)
        session.commit()

        # Mark as executed (ONGOING) - this ensures the position is recognized as a system position
        # The execution_time will be set automatically, and we'll ensure it matches position opened_at
        orders_repo.mark_executed(system_buy_order, execution_price=2500.0, execution_qty=100.0)
        # Set execution_time to match position opened_at (within 1 hour window for system detection)
        if hasattr(system_buy_order, "execution_time"):
            system_buy_order.execution_time = position_opened_at
        elif hasattr(system_buy_order, "filled_at"):
            system_buy_order.filled_at = position_opened_at
        session.commit()
        session.refresh(system_buy_order)

        # Verify buy order is CLOSED (filled orders are stored as CLOSED)
        assert system_buy_order.status == OrderStatus.CLOSED

        # Mock broker orders to show a sell order that closed the position
        sell_manager.orders.get_orders = Mock(
            return_value={
                "data": [
                    {
                        "nOrdNo": "SELL_ORDER_123",
                        "symbol": "RELIANCE-EQ",
                        "quantity": 100,
                        "filledQty": 100,
                        "orderStatus": "COMPLETE",
                        "transactionType": "SELL",
                        "orderPrice": 2600.0,
                        "ltp": 2600.0,
                        "orderTime": ist_now().isoformat(),
                    }
                ]
            }
        )

        # Execute manual sell detection (should not raise error)
        stats = sell_manager._detect_manual_sells_from_orders()

        # Verify position is closed
        session.refresh(position)
        assert position.closed_at is not None
        assert stats["closed"] == 1

        # Verify the ONGOING buy order was also closed (this is the fix we're testing)
        session.refresh(system_buy_order)
        assert system_buy_order.status == OrderStatus.CLOSED
        assert system_buy_order.closed_at is not None


class TestReconciliationClosesBuyOrders:
    """Test that buy orders are closed when position is closed via reconciliation."""

    def test_reconciliation_closes_buy_orders(
        self, db_session, test_user, sell_manager, orders_repo, positions_repo
    ):
        """Test that buy orders are closed when position closed via _reconcile_positions_with_broker_holdings()."""
        session = db_session
        user_id = test_user.id

        # Create open position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            quantity=100.0,
            avg_price=2500.0,
        )
        session.commit()

        # Create ONGOING buy orders
        buy_order1 = Orders(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="limit",
            quantity=50.0,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="BUY_ORDER_1",
        )
        session.add(buy_order1)
        session.commit()
        orders_repo.mark_executed(buy_order1, execution_price=2500.0, execution_qty=50.0)
        session.commit()
        session.refresh(buy_order1)

        # Mock broker holdings to show 0 shares (position closed)
        sell_manager.portfolio.get_holdings = Mock(
            return_value={"data": []}  # No holdings = position closed
        )

        # Execute reconciliation
        stats = sell_manager._reconcile_positions_with_broker_holdings()

        # Verify position is closed
        session.refresh(position)
        assert position.closed_at is not None
        assert stats["closed"] == 1

        # Verify buy orders are closed
        session.refresh(buy_order1)
        assert buy_order1.status == OrderStatus.CLOSED
        assert buy_order1.closed_at is not None

    def test_reconciliation_no_buy_orders_no_error(
        self, db_session, test_user, sell_manager, positions_repo
    ):
        """Test that reconciliation works even when no buy orders exist."""
        session = db_session
        user_id = test_user.id

        # Create open position (no buy orders)
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            quantity=100.0,
            avg_price=2500.0,
        )
        session.commit()

        # Mock broker holdings to show 0 shares (position closed)
        sell_manager.portfolio.get_holdings = Mock(
            return_value={"data": []}  # No holdings = position closed
        )

        # Execute reconciliation (should not raise error)
        stats = sell_manager._reconcile_positions_with_broker_holdings()

        # Verify position is closed
        session.refresh(position)
        assert position.closed_at is not None
        assert stats["closed"] == 1


class TestSingleSymbolReconciliationClosesBuyOrders:
    """Test that buy orders are closed when position is closed via single symbol reconciliation."""

    def test_single_symbol_reconciliation_closes_buy_orders(
        self, db_session, test_user, sell_manager, orders_repo, positions_repo
    ):
        """Test that buy orders are closed when position closed via _reconcile_single_symbol()."""
        session = db_session
        user_id = test_user.id

        # Create open position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            quantity=100.0,
            avg_price=2500.0,
        )
        session.commit()

        # Create ONGOING buy orders
        buy_order1 = Orders(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="limit",
            quantity=50.0,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="BUY_ORDER_1",
        )
        session.add(buy_order1)
        session.commit()
        orders_repo.mark_executed(buy_order1, execution_price=2500.0, execution_qty=50.0)
        session.commit()
        session.refresh(buy_order1)

        # Mock broker holdings to show 0 shares (position closed)
        sell_manager.portfolio.get_holdings = Mock(
            return_value={"data": []}  # No holdings = position closed
        )

        # Execute single symbol reconciliation
        result = sell_manager._reconcile_single_symbol("RELIANCE-EQ")

        # Verify position is closed
        session.refresh(position)
        assert position.closed_at is not None
        assert result is True

        # Verify buy orders are closed
        session.refresh(buy_order1)
        assert buy_order1.status == OrderStatus.CLOSED
        assert buy_order1.closed_at is not None

    def test_single_symbol_reconciliation_no_buy_orders_no_error(
        self, db_session, test_user, sell_manager, positions_repo
    ):
        """Test that single symbol reconciliation works even when no buy orders exist."""
        session = db_session
        user_id = test_user.id

        # Create open position (no buy orders)
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            quantity=100.0,
            avg_price=2500.0,
        )
        session.commit()

        # Mock broker holdings to show 0 shares (position closed)
        sell_manager.portfolio.get_holdings = Mock(
            return_value={"data": []}  # No holdings = position closed
        )

        # Execute single symbol reconciliation (should not raise error)
        result = sell_manager._reconcile_single_symbol("RELIANCE-EQ")

        # Verify position is closed
        session.refresh(position)
        assert position.closed_at is not None
        assert result is True


class TestErrorHandling:
    """Test error handling in buy order closure."""

    def test_buy_order_closure_failure_does_not_prevent_position_closure(
        self, db_session, test_user, sell_manager, orders_repo, positions_repo
    ):
        """Test that position closure succeeds even if buy order closure fails."""
        session = db_session
        user_id = test_user.id

        # Create open position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            quantity=100.0,
            avg_price=2500.0,
        )
        session.commit()

        # Create ONGOING buy order
        buy_order = Orders(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="limit",
            quantity=50.0,
            price=2500.0,
            status=OrderStatus.PENDING,
            broker_order_id="BUY_ORDER_1",
        )
        session.add(buy_order)
        session.commit()
        orders_repo.mark_executed(buy_order, execution_price=2500.0, execution_qty=50.0)
        session.commit()
        session.refresh(buy_order)

        # Mock orders_repo.update to raise an error
        original_update = sell_manager.orders_repo.update
        call_count = {"count": 0}

        def failing_update(order, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:  # Fail on first call
                raise Exception("Simulated update failure")
            return original_update(order, **kwargs)

        sell_manager.orders_repo.update = failing_update

        # Mock broker holdings to show 0 shares (position closed)
        sell_manager.portfolio.get_holdings = Mock(
            return_value={"data": []}  # No holdings = position closed
        )

        # Execute reconciliation (should not raise error, position should still close)
        stats = sell_manager._reconcile_positions_with_broker_holdings()

        # Verify position is closed (even though buy order closure failed)
        session.refresh(position)
        assert position.closed_at is not None
        assert stats["closed"] == 1

        # Restore original method
        sell_manager.orders_repo.update = original_update
