"""
Tests for Edge Case #8: SellOrderManager position table updates

Tests verify that SellOrderManager correctly updates positions table
when sell orders execute (full and partial execution scenarios).
"""

from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from src.infrastructure.db.models import OrderStatus as DbOrderStatus
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def mock_auth():
    """Create mock auth"""
    mock = Mock()
    mock.client = None
    return mock


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

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
    from src.infrastructure.persistence.positions_repository import PositionsRepository

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
        opened_at=ist_now(),
    )


@pytest.fixture
def sell_manager(mock_auth, positions_repo, user_id):
    """Create SellOrderManager with database repos"""
    with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth"):
        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
            manager = SellOrderManager(
                auth=mock_auth,
                positions_repo=positions_repo,
                user_id=user_id,
            )
            return manager


class TestHasCompletedSellOrderReturnsFilledQuantity:
    """Test that has_completed_sell_order() returns filled_qty and order_qty"""

    def test_has_completed_sell_order_returns_filled_qty_from_order_status_verifier(
        self, sell_manager
    ):
        """Test that has_completed_sell_order() extracts filled_qty from OrderStatusVerifier"""
        from modules.kotak_neo_auto_trader.utils.order_field_extractor import (
            OrderFieldExtractor,
        )

        # Mock OrderStatusVerifier
        mock_verifier = Mock()
        mock_verifier.get_verification_results_for_symbol.return_value = [
            {
                "status": "EXECUTED",
                "order_id": "ORDER123",
                "broker_order": {
                    "fldQty": 20,  # Filled quantity
                    "qty": 35,  # Order quantity
                    "avgPrc": "2550.0",
                },
            }
        ]
        sell_manager.order_verifier = mock_verifier

        result = sell_manager.has_completed_sell_order("RELIANCE")

        assert result is not None
        assert result["order_id"] == "ORDER123"
        assert result["filled_qty"] == 20
        assert result["order_qty"] == 35
        assert result["price"] == 2550.0

    def test_has_completed_sell_order_returns_filled_qty_from_direct_api(
        self, sell_manager
    ):
        """Test that has_completed_sell_order() extracts filled_qty from direct API call"""
        # Mock orders.get_orders() to return completed order
        mock_orders = Mock()
        mock_orders.get_orders.return_value = {
            "data": [
                {
                    "trnsTp": "S",  # Sell order
                    "trdSym": "RELIANCE-EQ",
                    "ordSt": "complete",  # Completed
                    "neoOrdNo": "ORDER123",
                    "avgPrc": "2550.0",
                    "fldQty": 20,  # Filled quantity
                    "qty": 35,  # Order quantity
                }
            ]
        }
        sell_manager.orders = mock_orders
        sell_manager.order_verifier = None  # No verifier, use direct API

        result = sell_manager.has_completed_sell_order("RELIANCE")

        assert result is not None
        assert result["order_id"] == "ORDER123"
        assert result["filled_qty"] == 20
        assert result["order_qty"] == 35
        assert result["price"] == 2550.0

    def test_has_completed_sell_order_returns_zero_when_no_filled_qty(
        self, sell_manager
    ):
        """Test that has_completed_sell_order() returns 0 for filled_qty when not available"""
        # Mock orders.get_orders() to return completed order without fldQty
        mock_orders = Mock()
        mock_orders.get_orders.return_value = {
            "data": [
                {
                    "trnsTp": "S",
                    "trdSym": "RELIANCE-EQ",
                    "ordSt": "complete",
                    "neoOrdNo": "ORDER123",
                    "avgPrc": "2550.0",
                    "qty": 35,  # Order quantity only, no fldQty
                }
            ]
        }
        sell_manager.orders = mock_orders
        sell_manager.order_verifier = None

        result = sell_manager.has_completed_sell_order("RELIANCE")

        assert result is not None
        assert result["filled_qty"] == 0  # Should default to 0
        assert result["order_qty"] == 35


