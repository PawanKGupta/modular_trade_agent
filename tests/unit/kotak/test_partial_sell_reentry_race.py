"""
Tests for Flaw #6: Partial Sell Execution + Reentry Race

Tests that when a partial sell executes, then a reentry happens, the sell order
quantity is updated to match the position quantity.

Scenario:
- Day 1: Partial sell executes (50 shares) → Position = 50, Sell order = 50 (remaining)
- Day 2: Reentry executes (20 shares) → Position = 70, Sell order should be updated to 70
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor


class TestPartialSellReentryRace:
    """Test that sell order quantity is synced with position after partial sell + reentry"""

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
        return positions_repo

    @pytest.fixture
    def mock_orders_repo(self, unified_monitor):
        """Mock orders repository"""
        orders_repo = Mock()
        unified_monitor.orders_repo = orders_repo
        return orders_repo

    def test_partial_sell_then_reentry_updates_sell_order(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """
        Test that after partial sell (50 shares), reentry (20 shares) updates sell order correctly.

        Scenario:
        - Initial: Position = 100, Sell order = 100
        - Partial sell: 50 shares → Position = 50, Sell order = 50 (remaining)
        - Reentry: 20 shares → Position = 70, Sell order should be updated to 70
        """
        # Setup: Existing position after partial sell (50 shares remaining)
        existing_position = Mock()
        existing_position.symbol = "RELIANCE-EQ"
        existing_position.quantity = 50.0  # After partial sell
        existing_position.avg_price = 9.00
        existing_position.opened_at = datetime.utcnow() - timedelta(days=1)
        existing_position.entry_rsi = 25.0
        existing_position.closed_at = None
        existing_position.reentry_count = 0
        existing_position.reentries = []
        existing_position.last_reentry_price = None

        mock_positions_repo.get_by_symbol_for_update = Mock(return_value=existing_position)
        mock_positions_repo.upsert = Mock(return_value=existing_position)
        mock_positions_repo.db = Mock()
        mock_positions_repo.db.refresh = Mock()

        # Mock sell order exists with quantity 50 (remaining after partial sell)
        mock_sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE-EQ": {  # Full symbol after migration
                    "order_id": "SELL123",
                    "qty": 50,  # Remaining quantity after partial sell
                    "price": 9.50,
                }
            }
        )

        # Mock order info
        order_info = {
            "symbol": "RELIANCE-EQ",
            "db_order_id": 1,
        }

        # Mock DB order with metadata
        db_order = Mock()
        db_order.symbol = "RELIANCE-EQ"
        db_order.order_metadata = {"entry_rsi": 18.0}  # Reentry at RSI 18
        db_order.filled_at = datetime.utcnow()
        db_order.execution_time = None
        mock_orders_repo.get = Mock(return_value=db_order)
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=None)
        mock_orders_repo.mark_executed = Mock(return_value=True)
        mock_orders_repo.db = Mock()

        # Mock transaction context manager
        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.transaction"):
            # Execute reentry: 20 shares @ 9.20
            unified_monitor._create_position_from_executed_order(
                order_id="BUY123",
                order_info=order_info,
                execution_price=9.20,
                execution_qty=20.0,
            )

        # Verify: Position should be updated to 70 (50 + 20)
        assert mock_positions_repo.upsert.called
        call_kwargs = mock_positions_repo.upsert.call_args[1]
        assert call_kwargs["quantity"] == 70.0  # 50 + 20

        # Verify: Sell order should be updated to match position (70)
        assert mock_sell_manager.update_sell_order.called
        update_call = mock_sell_manager.update_sell_order.call_args[1]
        assert update_call["qty"] == 70  # Should match new position quantity
        assert update_call["symbol"] == "RELIANCE-EQ"  # Full symbol after migration
        assert update_call["order_id"] == "SELL123"
        assert update_call["new_price"] == 9.50  # Price unchanged

    def test_reentry_after_partial_sell_detects_mismatch(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """
        Test that the condition correctly detects mismatch after partial sell.

        Even if new_qty (70) > existing_order_qty (50), it should still update
        because they don't match (new_qty != existing_order_qty).
        """
        # Setup: Position after partial sell
        existing_position = Mock()
        existing_position.symbol = "RELIANCE-EQ"
        existing_position.quantity = 50.0
        existing_position.avg_price = 9.00
        existing_position.opened_at = datetime.utcnow() - timedelta(days=1)
        existing_position.entry_rsi = 25.0
        existing_position.closed_at = None
        existing_position.reentry_count = 0
        existing_position.reentries = []
        existing_position.last_reentry_price = None

        mock_positions_repo.get_by_symbol_for_update = Mock(return_value=existing_position)
        mock_positions_repo.upsert = Mock(return_value=existing_position)
        mock_positions_repo.db = Mock()
        mock_positions_repo.db.refresh = Mock()

        # Sell order has 50 shares (remaining after partial sell)
        mock_sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE-EQ": {  # Full symbol after migration
                    "order_id": "SELL123",
                    "qty": 50,  # Mismatch: position will be 70 after reentry
                    "price": 9.50,
                }
            }
        )

        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}
        db_order = Mock()
        db_order.symbol = "RELIANCE-EQ"
        db_order.order_metadata = {"entry_rsi": 18.0}
        db_order.filled_at = datetime.utcnow()
        db_order.execution_time = None
        mock_orders_repo.get = Mock(return_value=db_order)
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=None)
        mock_orders_repo.mark_executed = Mock(return_value=True)
        mock_orders_repo.db = Mock()

        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.transaction"):
            unified_monitor._create_position_from_executed_order(
                order_id="BUY123",
                order_info=order_info,
                execution_price=9.20,
                execution_qty=20.0,  # Reentry: 20 shares
            )

        # Verify: Update should be called because 70 != 50 (mismatch detected)
        assert mock_sell_manager.update_sell_order.called
        update_call = mock_sell_manager.update_sell_order.call_args[1]
        assert update_call["qty"] == 70  # Updated to match position

    def test_reentry_when_quantities_match_no_update(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """
        Test that if sell order quantity already matches position, no update is needed.

        Scenario:
        - Position = 50, Sell order = 50 (already in sync)
        - Reentry: 20 shares → Position = 70
        - Sell order should be updated to 70 (mismatch detected)
        """
        # Setup: Position after partial sell
        existing_position = Mock()
        existing_position.symbol = "RELIANCE-EQ"
        existing_position.quantity = 50.0
        existing_position.avg_price = 9.00
        existing_position.opened_at = datetime.utcnow() - timedelta(days=1)
        existing_position.entry_rsi = 25.0
        existing_position.closed_at = None
        existing_position.reentry_count = 0
        existing_position.reentries = []
        existing_position.last_reentry_price = None

        mock_positions_repo.get_by_symbol_for_update = Mock(return_value=existing_position)
        mock_positions_repo.upsert = Mock(return_value=existing_position)
        mock_positions_repo.db = Mock()
        mock_positions_repo.db.refresh = Mock()

        # Sell order has 50 shares (matches current position, but will mismatch after reentry)
        mock_sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE-EQ": {  # Full symbol after migration
                    "order_id": "SELL123",
                    "qty": 50,  # Matches current position, but will be 70 after reentry
                    "price": 9.50,
                }
            }
        )

        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}
        db_order = Mock()
        db_order.symbol = "RELIANCE-EQ"
        db_order.order_metadata = {"entry_rsi": 18.0}
        db_order.filled_at = datetime.utcnow()
        db_order.execution_time = None
        mock_orders_repo.get = Mock(return_value=db_order)
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=None)
        mock_orders_repo.mark_executed = Mock(return_value=True)
        mock_orders_repo.db = Mock()

        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.transaction"):
            unified_monitor._create_position_from_executed_order(
                order_id="BUY123",
                order_info=order_info,
                execution_price=9.20,
                execution_qty=20.0,  # Reentry: 20 shares
            )

        # Verify: Update should be called because after reentry, 70 != 50
        assert mock_sell_manager.update_sell_order.called
        update_call = mock_sell_manager.update_sell_order.call_args[1]
        assert update_call["qty"] == 70  # Updated to match new position

    def test_partial_sell_reentry_with_different_quantities(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """
        Test various partial sell + reentry scenarios with different quantities.

        Scenario 1: Large partial sell, small reentry
        - Position: 100 → 30 (partial sell 70), then 30 → 40 (reentry 10)
        - Sell order: 30 → should be updated to 40
        """
        # Setup: Position after large partial sell
        existing_position = Mock()
        existing_position.symbol = "RELIANCE-EQ"
        existing_position.quantity = 30.0  # After selling 70 shares
        existing_position.avg_price = 9.00
        existing_position.opened_at = datetime.utcnow() - timedelta(days=1)
        existing_position.entry_rsi = 25.0
        existing_position.closed_at = None
        existing_position.reentry_count = 0
        existing_position.reentries = []
        existing_position.last_reentry_price = None

        mock_positions_repo.get_by_symbol_for_update = Mock(return_value=existing_position)
        mock_positions_repo.upsert = Mock(return_value=existing_position)
        mock_positions_repo.db = Mock()
        mock_positions_repo.db.refresh = Mock()

        # Sell order has 30 shares (remaining)
        mock_sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE-EQ": {  # Full symbol after migration
                    "order_id": "SELL123",
                    "qty": 30,
                    "price": 9.50,
                }
            }
        )

        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}
        db_order = Mock()
        db_order.symbol = "RELIANCE-EQ"
        db_order.order_metadata = {"entry_rsi": 18.0}
        db_order.filled_at = datetime.utcnow()
        db_order.execution_time = None
        mock_orders_repo.get = Mock(return_value=db_order)
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=None)
        mock_orders_repo.mark_executed = Mock(return_value=True)
        mock_orders_repo.db = Mock()

        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.transaction"):
            unified_monitor._create_position_from_executed_order(
                order_id="BUY123",
                order_info=order_info,
                execution_price=9.20,
                execution_qty=10.0,  # Small reentry: 10 shares
            )

        # Verify: Position updated to 40 (30 + 10)
        call_kwargs = mock_positions_repo.upsert.call_args[1]
        assert call_kwargs["quantity"] == 40.0

        # Verify: Sell order updated to 40 (to match position)
        assert mock_sell_manager.update_sell_order.called
        update_call = mock_sell_manager.update_sell_order.call_args[1]
        assert update_call["qty"] == 40

    def test_partial_sell_reentry_no_sell_order_exists(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """
        Test that if no sell order exists, no update is attempted.

        Scenario: Partial sell happened, but sell order was fully executed or cancelled.
        Reentry should still work, but no sell order update needed.
        """
        # Setup: Position after partial sell
        existing_position = Mock()
        existing_position.symbol = "RELIANCE-EQ"
        existing_position.quantity = 50.0
        existing_position.avg_price = 9.00
        existing_position.opened_at = datetime.utcnow() - timedelta(days=1)
        existing_position.entry_rsi = 25.0
        existing_position.closed_at = None
        existing_position.reentry_count = 0
        existing_position.reentries = []
        existing_position.last_reentry_price = None

        mock_positions_repo.get_by_symbol_for_update = Mock(return_value=existing_position)
        mock_positions_repo.upsert = Mock(return_value=existing_position)
        mock_positions_repo.db = Mock()
        mock_positions_repo.db.refresh = Mock()

        # No sell order exists (fully executed or cancelled)
        mock_sell_manager.get_existing_sell_orders = Mock(return_value={})

        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}
        db_order = Mock()
        db_order.symbol = "RELIANCE-EQ"
        db_order.order_metadata = {"entry_rsi": 18.0}
        db_order.filled_at = datetime.utcnow()
        db_order.execution_time = None
        mock_orders_repo.get = Mock(return_value=db_order)
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=None)
        mock_orders_repo.mark_executed = Mock(return_value=True)
        mock_orders_repo.db = Mock()

        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.transaction"):
            unified_monitor._create_position_from_executed_order(
                order_id="BUY123",
                order_info=order_info,
                execution_price=9.20,
                execution_qty=20.0,
            )

        # Verify: Position updated
        assert mock_positions_repo.upsert.called

        # Verify: No sell order update attempted (no sell order exists)
        assert not mock_sell_manager.update_sell_order.called

    def test_partial_sell_reentry_update_failure_handled_gracefully(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """
        Test that if sell order update fails, position update still succeeds.

        The position update should not fail if sell order update fails.
        """
        # Setup: Position after partial sell
        existing_position = Mock()
        existing_position.symbol = "RELIANCE-EQ"
        existing_position.quantity = 50.0
        existing_position.avg_price = 9.00
        existing_position.opened_at = datetime.utcnow() - timedelta(days=1)
        existing_position.entry_rsi = 25.0
        existing_position.closed_at = None
        existing_position.reentry_count = 0
        existing_position.reentries = []
        existing_position.last_reentry_price = None

        mock_positions_repo.get_by_symbol_for_update = Mock(return_value=existing_position)
        mock_positions_repo.upsert = Mock(return_value=existing_position)
        mock_positions_repo.db = Mock()
        mock_positions_repo.db.refresh = Mock()

        # Sell order exists
        mock_sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE-EQ": {  # Full symbol after migration
                    "order_id": "SELL123",
                    "qty": 50,
                    "price": 9.50,
                }
            }
        )

        # Sell order update fails (broker API error, etc.)
        mock_sell_manager.update_sell_order = Mock(return_value=False)

        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}
        db_order = Mock()
        db_order.symbol = "RELIANCE-EQ"
        db_order.order_metadata = {"entry_rsi": 18.0}
        db_order.filled_at = datetime.utcnow()
        db_order.execution_time = None
        mock_orders_repo.get = Mock(return_value=db_order)
        mock_orders_repo.get_by_broker_order_id = Mock(return_value=None)
        mock_orders_repo.mark_executed = Mock(return_value=True)
        mock_orders_repo.db = Mock()

        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.transaction"):
            # Should not raise exception even if sell order update fails
            unified_monitor._create_position_from_executed_order(
                order_id="BUY123",
                order_info=order_info,
                execution_price=9.20,
                execution_qty=20.0,
            )

        # Verify: Position update succeeded
        assert mock_positions_repo.upsert.called

        # Verify: Sell order update was attempted (but failed)
        assert mock_sell_manager.update_sell_order.called
