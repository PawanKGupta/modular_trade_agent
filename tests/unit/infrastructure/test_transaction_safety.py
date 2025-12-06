"""
Tests for Transaction Safety Implementation

Tests verify that:
1. Transaction utility works correctly (commit on success, rollback on error)
2. Repository methods support auto_commit parameter
3. Multi-step operations are atomic (all succeed or all fail)
4. Transaction rollback prevents partial updates
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db.base import Base
from src.infrastructure.db.models import OrderStatus, UserRole, Users
from src.infrastructure.db.transaction import transaction
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.positions_repository import PositionsRepository


@pytest.fixture
def db_session():
    """Create in-memory test database"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create test user
    user = Users(
        email="test@example.com",
        name="Test User",
        password_hash="dummy_hash",
        role=UserRole.USER,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    yield session, user.id

    session.close()


class TestTransactionUtility:
    """Test the transaction context manager utility"""

    def test_transaction_commits_on_success(self, db_session):
        """Test that transaction commits when no exception occurs"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Create position within transaction
        with transaction(session):
            positions_repo.upsert(
                user_id=user_id,
                symbol="RELIANCE",
                quantity=10.0,
                avg_price=100.0,
                auto_commit=False,
            )

        # Verify position was committed
        position = positions_repo.get_by_symbol(user_id, "RELIANCE")
        assert position is not None
        assert position.quantity == 10.0

    def test_transaction_rolls_back_on_exception(self, db_session):
        """Test that transaction rolls back when exception occurs"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Attempt to create position but raise exception
        with pytest.raises(ValueError):
            with transaction(session):
                positions_repo.upsert(
                    user_id=user_id,
                    symbol="RELIANCE",
                    quantity=10.0,
                    avg_price=100.0,
                    auto_commit=False,
                )
                raise ValueError("Test exception")

        # Verify position was NOT committed (rolled back)
        position = positions_repo.get_by_symbol(user_id, "RELIANCE")
        assert position is None

    def test_transaction_nested_transactions(self, db_session):
        """Test that nested transactions work correctly (SQLAlchemy uses savepoints)"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Outer transaction
        with transaction(session):
            positions_repo.upsert(
                user_id=user_id,
                symbol="RELIANCE",
                quantity=10.0,
                avg_price=100.0,
                auto_commit=False,
            )

            # Inner transaction (nested)
            with transaction(session):
                positions_repo.upsert(
                    user_id=user_id,
                    symbol="TCS",
                    quantity=5.0,
                    avg_price=200.0,
                    auto_commit=False,
                )

        # Both should be committed
        rel_position = positions_repo.get_by_symbol(user_id, "RELIANCE")
        tcs_position = positions_repo.get_by_symbol(user_id, "TCS")
        assert rel_position is not None
        assert tcs_position is not None


class TestRepositoryAutoCommit:
    """Test repository methods with auto_commit parameter"""

    def test_positions_upsert_with_auto_commit_false(self, db_session):
        """Test that upsert doesn't commit when auto_commit=False"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Use a nested transaction (savepoint) to test rollback
        savepoint = session.begin_nested()

        # Upsert with auto_commit=False
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="TCS",
            quantity=5.0,
            avg_price=200.0,
            auto_commit=False,
        )

        # Position should exist in session but not committed
        assert position.quantity == 5.0

        # Rollback the nested transaction (savepoint)
        savepoint.rollback()

        # Verify it's not in database (rolled back)
        position_after_rollback = positions_repo.get_by_symbol(user_id, "TCS")
        assert position_after_rollback is None

    def test_positions_upsert_with_auto_commit_true(self, db_session):
        """Test that upsert commits when auto_commit=True (default)"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Upsert with auto_commit=True (default)
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=10.0,
            avg_price=100.0,
            auto_commit=True,  # Explicit for clarity
        )

        # Position should be committed
        assert position.quantity == 10.0
        position_retrieved = positions_repo.get_by_symbol(user_id, "RELIANCE")
        assert position_retrieved is not None
        assert position_retrieved.quantity == 10.0

    def test_orders_mark_executed_with_auto_commit_false(self, db_session):
        """Test that mark_executed doesn't commit when auto_commit=False"""
        session, user_id = db_session
        orders_repo = OrdersRepository(session)

        # Create order first
        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        # Use nested transaction to test rollback
        session.begin_nested()

        # Mark as executed with auto_commit=False
        executed_order = orders_repo.mark_executed(
            order,
            execution_price=100.0,
            execution_qty=10.0,
            auto_commit=False,
        )

        # Order should be updated in session but not committed
        assert executed_order.status == OrderStatus.ONGOING
        assert executed_order.execution_price == 100.0

        # Rollback the nested transaction
        session.rollback()

        # Re-fetch order - should still be PENDING (not executed)
        order_after_rollback = orders_repo.get(order.id)
        assert order_after_rollback.status == OrderStatus.PENDING  # Not executed


