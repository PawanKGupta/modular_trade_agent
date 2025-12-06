"""
Tests for Flaw #8: Duplicate Reentry Detection Timing

Tests verify that duplicate reentry detection works correctly even when
two processes process the same order concurrently.

Scenario:
- Process A reads position, checks for duplicate (not found)
- Process B reads position, checks for duplicate (not found)
- Process A adds reentry to array
- Process B should detect duplicate during final check and skip update
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor
from src.infrastructure.db.models import Positions
from src.infrastructure.db.timezone_utils import ist_now


class TestDuplicateReentryDetectionTiming:
    """Test that duplicate reentry detection works with concurrent processing"""

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
            from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager

            manager = SellOrderManager(auth=mock_auth, history_path="test_history.json")
            manager.orders = Mock()
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
        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.DB_AVAILABLE", True):
            monitor = UnifiedOrderMonitor(
                sell_order_manager=mock_sell_manager,
                db_session=mock_db_session,
                user_id=1,
            )
            return monitor

    @pytest.fixture
    def mock_positions_repo(self, unified_monitor):
        """Create mock positions repository"""
        positions_repo = Mock()
        unified_monitor.positions_repo = positions_repo
        return positions_repo

    @pytest.fixture
    def mock_orders_repo(self, unified_monitor):
        """Create mock orders repository"""
        orders_repo = Mock()
        unified_monitor.orders_repo = orders_repo
        return orders_repo

    def test_duplicate_reentry_detected_during_final_check(
        self, unified_monitor, mock_positions_repo, mock_orders_repo
    ):
        """Test that duplicate reentry is detected during final check before update"""
        # Setup: Initial position with one reentry already added
        base_symbol = "RELIANCE"
        order_id = "REENTRY123"
        execution_time = ist_now()

        # Initial position read (stale - doesn't have the reentry yet)
        initial_position = Positions(
            user_id=1,
            symbol=base_symbol,
            quantity=100.0,
            avg_price=100.0,
            opened_at=ist_now(),
            reentry_count=0,
            reentries=[],
            closed_at=None,
        )

        # Latest position (after another process added the reentry)
        reentry_data = {
            "qty": 10,
            "price": 95.0,
            "time": execution_time.isoformat(),
            "order_id": order_id,
        }
        latest_position = Positions(
            user_id=1,
            symbol=base_symbol,
            quantity=110.0,  # Already updated by another process
            avg_price=99.5,  # Already updated by another process
            opened_at=ist_now(),
            reentry_count=1,  # Already incremented
            reentries=[reentry_data],  # Already has the reentry
            closed_at=None,
        )

        # Mock initial read (stale data)
        # First call: initial read, Second call: final check (inside transaction)
        mock_positions_repo.get_by_symbol_for_update = Mock(
            side_effect=[initial_position, latest_position]
        )

        # Mock DB order with proper datetime
        db_order = Mock()
        db_order.entry_type = "reentry"
        db_order.order_metadata = {"rsi": 25.0, "price": 95.0, "rsi_entry_level": 25.0}
        db_order.filled_at = execution_time  # Real datetime object
        db_order.execution_time = None
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=db_order)
        # Also mock get() for db_order_id lookup
        mock_orders_repo.get = Mock(return_value=db_order)

        # Mock transaction context manager
        mock_positions_repo.db = Mock()
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

        # Verify: get_by_symbol_for_update was called at least twice
        # (once for initial read, once for final check inside transaction)
        assert mock_positions_repo.get_by_symbol_for_update.call_count >= 2

        # Verify: upsert was NOT called (duplicate detected, update skipped)
        mock_positions_repo.upsert.assert_not_called()

    def test_no_duplicate_proceeds_with_update(
        self, unified_monitor, mock_positions_repo, mock_orders_repo
    ):
        """Test that if no duplicate found, update proceeds normally"""
        base_symbol = "RELIANCE"
        order_id = "REENTRY123"
        execution_time = ist_now()

        # Position without the reentry
        position = Positions(
            user_id=1,
            symbol=base_symbol,
            quantity=100.0,
            avg_price=100.0,
            opened_at=ist_now(),
            reentry_count=0,
            reentries=[],  # No reentries yet
            closed_at=None,
        )

        # Mock reads (same position both times - no concurrent update)
        mock_positions_repo.get_by_symbol_for_update = Mock(return_value=position)

        # Mock DB order with proper datetime
        db_order = Mock()
        db_order.entry_type = "reentry"
        db_order.order_metadata = {"rsi": 25.0, "price": 95.0, "rsi_entry_level": 25.0}
        db_order.filled_at = execution_time  # Real datetime object
        db_order.execution_time = None
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=db_order)

        # Mock transaction context manager
        mock_positions_repo.db = Mock()
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

        # Verify: get_by_symbol_for_update was called (for final check)
        assert mock_positions_repo.get_by_symbol_for_update.called

        # Verify: upsert was called (no duplicate, update proceeds)
        mock_positions_repo.upsert.assert_called_once()

    def test_duplicate_detected_by_order_id(
        self, unified_monitor, mock_positions_repo, mock_orders_repo
    ):
        """Test that duplicate is detected by order_id match"""
        base_symbol = "RELIANCE"
        order_id = "REENTRY123"
        execution_time = ist_now()

        initial_position = Positions(
            user_id=1,
            symbol=base_symbol,
            quantity=100.0,
            avg_price=100.0,
            opened_at=ist_now(),
            reentry_count=0,
            reentries=[],
            closed_at=None,
        )

        # Latest position has reentry with same order_id
        reentry_data = {
            "qty": 10,
            "price": 95.0,
            "time": execution_time.isoformat(),
            "order_id": order_id,  # Same order_id
        }
        latest_position = Positions(
            user_id=1,
            symbol=base_symbol,
            quantity=110.0,
            avg_price=99.5,
            opened_at=ist_now(),
            reentry_count=1,
            reentries=[reentry_data],
            closed_at=None,
        )

        mock_positions_repo.get_by_symbol_for_update = Mock(
            side_effect=[initial_position, latest_position]
        )

        db_order = Mock()
        db_order.entry_type = "reentry"
        db_order.order_metadata = {"rsi": 25.0, "price": 95.0, "rsi_entry_level": 25.0}
        db_order.filled_at = execution_time  # Real datetime object
        db_order.execution_time = None
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=db_order)
        mock_orders_repo.get = Mock(return_value=db_order)

        mock_positions_repo.db = Mock()
        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.transaction"):
            unified_monitor._create_position_from_executed_order(
                order_id=order_id,
                order_info={"symbol": "RELIANCE-EQ", "db_order_id": 1},
                execution_price=95.0,
                execution_qty=10.0,
            )

        # Verify: upsert was NOT called (duplicate detected by order_id)
        mock_positions_repo.upsert.assert_not_called()

    def test_duplicate_detected_by_timestamp_qty_price(
        self, unified_monitor, mock_positions_repo, mock_orders_repo
    ):
        """Test that duplicate is detected by timestamp, qty, and price match"""
        base_symbol = "RELIANCE"
        order_id = "REENTRY456"  # Different order_id
        execution_time = ist_now()

        initial_position = Positions(
            user_id=1,
            symbol=base_symbol,
            quantity=100.0,
            avg_price=100.0,
            opened_at=ist_now(),
            reentry_count=0,
            reentries=[],
            closed_at=None,
        )

        # Latest position has reentry with same timestamp, qty, and price (but different order_id)
        reentry_data = {
            "qty": 10,  # Same qty
            "price": 95.0,  # Same price
            "time": execution_time.isoformat(),  # Same time
            "order_id": "REENTRY123",  # Different order_id, but should still match
        }
        latest_position = Positions(
            user_id=1,
            symbol=base_symbol,
            quantity=110.0,
            avg_price=99.5,
            opened_at=ist_now(),
            reentry_count=1,
            reentries=[reentry_data],
            closed_at=None,
        )

        mock_positions_repo.get_by_symbol_for_update = Mock(
            side_effect=[initial_position, latest_position]
        )

        db_order = Mock()
        db_order.entry_type = "reentry"
        db_order.order_metadata = {"rsi": 25.0, "price": 95.0, "rsi_entry_level": 25.0}
        db_order.filled_at = execution_time  # Real datetime object
        db_order.execution_time = None
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=db_order)
        mock_orders_repo.get = Mock(return_value=db_order)

        mock_positions_repo.db = Mock()
        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.transaction"):
            unified_monitor._create_position_from_executed_order(
                order_id=order_id,
                order_info={"symbol": "RELIANCE-EQ", "db_order_id": 1},
                execution_price=95.0,  # Same price
                execution_qty=10.0,  # Same qty
            )

        # Verify: upsert was NOT called (duplicate detected by timestamp+qty+price)
        mock_positions_repo.upsert.assert_not_called()
