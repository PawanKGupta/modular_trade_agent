"""
Tests for Edge Case #8: Sell Order Execution Updates Positions Table

Tests verify that:
1. mark_closed() sets closed_at and quantity = 0
2. reduce_quantity() reduces quantity and marks closed if quantity becomes 0
3. SellOrderManager updates positions table when sell orders execute
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.persistence.positions_repository import PositionsRepository


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    from src.infrastructure.db.models import Base

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def positions_repo(db_session):
    """Create PositionsRepository instance"""
    return PositionsRepository(db_session)


@pytest.fixture
def user_id():
    return 1


@pytest.fixture
def sample_position(positions_repo, user_id):
    """Create a sample open position for testing"""
    return positions_repo.upsert(
        user_id=user_id,
        symbol="RELIANCE",
        quantity=35.0,
        avg_price=2500.0,
        opened_at=datetime.now(),
    )


class TestMarkClosed:
    """Test mark_closed() method"""

    def test_mark_closed_sets_closed_at_and_quantity_zero(
        self, positions_repo, user_id, sample_position
    ):
        """Test that mark_closed() sets closed_at and quantity = 0"""
        # Verify position is open initially
        assert sample_position.closed_at is None
        assert sample_position.quantity == 35.0

        # Mark as closed
        closed_position = positions_repo.mark_closed(
            user_id=user_id,
            symbol="RELIANCE",
        )

        # Verify position is closed
        assert closed_position is not None
        assert closed_position.closed_at is not None
        assert closed_position.quantity == 0.0
        assert closed_position.symbol == "RELIANCE"

    def test_mark_closed_with_custom_closed_at(self, positions_repo, user_id, sample_position):
        """Test that mark_closed() accepts custom closed_at timestamp"""
        custom_time = datetime(2025, 1, 22, 15, 30, 0)

        closed_position = positions_repo.mark_closed(
            user_id=user_id,
            symbol="RELIANCE",
            closed_at=custom_time,
        )

        assert closed_position.closed_at == custom_time
        assert closed_position.quantity == 0.0

    def test_mark_closed_with_exit_price(self, positions_repo, user_id, sample_position):
        """Test that mark_closed() accepts exit_price parameter (for future use)"""
        closed_position = positions_repo.mark_closed(
            user_id=user_id,
            symbol="RELIANCE",
            exit_price=2550.0,
        )

        assert closed_position.closed_at is not None
        assert closed_position.quantity == 0.0

    def test_mark_closed_position_not_found(self, positions_repo, user_id):
        """Test that mark_closed() returns None if position not found"""
        result = positions_repo.mark_closed(
            user_id=user_id,
            symbol="NONEXISTENT",
        )

        assert result is None

    def test_mark_closed_different_user(self, positions_repo, user_id, sample_position):
        """Test that mark_closed() doesn't affect positions of other users"""
        # Try to close position with wrong user_id
        result = positions_repo.mark_closed(
            user_id=999,  # Different user
            symbol="RELIANCE",
        )

        assert result is None

        # Verify original position is still open
        positions_repo.db.refresh(sample_position)
        assert sample_position.closed_at is None
        assert sample_position.quantity == 35.0


