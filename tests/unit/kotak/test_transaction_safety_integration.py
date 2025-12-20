"""
Integration tests for transaction safety in order and position management flows.

Tests verify that:
1. Order execution + position creation is atomic
2. Sell execution + position close + order closure is atomic
3. Reentry processing (position update + sell order update) is atomic
4. Transaction rollback prevents partial updates in real scenarios
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.db.base import Base
from src.infrastructure.db.models import OrderStatus, UserRole, Users
from src.infrastructure.db.timezone_utils import ist_now
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


@pytest.fixture
def mock_sell_manager():
    """Create a mock SellOrderManager"""
    manager = Mock()
    manager.get_existing_sell_orders = Mock(return_value={})
    manager.update_sell_order = Mock(return_value=True)
    return manager


class TestOrderExecutionTransactionSafety:
    """Test transaction safety in order execution flow"""

    def test_order_execution_creates_position_atomically(self, db_session, mock_sell_manager):
        """Test that order execution and position creation happen atomically"""
        session, user_id = db_session
        orders_repo = OrdersRepository(session)
        positions_repo = PositionsRepository(session)

        # Create order
        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",  # Full symbol after migration
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        # Simulate order execution flow (like unified_order_monitor does)
        from src.infrastructure.db.transaction import transaction

        with transaction(session):
            # Mark order as executed
            orders_repo.mark_executed(
                order,
                execution_price=100.0,
                execution_qty=10.0,
                auto_commit=False,
            )

            # Create position
            positions_repo.upsert(
                user_id=user_id,
                symbol="RELIANCE-EQ",  # Full symbol after migration
                quantity=10.0,
                avg_price=100.0,
                auto_commit=False,
            )

        # Both should be committed
        executed_order = orders_repo.get(order.id)
        position = positions_repo.get_by_symbol(
            user_id, "RELIANCE-EQ"
        )  # Full symbol after migration

        assert executed_order.status == OrderStatus.ONGOING
        assert position is not None
        assert position.quantity == 10.0

    def test_order_execution_rollback_on_position_creation_failure(
        self, db_session, mock_sell_manager
    ):
        """Test that order execution is rolled back if position creation fails"""
        session, user_id = db_session
        orders_repo = OrdersRepository(session)
        positions_repo = PositionsRepository(session)

        # Create order
        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",  # Full symbol after migration
            side="buy",
            order_type="market",
            quantity=10.0,
            price=None,
        )

        # Simulate order execution with position creation failure
        from src.infrastructure.db.transaction import transaction

        with pytest.raises(ValueError):
            with transaction(session):
                # Mark order as executed
                orders_repo.mark_executed(
                    order,
                    execution_price=100.0,
                    execution_qty=10.0,
                    auto_commit=False,
                )

                # Simulate position creation failure
                raise ValueError("Position creation failed")

        # Order should not be executed (rolled back)
        order_after = orders_repo.get(order.id)
        assert order_after.status == OrderStatus.PENDING

        # Position should not exist
        position_after = positions_repo.get_by_symbol(user_id, "RELIANCE")
        assert position_after is None


class TestReentryTransactionSafety:
    """Test transaction safety in reentry processing flow"""

    def test_reentry_position_update_atomic(self, db_session, mock_sell_manager):
        """Test that reentry position update and integrity check are atomic"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Create initial position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=100.0,
            avg_price=100.0,
            reentry_count=0,
            reentries=[],
        )

        # Simulate reentry: update position + integrity check
        from src.infrastructure.db.transaction import transaction

        with transaction(session):
            # Step 1: Update position with reentry
            reentry_data = {
                "qty": 10,
                "price": 95.0,
                "time": ist_now().isoformat(),
                "order_id": "REENTRY-123",
            }
            reentries_array = [reentry_data]

            positions_repo.upsert(
                user_id=user_id,
                symbol="RELIANCE",
                quantity=110.0,  # Added 10 shares
                avg_price=99.5,  # New average
                reentry_count=1,
                reentries=reentries_array,
                auto_commit=False,
            )

            # Step 2: Integrity check and fix (simulated - in real code this happens)
            updated_position = positions_repo.get_by_symbol(user_id, "RELIANCE")
            if updated_position.reentry_count != len(updated_position.reentries):
                # Fix mismatch
                positions_repo.upsert(
                    user_id=user_id,
                    symbol="RELIANCE",
                    reentry_count=len(updated_position.reentries),
                    quantity=updated_position.quantity,
                    avg_price=updated_position.avg_price,
                    reentries=updated_position.reentries,
                    auto_commit=False,
                )

        # Position should be updated with correct reentry data
        final_position = positions_repo.get_by_symbol(user_id, "RELIANCE")
        assert final_position.quantity == 110.0
        assert final_position.reentry_count == 1
        assert len(final_position.reentries) == 1

    def test_reentry_rollback_on_integrity_check_failure(self, db_session, mock_sell_manager):
        """Test that reentry update is rolled back if integrity check fails"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Create initial position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=100.0,
            avg_price=100.0,
            reentry_count=0,
            reentries=[],
        )

        # Simulate reentry with integrity check failure
        from src.infrastructure.db.transaction import transaction

        with pytest.raises(ValueError):
            with transaction(session):
                # Update position with reentry
                reentry_data = {
                    "qty": 10,
                    "price": 95.0,
                    "time": ist_now().isoformat(),
                    "order_id": "REENTRY-123",
                }

                positions_repo.upsert(
                    user_id=user_id,
                    symbol="RELIANCE",
                    quantity=110.0,
                    avg_price=99.5,
                    reentry_count=1,
                    reentries=[reentry_data],
                    auto_commit=False,
                )

                # Simulate integrity check failure
                raise ValueError("Integrity check failed")

        # Position should be rolled back to original state
        position_after = positions_repo.get_by_symbol(user_id, "RELIANCE")
        assert position_after.quantity == 100.0
        assert position_after.reentry_count == 0
        assert len(position_after.reentries) == 0


class TestSellExecutionTransactionSafety:
    """Test transaction safety in sell execution flow"""

    def test_sell_execution_closes_position_and_orders_atomically(
        self, db_session, mock_sell_manager
    ):
        """Test that sell execution closes position and orders atomically"""
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
            symbol="RELIANCE-EQ",  # Full symbol after migration
            side="buy",
            order_type="market",
            quantity=50.0,
            price=None,
        )
        orders_repo.mark_executed(buy_order1, execution_price=100.0, execution_qty=50.0)

        buy_order2 = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",  # Full symbol after migration
            side="buy",
            order_type="market",
            quantity=50.0,
            price=None,
        )
        orders_repo.mark_executed(buy_order2, execution_price=100.0, execution_qty=50.0)

        # Simulate sell execution: close position + close buy orders
        from src.infrastructure.db.transaction import transaction

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
        # Use get_by_symbol_any() to get closed position
        closed_position = positions_repo.get_by_symbol_any(user_id, "RELIANCE", include_closed=True)
        closed_order1 = orders_repo.get(buy_order1.id)
        closed_order2 = orders_repo.get(buy_order2.id)

        assert closed_position is not None, "Position should exist (closed)"
        assert closed_position.closed_at is not None
        assert closed_position.quantity == 0.0
        assert closed_order1.status == OrderStatus.CLOSED
        assert closed_order2.status == OrderStatus.CLOSED

    def test_sell_execution_rollback_on_order_closure_failure(self, db_session, mock_sell_manager):
        """Test that position close is rolled back if order closure fails"""
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
            symbol="RELIANCE-EQ",  # Full symbol after migration
            side="buy",
            order_type="market",
            quantity=50.0,
            price=None,
        )
        orders_repo.mark_executed(buy_order, execution_price=100.0, execution_qty=50.0)

        # Simulate sell execution with order closure failure
        from src.infrastructure.db.transaction import transaction

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

        assert position_after.closed_at is None
        assert position_after.quantity == 100.0
        assert order_after.status == OrderStatus.ONGOING

    def test_partial_sell_reduces_quantity_atomically(self, db_session, mock_sell_manager):
        """Test that partial sell reduces position quantity atomically"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Create position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=100.0,
            avg_price=100.0,
        )

        # Simulate partial sell execution
        from src.infrastructure.db.transaction import transaction

        with transaction(session):
            # Reduce quantity
            positions_repo.reduce_quantity(
                user_id=user_id,
                symbol="RELIANCE",
                sold_quantity=50.0,
                auto_commit=False,
            )

        # Position should be updated
        updated_position = positions_repo.get_by_symbol(user_id, "RELIANCE")
        assert updated_position.quantity == 50.0
        assert updated_position.closed_at is None  # Still open

    def test_partial_sell_rollback(self, db_session, mock_sell_manager):
        """Test that partial sell is rolled back on failure"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Create position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=100.0,
            avg_price=100.0,
        )

        # Simulate partial sell with failure
        from src.infrastructure.db.transaction import transaction

        with pytest.raises(ValueError):
            with transaction(session):
                # Reduce quantity
                positions_repo.reduce_quantity(
                    user_id=user_id,
                    symbol="RELIANCE",
                    sold_quantity=50.0,
                    auto_commit=False,
                )

                # Simulate failure
                raise ValueError("Partial sell failed")

        # Position should be unchanged
        position_after = positions_repo.get_by_symbol(user_id, "RELIANCE")
        assert position_after.quantity == 100.0
