"""
Additional tests for _sync_order_status_snapshot() to reach >80% coverage.

Tests edge cases and uncovered lines.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
from src.infrastructure.db.models import OrderStatus as DbOrderStatus


@pytest.fixture
def auto_trade_engine():
    """Create AutoTradeEngine instance with mocked dependencies"""
    with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"):
        engine = AutoTradeEngine(
            enable_verifier=False,
            enable_telegram=False,
            user_id=1,
            db_session=MagicMock(),
        )
        engine.orders = Mock()
        engine.orders_repo = Mock()
        engine.user_id = 1
        return engine


class TestSyncOrderStatusSnapshotCoverage:
    """Additional tests for _sync_order_status_snapshot edge cases"""

    def test_sync_order_status_cancelled(self, auto_trade_engine):
        """Test that cancelled order status is synced to DB"""
        order_id = "ORDER123"
        symbol = "RELIANCE"

        # Mock broker order response - order is cancelled
        broker_order = {
            "neoOrdNo": order_id,
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "cancelled",
            "transactionType": "BUY",
            "rejRsn": "User cancelled",
        }
        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        # Mock DB order
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.broker_order_id = order_id
        auto_trade_engine.orders_repo.get_by_broker_order_id.return_value = mock_db_order
        auto_trade_engine.orders_repo.mark_cancelled = Mock()

        # Call sync
        auto_trade_engine._sync_order_status_snapshot(order_id, symbol)

        # Verify mark_cancelled was called
        auto_trade_engine.orders_repo.mark_cancelled.assert_called_once()
        call_args = auto_trade_engine.orders_repo.mark_cancelled.call_args[0]
        assert call_args[0] == mock_db_order
        assert call_args[1] == "User cancelled"

    def test_sync_order_status_partially_filled(self, auto_trade_engine):
        """Test that partially filled order status is synced to PENDING"""
        order_id = "ORDER123"
        symbol = "RELIANCE"

        # Mock broker order response - order is partially filled
        broker_order = {
            "neoOrdNo": order_id,
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "partially_filled",
            "transactionType": "BUY",
        }
        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        # Mock DB order
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.broker_order_id = order_id
        mock_db_order.status = DbOrderStatus.ONGOING  # Start with different status to test transition
        auto_trade_engine.orders_repo.get_by_broker_order_id.return_value = mock_db_order
        auto_trade_engine.orders_repo.update = Mock()

        # Call sync
        auto_trade_engine._sync_order_status_snapshot(order_id, symbol)

        # Verify update was called with PENDING status
        auto_trade_engine.orders_repo.update.assert_called_once()
        call_kwargs = auto_trade_engine.orders_repo.update.call_args[1]
        assert call_kwargs["status"] == DbOrderStatus.PENDING

    def test_sync_order_status_trigger_pending(self, auto_trade_engine):
        """Test that trigger_pending order status is synced to PENDING"""
        order_id = "ORDER123"
        symbol = "RELIANCE"

        # Mock broker order response - order is trigger_pending
        broker_order = {
            "neoOrdNo": order_id,
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "trigger_pending",
            "transactionType": "BUY",
        }
        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        # Mock DB order
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.broker_order_id = order_id
        mock_db_order.status = DbOrderStatus.ONGOING  # Start with different status to test transition
        auto_trade_engine.orders_repo.get_by_broker_order_id.return_value = mock_db_order
        auto_trade_engine.orders_repo.update = Mock()

        # Call sync
        auto_trade_engine._sync_order_status_snapshot(order_id, symbol)

        # Verify update was called
        auto_trade_engine.orders_repo.update.assert_called_once()

    def test_sync_order_status_already_pending_execution(self, auto_trade_engine):
        """Test that order already in PENDING status is not updated again"""
        order_id = "ORDER123"
        symbol = "RELIANCE"

        # Mock broker order response - order is pending
        broker_order = {
            "neoOrdNo": order_id,
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "pending",
            "transactionType": "BUY",
        }
        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        # Mock DB order already in PENDING
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.broker_order_id = order_id
        mock_db_order.status = DbOrderStatus.PENDING  # Already in this status
        auto_trade_engine.orders_repo.get_by_broker_order_id.return_value = mock_db_order
        auto_trade_engine.orders_repo.update = Mock()

        # Call sync
        auto_trade_engine._sync_order_status_snapshot(order_id, symbol)

        # Verify update was NOT called (already in correct status)
        auto_trade_engine.orders_repo.update.assert_not_called()

    def test_sync_order_status_empty_status(self, auto_trade_engine):
        """Test that empty status is handled gracefully"""
        order_id = "ORDER123"
        symbol = "RELIANCE"

        # Mock broker order response - empty status
        broker_order = {
            "neoOrdNo": order_id,
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "",
            "transactionType": "BUY",
        }
        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        # Mock DB order
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.broker_order_id = order_id
        auto_trade_engine.orders_repo.get_by_broker_order_id.return_value = mock_db_order

        # Call sync - should not raise error
        auto_trade_engine._sync_order_status_snapshot(order_id, symbol)

        # Verify no DB operations were called
        assert not auto_trade_engine.orders_repo.mark_rejected.called
        assert not auto_trade_engine.orders_repo.mark_executed.called

    def test_sync_order_status_no_orders_repo(self, auto_trade_engine):
        """Test that sync handles missing orders_repo gracefully"""
        order_id = "ORDER123"
        symbol = "RELIANCE"

        # Remove orders_repo
        auto_trade_engine.orders_repo = None

        # Call sync - should not raise error
        auto_trade_engine._sync_order_status_snapshot(order_id, symbol)

        # Should return early without error
        assert True

    def test_sync_order_status_fallback_to_get_by_order_id(self, auto_trade_engine):
        """Test that sync falls back to get_by_order_id if get_by_broker_order_id fails"""
        order_id = "ORDER123"
        symbol = "RELIANCE"

        # Mock broker order response
        broker_order = {
            "neoOrdNo": order_id,
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "pending",
            "transactionType": "BUY",
        }
        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        # Mock get_by_broker_order_id returns None, get_by_order_id returns order
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.broker_order_id = order_id
        mock_db_order.status = DbOrderStatus.ONGOING  # Start with different status to test transition
        auto_trade_engine.orders_repo.get_by_broker_order_id.return_value = None
        auto_trade_engine.orders_repo.get_by_order_id.return_value = mock_db_order
        auto_trade_engine.orders_repo.update = Mock()

        # Call sync
        auto_trade_engine._sync_order_status_snapshot(order_id, symbol)

        # Verify both methods were tried
        auto_trade_engine.orders_repo.get_by_broker_order_id.assert_called_once()
        auto_trade_engine.orders_repo.get_by_order_id.assert_called_once()
        # Verify update was called
        auto_trade_engine.orders_repo.update.assert_called_once()