class TestReduceQuantity:
    """Test reduce_quantity() method"""

    def test_reduce_quantity_partial_sell_keeps_position_open(
        self, positions_repo, user_id, sample_position
    ):
        """Test that reduce_quantity() reduces quantity but keeps position open"""
        # Verify initial state
        assert sample_position.quantity == 35.0
        assert sample_position.closed_at is None

        # Reduce quantity by 20 (partial sell)
        updated_position = positions_repo.reduce_quantity(
            user_id=user_id,
            symbol="RELIANCE",
            sold_quantity=20.0,
        )

        # Verify quantity reduced but position still open
        assert updated_position.quantity == 15.0  # 35 - 20
        assert updated_position.closed_at is None  # Still open

    def test_reduce_quantity_full_sell_marks_closed(self, positions_repo, user_id, sample_position):
        """Test that reduce_quantity() marks position as closed if quantity becomes 0"""
        # Reduce quantity by full amount
        updated_position = positions_repo.reduce_quantity(
            user_id=user_id,
            symbol="RELIANCE",
            sold_quantity=35.0,
        )

        # Verify position is closed
        assert updated_position.quantity == 0.0
        assert updated_position.closed_at is not None

    def test_reduce_quantity_more_than_available_sets_to_zero(
        self, positions_repo, user_id, sample_position
    ):
        """Test that reduce_quantity() doesn't go negative, sets to 0"""
        # Try to reduce more than available
        updated_position = positions_repo.reduce_quantity(
            user_id=user_id,
            symbol="RELIANCE",
            sold_quantity=50.0,  # More than 35
        )

        # Verify quantity is 0 (not negative)
        assert updated_position.quantity == 0.0
        assert updated_position.closed_at is not None  # Should be closed

    def test_reduce_quantity_multiple_partial_sells(self, positions_repo, user_id, sample_position):
        """Test multiple partial sells reduce quantity correctly"""
        # First partial sell: 10 shares
        pos1 = positions_repo.reduce_quantity(
            user_id=user_id,
            symbol="RELIANCE",
            sold_quantity=10.0,
        )
        assert pos1.quantity == 25.0  # 35 - 10
        assert pos1.closed_at is None

        # Second partial sell: 15 shares
        pos2 = positions_repo.reduce_quantity(
            user_id=user_id,
            symbol="RELIANCE",
            sold_quantity=15.0,
        )
        assert pos2.quantity == 10.0  # 25 - 15
        assert pos2.closed_at is None

        # Third partial sell: remaining 10 shares
        pos3 = positions_repo.reduce_quantity(
            user_id=user_id,
            symbol="RELIANCE",
            sold_quantity=10.0,
        )
        assert pos3.quantity == 0.0
        assert pos3.closed_at is not None  # Now closed

    def test_reduce_quantity_position_not_found(self, positions_repo, user_id):
        """Test that reduce_quantity() returns None if position not found"""
        result = positions_repo.reduce_quantity(
            user_id=user_id,
            symbol="NONEXISTENT",
            sold_quantity=10.0,
        )

        assert result is None

    def test_reduce_quantity_different_user(self, positions_repo, user_id, sample_position):
        """Test that reduce_quantity() doesn't affect positions of other users"""
        # Try to reduce quantity with wrong user_id
        result = positions_repo.reduce_quantity(
            user_id=999,  # Different user
            symbol="RELIANCE",
            sold_quantity=10.0,
        )

        assert result is None

        # Verify original position unchanged
        positions_repo.db.refresh(sample_position)
        assert sample_position.quantity == 35.0
        assert sample_position.closed_at is None


