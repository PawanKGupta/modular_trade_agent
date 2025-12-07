"""
Tests for Flaw #9: No Rollback on Broker API Failure

Tests that broker API calls happen before database updates, and if broker API fails,
the position update still happens (primary operation) while sell order update is retried later.

Scenario:
- Reentry order executes: Position should be updated (primary)
- Sell order update attempted: If broker API fails, position still updated, sell order retried later
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor
from src.infrastructure.db.models import Positions
from src.infrastructure.db.timezone_utils import ist_now


class TestBrokerAPIFailureRollback:
    """Test that broker API calls happen before database updates and handle failures correctly"""

    @pytest.fixture
    def mock_auth(self):
        """Create mock auth object"""
        auth = Mock()
        auth.client = Mock()
        return auth

    @pytest.fixture
    def mock_sell_manager(self, mock_auth):
        """Create mock SellOrderManager"""
        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
            manager = SellOrderManager(auth=mock_auth, history_path="test_history.json")
            manager.orders = Mock()
            manager.update_sell_order = Mock(return_value=True)
            manager.get_existing_sell_orders = Mock(return_value={})
            manager.active_sell_orders = {}
            return manager

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session"""
        return Mock()

    @pytest.fixture
    def unified_monitor(self, mock_sell_manager, mock_db_session):
        """Create UnifiedOrderMonitor instance"""
        with (
            patch("modules.kotak_neo_auto_trader.unified_order_monitor.OrdersRepository"),
            patch("modules.kotak_neo_auto_trader.unified_order_monitor.PositionsRepository"),
        ):
            monitor = UnifiedOrderMonitor(
                sell_order_manager=mock_sell_manager,
                db_session=mock_db_session,
                user_id=1,
            )
            return monitor

    @pytest.fixture
    def mock_positions_repo(self, unified_monitor):
        """Mock positions repository"""
        positions_repo = Mock()
        unified_monitor.positions_repo = positions_repo
        positions_repo.db = Mock()
        return positions_repo

    @pytest.fixture
    def mock_orders_repo(self, unified_monitor):
        """Mock orders repository"""
        orders_repo = Mock()
        unified_monitor.orders_repo = orders_repo
        return orders_repo

    def test_broker_api_called_before_database_update(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """Test that broker API call happens before database update"""
        # Setup: Existing position
        base_symbol = "RELIANCE"
        order_id = "REENTRY123"
        execution_time = ist_now()

        existing_position = Positions(
            user_id=1,
            symbol=base_symbol,
            quantity=100.0,
            avg_price=100.0,
            opened_at=ist_now(),
            reentry_count=0,
            reentries=[],
            closed_at=None,
        )

        # Mock position read
        mock_positions_repo.get_by_symbol_for_update = Mock(return_value=existing_position)

        # Mock DB order
        db_order = Mock()
        db_order.entry_type = "reentry"
        db_order.order_metadata = {"rsi": 25.0, "price": 95.0, "rsi_entry_level": 25.0}
        db_order.filled_at = execution_time
        db_order.execution_time = None
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=db_order)
        mock_orders_repo.get = Mock(return_value=db_order)

        # Mock sell order exists
        mock_sell_manager.get_existing_sell_orders = Mock(
            return_value={
                base_symbol.upper(): {
                    "order_id": "SELL123",
                    "qty": 100,
                    "price": 9.50,
                }
            }
        )
        mock_sell_manager.update_sell_order = Mock(return_value=True)

        # Track call order
        call_order = []

        def track_update_sell_order(*args, **kwargs):
            call_order.append("broker_api")
            return True

        def track_upsert(*args, **kwargs):
            call_order.append("database_update")
            return Mock()

        mock_sell_manager.update_sell_order.side_effect = track_update_sell_order
        mock_positions_repo.upsert = Mock(side_effect=track_upsert)

        # Mock transaction context manager
        mock_transaction = Mock()
        mock_transaction.__enter__ = Mock(return_value=mock_positions_repo.db)
        mock_transaction.__exit__ = Mock(return_value=False)

        with patch(
            "modules.kotak_neo_auto_trader.unified_order_monitor.transaction",
            return_value=mock_transaction,
        ):
            # Call _create_position_from_executed_order
            unified_monitor._create_position_from_executed_order(
                order_id=order_id,
                order_info={"symbol": "RELIANCE-EQ", "db_order_id": 1},
                execution_price=95.0,
                execution_qty=10.0,
            )

        # Verify: Broker API called before database update
        assert call_order[0] == "broker_api", "Broker API should be called first"
        assert call_order[1] == "database_update", "Database update should happen after broker API"
        assert mock_sell_manager.update_sell_order.called, "Broker API should be called"
        assert mock_positions_repo.upsert.called, "Database update should happen"

    def test_broker_api_success_updates_both_position_and_sell_order(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """Test that if broker API succeeds, both position and sell order are updated"""
        # Setup: Existing position
        base_symbol = "RELIANCE"
        order_id = "REENTRY123"
        execution_time = ist_now()

        existing_position = Positions(
            user_id=1,
            symbol=base_symbol,
            quantity=100.0,
            avg_price=100.0,
            opened_at=ist_now(),
            reentry_count=0,
            reentries=[],
            closed_at=None,
        )

        # Mock position read
        mock_positions_repo.get_by_symbol_for_update = Mock(return_value=existing_position)

        # Mock DB order
        db_order = Mock()
        db_order.entry_type = "reentry"
        db_order.order_metadata = {"rsi": 25.0, "price": 95.0, "rsi_entry_level": 25.0}
        db_order.filled_at = execution_time
        db_order.execution_time = None
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=db_order)
        mock_orders_repo.get = Mock(return_value=db_order)

        # Mock sell order exists
        mock_sell_manager.get_existing_sell_orders = Mock(
            return_value={
                base_symbol.upper(): {
                    "order_id": "SELL123",
                    "qty": 100,
                    "price": 9.50,
                }
            }
        )
        mock_sell_manager.update_sell_order = Mock(return_value=True)

        # Mock transaction context manager
        mock_transaction = Mock()
        mock_transaction.__enter__ = Mock(return_value=mock_positions_repo.db)
        mock_transaction.__exit__ = Mock(return_value=False)

        with patch(
            "modules.kotak_neo_auto_trader.unified_order_monitor.transaction",
            return_value=mock_transaction,
        ):
            # Call _create_position_from_executed_order
            unified_monitor._create_position_from_executed_order(
                order_id=order_id,
                order_info={"symbol": "RELIANCE-EQ", "db_order_id": 1},
                execution_price=95.0,
                execution_qty=10.0,
            )

        # Verify: Both broker API and database update were called
        assert mock_sell_manager.update_sell_order.called, "Broker API should be called"
        assert mock_positions_repo.upsert.called, "Position should be updated"
        # Verify: Broker API was called with correct parameters
        mock_sell_manager.update_sell_order.assert_called_once_with(
            order_id="SELL123",
            symbol=base_symbol,
            qty=110,  # New quantity after reentry
            new_price=9.50,
        )

    def test_broker_api_failure_still_updates_position(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """Test that if broker API fails, position is still updated (primary operation)"""
        # Setup: Existing position
        base_symbol = "RELIANCE"
        order_id = "REENTRY123"
        execution_time = ist_now()

        existing_position = Positions(
            user_id=1,
            symbol=base_symbol,
            quantity=100.0,
            avg_price=100.0,
            opened_at=ist_now(),
            reentry_count=0,
            reentries=[],
            closed_at=None,
        )

        # Mock position read
        mock_positions_repo.get_by_symbol_for_update = Mock(return_value=existing_position)

        # Mock DB order
        db_order = Mock()
        db_order.entry_type = "reentry"
        db_order.order_metadata = {"rsi": 25.0, "price": 95.0, "rsi_entry_level": 25.0}
        db_order.filled_at = execution_time
        db_order.execution_time = None
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=db_order)
        mock_orders_repo.get = Mock(return_value=db_order)

        # Mock sell order exists
        mock_sell_manager.get_existing_sell_orders = Mock(
            return_value={
                base_symbol.upper(): {
                    "order_id": "SELL123",
                    "qty": 100,
                    "price": 9.50,
                }
            }
        )
        # Mock broker API failure
        mock_sell_manager.update_sell_order = Mock(return_value=False)

        # Mock transaction context manager
        mock_transaction = Mock()
        mock_transaction.__enter__ = Mock(return_value=mock_positions_repo.db)
        mock_transaction.__exit__ = Mock(return_value=False)

        with patch(
            "modules.kotak_neo_auto_trader.unified_order_monitor.transaction",
            return_value=mock_transaction,
        ):
            # Call _create_position_from_executed_order
            unified_monitor._create_position_from_executed_order(
                order_id=order_id,
                order_info={"symbol": "RELIANCE-EQ", "db_order_id": 1},
                execution_price=95.0,
                execution_qty=10.0,
            )

        # Verify: Broker API was called (but failed)
        assert mock_sell_manager.update_sell_order.called, "Broker API should be attempted"
        # Verify: Position is still updated (primary operation)
        assert (
            mock_positions_repo.upsert.called
        ), "Position should still be updated even if broker API fails"

    def test_broker_api_exception_still_updates_position(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """Test that if broker API raises exception, position is still updated"""
        # Setup: Existing position
        base_symbol = "RELIANCE"
        order_id = "REENTRY123"
        execution_time = ist_now()

        existing_position = Positions(
            user_id=1,
            symbol=base_symbol,
            quantity=100.0,
            avg_price=100.0,
            opened_at=ist_now(),
            reentry_count=0,
            reentries=[],
            closed_at=None,
        )

        # Mock position read
        mock_positions_repo.get_by_symbol_for_update = Mock(return_value=existing_position)

        # Mock DB order
        db_order = Mock()
        db_order.entry_type = "reentry"
        db_order.order_metadata = {"rsi": 25.0, "price": 95.0, "rsi_entry_level": 25.0}
        db_order.filled_at = execution_time
        db_order.execution_time = None
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=db_order)
        mock_orders_repo.get = Mock(return_value=db_order)

        # Mock sell order exists
        mock_sell_manager.get_existing_sell_orders = Mock(
            return_value={
                base_symbol.upper(): {
                    "order_id": "SELL123",
                    "qty": 100,
                    "price": 9.50,
                }
            }
        )
        # Mock broker API exception
        mock_sell_manager.update_sell_order = Mock(side_effect=Exception("Network timeout"))

        # Mock transaction context manager
        mock_transaction = Mock()
        mock_transaction.__enter__ = Mock(return_value=mock_positions_repo.db)
        mock_transaction.__exit__ = Mock(return_value=False)

        with patch(
            "modules.kotak_neo_auto_trader.unified_order_monitor.transaction",
            return_value=mock_transaction,
        ):
            # Call _create_position_from_executed_order
            unified_monitor._create_position_from_executed_order(
                order_id=order_id,
                order_info={"symbol": "RELIANCE-EQ", "db_order_id": 1},
                execution_price=95.0,
                execution_qty=10.0,
            )

        # Verify: Broker API was attempted (but raised exception)
        assert mock_sell_manager.update_sell_order.called, "Broker API should be attempted"
        # Verify: Position is still updated (primary operation)
        assert (
            mock_positions_repo.upsert.called
        ), "Position should still be updated even if broker API raises exception"

    def test_no_sell_order_skips_broker_api_call(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """Test that if no sell order exists, broker API call is skipped"""
        # Setup: Existing position
        base_symbol = "RELIANCE"
        order_id = "REENTRY123"
        execution_time = ist_now()

        existing_position = Positions(
            user_id=1,
            symbol=base_symbol,
            quantity=100.0,
            avg_price=100.0,
            opened_at=ist_now(),
            reentry_count=0,
            reentries=[],
            closed_at=None,
        )

        # Mock position read
        mock_positions_repo.get_by_symbol_for_update = Mock(return_value=existing_position)

        # Mock DB order
        db_order = Mock()
        db_order.entry_type = "reentry"
        db_order.order_metadata = {"rsi": 25.0, "price": 95.0, "rsi_entry_level": 25.0}
        db_order.filled_at = execution_time
        db_order.execution_time = None
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=db_order)
        mock_orders_repo.get = Mock(return_value=db_order)

        # Mock no sell order exists
        mock_sell_manager.get_existing_sell_orders = Mock(return_value={})

        # Mock transaction context manager
        mock_transaction = Mock()
        mock_transaction.__enter__ = Mock(return_value=mock_positions_repo.db)
        mock_transaction.__exit__ = Mock(return_value=False)

        with patch(
            "modules.kotak_neo_auto_trader.unified_order_monitor.transaction",
            return_value=mock_transaction,
        ):
            # Call _create_position_from_executed_order
            unified_monitor._create_position_from_executed_order(
                order_id=order_id,
                order_info={"symbol": "RELIANCE-EQ", "db_order_id": 1},
                execution_price=95.0,
                execution_qty=10.0,
            )

        # Verify: Broker API was not called (no sell order to update)
        assert (
            not mock_sell_manager.update_sell_order.called
        ), "Broker API should not be called if no sell order"
        # Verify: Position is still updated
        assert mock_positions_repo.upsert.called, "Position should still be updated"