class TestMultiStepTransactionSafety:
    """Test that multi-step operations are atomic"""

    def test_order_execution_and_position_creation_atomic(self, db_session):
        """Test that order execution + position creation happen atomically"""
        session, user_id = db_session
        orders_repo = OrdersRepository(session)
        positions_repo = PositionsRepository(session)

        # Create order
        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        # Simulate order execution + position creation in transaction
        with transaction(session):
            # Step 1: Mark order as executed
            orders_repo.mark_executed(
                order,
                execution_price=100.0,
                execution_qty=10.0,
                auto_commit=False,
            )

            # Step 2: Create position
            positions_repo.upsert(
                user_id=user_id,
                symbol="RELIANCE",
                quantity=10.0,
                avg_price=100.0,
                auto_commit=False,
            )

        # Both should be committed
        executed_order = orders_repo.get(order.id)
        position = positions_repo.get_by_symbol(user_id, "RELIANCE")

        assert executed_order.status == OrderStatus.ONGOING
        assert position is not None
        assert position.quantity == 10.0

    def test_order_execution_and_position_creation_rollback(self, db_session):
        """Test that if position creation fails, order execution is rolled back"""
        session, user_id = db_session
        orders_repo = OrdersRepository(session)
        positions_repo = PositionsRepository(session)

        # Create order
        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        # Simulate order execution + position creation with failure
        with pytest.raises(ValueError):
            with transaction(session):
                # Step 1: Mark order as executed
                orders_repo.mark_executed(
                    order,
                    execution_price=100.0,
                    execution_qty=10.0,
                    auto_commit=False,
                )

                # Step 2: Create position
                positions_repo.upsert(
                    user_id=user_id,
                    symbol="RELIANCE",
                    quantity=10.0,
                    avg_price=100.0,
                    auto_commit=False,
                )

                # Step 3: Simulate failure
                raise ValueError("Position creation failed")

        # Both should be rolled back
        order_after = orders_repo.get(order.id)
        position_after = positions_repo.get_by_symbol(user_id, "RELIANCE")

        assert order_after.status == OrderStatus.PENDING  # Not executed
        assert position_after is None  # Not created

    def test_position_update_and_sell_order_update_atomic(self, db_session):
        """Test that position update + sell order update (simulated) are atomic"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Create initial position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=100.0,
            avg_price=100.0,
        )

        # Simulate reentry: update position + update sell order (simulated with DB update)
        with transaction(session):
            # Step 1: Update position (reentry)
            positions_repo.upsert(
                user_id=user_id,
                symbol="RELIANCE",
                quantity=110.0,  # Added 10 shares
                avg_price=105.0,  # New average
                auto_commit=False,
            )

            # Step 2: Simulate sell order update (just verify transaction works)
            # In real code, this would call sell_manager.update_sell_order()
            # For test, we'll just verify the position update is atomic

        # Position should be updated
        updated_position = positions_repo.get_by_symbol(user_id, "RELIANCE")
        assert updated_position.quantity == 110.0
        assert updated_position.avg_price == 105.0

    def test_sell_execution_atomic(self, db_session):
        """Test that sell execution (position close + order closure) is atomic"""
        session, user_id = db_session
        orders_repo = OrdersRepository(session)
        positions_repo = PositionsRepository(session)

        # Create position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=100.0,
            avg_price=100.0,
        )

        # Create buy orders
        buy_order1 = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=50.0,
            price=None,
        )
        orders_repo.mark_executed(buy_order1, execution_price=100.0, execution_qty=50.0)

        buy_order2 = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=50.0,
            price=None,
        )
        orders_repo.mark_executed(buy_order2, execution_price=100.0, execution_qty=50.0)

        # Simulate sell execution: close position + close buy orders
        with transaction(session):
            # Step 1: Mark position as closed
            positions_repo.mark_closed(
                user_id=user_id,
                symbol="RELIANCE",
                auto_commit=False,
            )

            # Step 2: Close buy orders
            orders_repo.update(
                buy_order1,
                status=OrderStatus.CLOSED,
                auto_commit=False,
            )
            orders_repo.update(
                buy_order2,
                status=OrderStatus.CLOSED,
                auto_commit=False,
            )

        # All should be committed
        closed_position = positions_repo.get_by_symbol(user_id, "RELIANCE")
        closed_order1 = orders_repo.get(buy_order1.id)
        closed_order2 = orders_repo.get(buy_order2.id)

        assert closed_position.closed_at is not None
        assert closed_position.quantity == 0.0
        assert closed_order1.status == OrderStatus.CLOSED
        assert closed_order2.status == OrderStatus.CLOSED

    def test_sell_execution_rollback(self, db_session):
        """Test that if order closure fails, position close is rolled back"""
        session, user_id = db_session
        orders_repo = OrdersRepository(session)
        positions_repo = PositionsRepository(session)

        # Create position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=100.0,
            avg_price=100.0,
        )

        # Create buy order
        buy_order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=50.0,
            price=None,
        )
        orders_repo.mark_executed(buy_order, execution_price=100.0, execution_qty=50.0)

        # Simulate sell execution with failure
        with pytest.raises(ValueError):
            with transaction(session):
                # Step 1: Mark position as closed
                positions_repo.mark_closed(
                    user_id=user_id,
                    symbol="RELIANCE",
                    auto_commit=False,
                )

                # Step 2: Close buy order
                orders_repo.update(
                    buy_order,
                    status=OrderStatus.CLOSED,
                    auto_commit=False,
                )

                # Step 3: Simulate failure
                raise ValueError("Order closure failed")

        # Both should be rolled back
        position_after = positions_repo.get_by_symbol(user_id, "RELIANCE")
        order_after = orders_repo.get(buy_order.id)

        assert position_after.closed_at is None  # Not closed
        assert position_after.quantity == 100.0  # Original quantity
        assert order_after.status == OrderStatus.ONGOING  # Not closed


class TestBackwardCompatibility:
    """Test that existing code (without transactions) still works"""

    def test_default_auto_commit_behavior(self, db_session):
        """Test that default behavior (auto_commit=True) still commits immediately"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Upsert without specifying auto_commit (defaults to True)
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=10.0,
            avg_price=100.0,
            # auto_commit not specified - should default to True
        )

        # Should be committed immediately
        assert position.quantity == 10.0
        position_retrieved = positions_repo.get_by_symbol(user_id, "RELIANCE")
        assert position_retrieved is not None
        assert position_retrieved.quantity == 10.0

    def test_orders_default_auto_commit_behavior(self, db_session):
        """Test that orders repository default behavior still commits immediately"""
        session, user_id = db_session
        orders_repo = OrdersRepository(session)

        # Create order
        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE",
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        # Mark as executed without specifying auto_commit (defaults to True)
        executed_order = orders_repo.mark_executed(
            order,
            execution_price=100.0,
            execution_qty=10.0,
            # auto_commit not specified - should default to True
        )

        # Should be committed immediately
        assert executed_order.status == OrderStatus.ONGOING
        order_retrieved = orders_repo.get(order.id)
        assert order_retrieved.status == OrderStatus.ONGOING