class TestSellOrderExecutionUpdatesPositions:
    """Test that SellOrderManager updates positions table on sell execution"""

    @pytest.fixture
    def mock_auth(self):
        """Create mock auth"""
        from unittest.mock import Mock

        mock = Mock()
        mock.client = None
        return mock

    @pytest.fixture
    def sell_manager(self, mock_auth, positions_repo, user_id):
        """Create SellOrderManager with database repos"""
        from unittest.mock import patch

        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth"):
            with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
                from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager

                manager = SellOrderManager(
                    auth=mock_auth,
                    positions_repo=positions_repo,
                    user_id=user_id,
                )
                return manager

    def test_full_execution_marks_position_closed(
        self, sell_manager, positions_repo, user_id, sample_position
    ):
        """Test that full sell execution marks position as closed"""
        from unittest.mock import patch

        # Mock has_completed_sell_order to return full execution
        with patch.object(
            sell_manager,
            "has_completed_sell_order",
            return_value={
                "order_id": "ORDER123",
                "price": 2550.0,
                "filled_qty": 35,
                "order_qty": 35,
            },
        ):
            with patch.object(sell_manager, "state_manager", None):
                with patch.object(sell_manager, "mark_position_closed", return_value=True):
                    # Setup active sell order
                    sell_manager.active_sell_orders = {
                        "RELIANCE": {
                            "order_id": "ORDER123",
                            "qty": 35,
                            "target_price": 2550.0,
                        }
                    }

                    # Call monitor_and_update
                    sell_manager.monitor_and_update()

                    # Verify position is closed
                    positions_repo.db.refresh(sample_position)
                    assert sample_position.closed_at is not None
                    assert sample_position.quantity == 0.0

    def test_partial_execution_reduces_quantity(
        self, sell_manager, positions_repo, user_id, sample_position
    ):
        """Test that partial sell execution reduces quantity but keeps position open"""
        from unittest.mock import patch

        # Mock has_completed_sell_order to return partial execution
        with patch.object(
            sell_manager,
            "has_completed_sell_order",
            return_value={
                "order_id": "ORDER123",
                "price": 2550.0,
                "filled_qty": 20,  # Partial: 20 out of 35
                "order_qty": 35,
            },
        ):
            with patch.object(sell_manager, "state_manager", None):
                with patch.object(sell_manager, "mark_position_closed", return_value=True):
                    # Setup active sell order
                    sell_manager.active_sell_orders = {
                        "RELIANCE": {
                            "order_id": "ORDER123",
                            "qty": 35,
                            "target_price": 2550.0,
                        }
                    }

                    # Call monitor_and_update
                    sell_manager.monitor_and_update()

                    # Verify quantity reduced but position still open
                    positions_repo.db.refresh(sample_position)
                    assert sample_position.quantity == 15.0  # 35 - 20
                    assert sample_position.closed_at is None  # Still open

    def test_no_positions_repo_skips_update(self, sell_manager, sample_position):
        """Test that if positions_repo is None, update is skipped gracefully"""
        from unittest.mock import patch

        # Set positions_repo to None
        sell_manager.positions_repo = None

        with patch.object(
            sell_manager,
            "has_completed_sell_order",
            return_value={
                "order_id": "ORDER123",
                "price": 2550.0,
                "filled_qty": 35,
                "order_qty": 35,
            },
        ):
            with patch.object(sell_manager, "state_manager", None):
                with patch.object(sell_manager, "mark_position_closed", return_value=True):
                    sell_manager.active_sell_orders = {
                        "RELIANCE": {
                            "order_id": "ORDER123",
                            "qty": 35,
                            "target_price": 2550.0,
                        }
                    }

                    # Should not raise error
                    sell_manager.monitor_and_update()

                    # Position should remain unchanged (no update attempted)
                    assert sample_position.closed_at is None

    def test_no_user_id_skips_update(self, sell_manager, positions_repo, sample_position):
        """Test that if user_id is None, update is skipped gracefully"""
        from unittest.mock import patch

        # Set user_id to None
        sell_manager.user_id = None

        with patch.object(
            sell_manager,
            "has_completed_sell_order",
            return_value={
                "order_id": "ORDER123",
                "price": 2550.0,
                "filled_qty": 35,
                "order_qty": 35,
            },
        ):
            with patch.object(sell_manager, "state_manager", None):
                with patch.object(sell_manager, "mark_position_closed", return_value=True):
                    sell_manager.active_sell_orders = {
                        "RELIANCE": {
                            "order_id": "ORDER123",
                            "qty": 35,
                            "target_price": 2550.0,
                        }
                    }

                    # Should not raise error
                    sell_manager.monitor_and_update()

                    # Position should remain unchanged (no update attempted)
                    assert sample_position.closed_at is None

    def test_error_handling_continues_execution(
        self, sell_manager, positions_repo, user_id, sample_position
    ):
        """Test that errors in position update don't break execution flow"""
        from unittest.mock import patch

        # Mock positions_repo.mark_closed to raise exception
        with patch.object(positions_repo, "mark_closed", side_effect=Exception("Database error")):
            with patch.object(
                sell_manager,
                "has_completed_sell_order",
                return_value={
                    "order_id": "ORDER123",
                    "price": 2550.0,
                    "filled_qty": 35,
                    "order_qty": 35,
                },
            ):
                with patch.object(sell_manager, "state_manager", None):
                    with patch.object(sell_manager, "mark_position_closed", return_value=True):
                        sell_manager.active_sell_orders = {
                            "RELIANCE": {
                                "order_id": "ORDER123",
                                "qty": 35,
                                "target_price": 2550.0,
                            }
                        }

                        # Should not raise error, should continue execution
                        sell_manager.monitor_and_update()

                        # Verify execution continued (mark_position_closed was called)
                        sell_manager.mark_position_closed.assert_called_once()