class TestMonitorAndUpdatePositionTableUpdates:
    """Test that monitor_and_update() updates positions table correctly"""

    def test_monitor_and_update_full_execution_via_has_completed_sell_order(
        self, sell_manager, positions_repo, user_id, sample_position
    ):
        """Test full execution detected via has_completed_sell_order()"""
        # Mock has_completed_sell_order to return full execution
        with patch.object(
            sell_manager,
            "has_completed_sell_order",
            return_value={
                "order_id": "ORDER123",
                "price": 2550.0,
                "filled_qty": 35,  # Full execution
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

    def test_monitor_and_update_partial_execution_via_has_completed_sell_order(
        self, sell_manager, positions_repo, user_id, sample_position
    ):
        """Test partial execution detected via has_completed_sell_order()"""
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

    def test_monitor_and_update_full_execution_via_executed_ids(
        self, sell_manager, positions_repo, user_id, sample_position
    ):
        """Test full execution detected via executed_ids path"""
        # Mock check_order_execution to return executed order IDs
        with patch.object(sell_manager, "check_order_execution", return_value=["ORDER123"]):
            with patch.object(sell_manager, "has_completed_sell_order", return_value=None):
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

                        # Verify position is closed (assumes full execution when no filled_qty info)
                        positions_repo.db.refresh(sample_position)
                        assert sample_position.closed_at is not None
                        assert sample_position.quantity == 0.0

    def test_monitor_and_update_uses_filled_qty_over_order_qty_for_full_check(
        self, sell_manager, positions_repo, user_id, sample_position
    ):
        """Test that filled_qty >= order_qty correctly identifies full execution"""
        # Mock has_completed_sell_order to return filled_qty equal to order_qty
        with patch.object(
            sell_manager,
            "has_completed_sell_order",
            return_value={
                "order_id": "ORDER123",
                "price": 2550.0,
                "filled_qty": 35,  # Equal to order_qty
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

                    sell_manager.monitor_and_update()

                    # Should mark as closed (filled_qty >= order_qty)
                    positions_repo.db.refresh(sample_position)
                    assert sample_position.closed_at is not None
                    assert sample_position.quantity == 0.0

    def test_monitor_and_update_uses_filled_qty_over_order_info_qty(
        self, sell_manager, positions_repo, user_id, sample_position
    ):
        """Test that filled_qty >= order_info['qty'] correctly identifies full execution"""
        # Mock has_completed_sell_order to return filled_qty equal to order_info qty
        with patch.object(
            sell_manager,
            "has_completed_sell_order",
            return_value={
                "order_id": "ORDER123",
                "price": 2550.0,
                "filled_qty": 35,  # Equal to order_info qty
                "order_qty": 0,  # Missing, will use order_info qty
            },
        ):
            with patch.object(sell_manager, "state_manager", None):
                with patch.object(sell_manager, "mark_position_closed", return_value=True):
                    sell_manager.active_sell_orders = {
                        "RELIANCE": {
                            "order_id": "ORDER123",
                            "qty": 35,  # This will be used for comparison
                            "target_price": 2550.0,
                        }
                    }

                    sell_manager.monitor_and_update()

                    # Should mark as closed (filled_qty >= order_info['qty'])
                    positions_repo.db.refresh(sample_position)
                    assert sample_position.closed_at is not None
                    assert sample_position.quantity == 0.0


    def test_monitor_and_update_handles_database_error_gracefully(
        self, sell_manager, user_id, sample_position
    ):
        """Test that database errors don't break execution flow"""
        # Mock positions_repo.mark_closed to raise exception
        with patch.object(
            sell_manager.positions_repo, "mark_closed", side_effect=Exception("Database error")
        ):
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
                    with patch.object(
                        sell_manager, "mark_position_closed", return_value=True
                    ):
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

    def test_monitor_and_update_symbol_extraction_handles_various_formats(
        self, sell_manager, positions_repo, user_id
    ):
        """Test that symbol extraction works with various symbol formats"""
        # Create position with base symbol
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=35.0,
            avg_price=2500.0,
        )

        # Mock has_completed_sell_order with full symbol format
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
                    # Use full symbol format in active_sell_orders
                    sell_manager.active_sell_orders = {
                        "RELIANCE-EQ": {  # Full symbol format
                            "order_id": "ORDER123",
                            "qty": 35,
                            "target_price": 2550.0,
                        }
                    }

                    sell_manager.monitor_and_update()

                    # Should find position by base symbol
                    positions_repo.db.refresh(position)
                    assert position.closed_at is not None
                    assert position.quantity == 0.0

