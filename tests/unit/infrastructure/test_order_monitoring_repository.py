"""
Unit tests for order monitoring repository methods.

Tests for:
1. Order status transitions (failed, rejected, cancelled, executed)
2. Failure tracking (failure_reason, retry_count, timestamps)
3. Execution tracking (execution_price, execution_qty, execution_time)
4. Status check updates
5. Query methods (get_pending_amo_orders, get_failed_orders)
"""

from datetime import datetime

import pytest

from src.infrastructure.db.models import OrderStatus, UserRole, Users
from src.infrastructure.persistence.orders_repository import OrdersRepository


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing"""
    user = Users(
        email="test@example.com",
        name="Test User",
        password_hash="hashed_password",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestOrderMonitoringRepository:
    """Test order monitoring repository methods"""

    def test_mark_failed_with_retry_pending(self, db_session, sample_user):
        """Test marking order as failed with retry_pending status"""
        repo = OrdersRepository(db_session)
        order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        updated = repo.mark_failed(
            order,
            failure_reason="insufficient_balance",
            retry_pending=True,
        )

        assert updated.status == OrderStatus.RETRY_PENDING
        assert updated.failure_reason == "insufficient_balance"
        assert updated.first_failed_at is not None
        assert updated.last_retry_attempt is not None
        assert updated.retry_count == 1

    def test_mark_failed_without_retry(self, db_session, sample_user):
        """Test marking order as failed without retry"""
        repo = OrdersRepository(db_session)
        order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        updated = repo.mark_failed(
            order,
            failure_reason="broker_api_error",
            retry_pending=False,
        )

        assert updated.status == OrderStatus.FAILED
        assert updated.failure_reason == "broker_api_error"
        assert updated.first_failed_at is not None
        assert updated.retry_count == 0

    def test_mark_failed_increments_retry_count(self, db_session, sample_user):
        """Test that mark_failed increments retry_count on subsequent calls"""
        repo = OrdersRepository(db_session)
        order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        # First failure
        order = repo.mark_failed(order, "insufficient_balance", retry_pending=True)
        assert order.retry_count == 1

        # Second retry attempt
        order = repo.mark_failed(order, "insufficient_balance", retry_pending=True)
        assert order.retry_count == 2
        assert order.first_failed_at is not None  # Should preserve original failure time

    def test_mark_rejected(self, db_session, sample_user):
        """Test marking order as rejected"""
        repo = OrdersRepository(db_session)
        order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        updated = repo.mark_rejected(order, "Symbol not tradable")

        assert updated.status == OrderStatus.REJECTED
        assert updated.rejection_reason == "Symbol not tradable"
        assert updated.last_status_check is not None

    def test_mark_cancelled(self, db_session, sample_user):
        """Test marking order as cancelled"""
        repo = OrdersRepository(db_session)
        order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        updated = repo.mark_cancelled(order, "Manual cancellation")

        assert updated.status == OrderStatus.CLOSED
        assert updated.cancelled_reason == "Manual cancellation"
        assert updated.closed_at is not None
        assert updated.last_status_check is not None

    def test_mark_cancelled_without_reason(self, db_session, sample_user):
        """Test marking order as cancelled without reason"""
        repo = OrdersRepository(db_session)
        order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        updated = repo.mark_cancelled(order)

        assert updated.status == OrderStatus.CLOSED
        assert updated.cancelled_reason == "Cancelled"  # Default reason
        assert updated.closed_at is not None

    def test_mark_executed(self, db_session, sample_user):
        """Test marking order as executed"""
        repo = OrdersRepository(db_session)
        order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        updated = repo.mark_executed(
            order,
            execution_price=2450.50,
            execution_qty=10.0,
        )

        assert updated.status == OrderStatus.ONGOING
        assert updated.execution_price == 2450.50
        assert updated.execution_qty == 10.0
        assert updated.execution_time is not None
        assert updated.filled_at is not None
        assert updated.last_status_check is not None

    def test_mark_executed_with_partial_qty(self, db_session, sample_user):
        """Test marking order as executed with partial quantity"""
        repo = OrdersRepository(db_session)
        order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        updated = repo.mark_executed(
            order,
            execution_price=2450.50,
            execution_qty=5.0,  # Partial fill
        )

        assert updated.execution_price == 2450.50
        assert updated.execution_qty == 5.0
        assert updated.quantity == 10.0  # Original quantity preserved

    def test_mark_executed_defaults_qty_to_order_quantity(self, db_session, sample_user):
        """Test that mark_executed defaults execution_qty to order quantity"""
        repo = OrdersRepository(db_session)
        order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        updated = repo.mark_executed(order, execution_price=2450.50)

        assert updated.execution_qty == 10.0  # Should default to order quantity

    def test_update_status_check(self, db_session, sample_user):
        """Test updating last status check timestamp"""
        repo = OrdersRepository(db_session)
        order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        initial_check = order.last_status_check
        updated = repo.update_status_check(order)

        assert updated.last_status_check is not None
        assert updated.last_status_check != initial_check

    def test_get_pending_amo_orders(self, db_session, sample_user):
        """Test getting pending AMO orders"""
        repo = OrdersRepository(db_session)

        # Create orders with different statuses
        amo_order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )
        pending_order = repo.create_amo(
            user_id=sample_user.id,
            symbol="TCS",
            side="buy",
            order_type="market",
            quantity=5.0,
            price=None,
        )
        repo.update(pending_order, status=OrderStatus.PENDING_EXECUTION)

        # Create a closed order (should not be included)
        closed_order = repo.create_amo(
            user_id=sample_user.id,
            symbol="INFY",
            side="buy",
            order_type="market",
            quantity=3.0,
            price=None,
        )
        repo.cancel(closed_order)

        pending_orders = repo.get_pending_amo_orders(sample_user.id)

        assert len(pending_orders) == 2
        symbols = {o.symbol for o in pending_orders}
        assert "RELIANCE" in symbols
        assert "TCS" in symbols
        assert "INFY" not in symbols

    def test_get_failed_orders(self, db_session, sample_user):
        """Test getting failed orders"""
        repo = OrdersRepository(db_session)

        # Create failed order
        failed_order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )
        repo.mark_failed(failed_order, "insufficient_balance", retry_pending=False)

        # Create retry pending order
        retry_order = repo.create_amo(
            user_id=sample_user.id,
            symbol="TCS",
            side="buy",
            order_type="market",
            quantity=5.0,
            price=None,
        )
        repo.mark_failed(retry_order, "insufficient_balance", retry_pending=True)

        # Create successful order (should not be included)
        success_order = repo.create_amo(
            user_id=sample_user.id,
            symbol="INFY",
            side="buy",
            order_type="market",
            quantity=3.0,
            price=None,
        )
        repo.mark_executed(success_order, execution_price=1500.0)

        failed_orders = repo.get_failed_orders(sample_user.id)

        assert len(failed_orders) == 2
        symbols = {o.symbol for o in failed_orders}
        assert "RELIANCE" in symbols
        assert "TCS" in symbols
        assert "INFY" not in symbols

    def test_list_includes_new_fields(self, db_session, sample_user):
        """Test that list() method includes new monitoring fields"""
        repo = OrdersRepository(db_session)
        order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        # Update with monitoring fields
        repo.mark_failed(order, "test_reason", retry_pending=True)
        repo.update(order, rejection_reason="test_rejection")

        # Retrieve via list
        orders = repo.list(sample_user.id)
        retrieved = next(o for o in orders if o.id == order.id)

        assert retrieved.failure_reason == "test_reason"
        assert retrieved.rejection_reason == "test_rejection"
        assert retrieved.retry_count == 1
        assert retrieved.first_failed_at is not None

    def test_status_transitions_work_correctly(self, db_session, sample_user):
        """Test that status transitions work correctly through the lifecycle"""
        repo = OrdersRepository(db_session)
        order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        # AMO -> Failed -> Retry Pending -> Executed
        assert order.status == OrderStatus.AMO

        order = repo.mark_failed(order, "insufficient_balance", retry_pending=False)
        assert order.status == OrderStatus.FAILED

        order = repo.mark_failed(order, "insufficient_balance", retry_pending=True)
        assert order.status == OrderStatus.RETRY_PENDING

        order = repo.mark_executed(order, execution_price=2450.50)
        assert order.status == OrderStatus.ONGOING

    def test_rejected_order_has_rejection_reason(self, db_session, sample_user):
        """Test that rejected orders have rejection reason set"""
        repo = OrdersRepository(db_session)
        order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        updated = repo.mark_rejected(order, "Circuit limit hit")

        assert updated.status == OrderStatus.REJECTED
        assert updated.rejection_reason == "Circuit limit hit"
        assert updated.last_status_check is not None

    def test_execution_tracking_fields(self, db_session, sample_user):
        """Test that execution tracking fields are properly set"""
        repo = OrdersRepository(db_session)
        order = repo.create_amo(
            user_id=sample_user.id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        execution_time_before = datetime.now()
        updated = repo.mark_executed(
            order,
            execution_price=2450.50,
            execution_qty=10.0,
        )
        execution_time_after = datetime.now()

        assert updated.execution_price == 2450.50
        assert updated.execution_qty == 10.0
        assert updated.execution_time is not None
        assert execution_time_before <= updated.execution_time <= execution_time_after
