"""
Tests for _sync_order_status_snapshot() - immediate order status sync after placement.

This tests the bug fix where we immediately fetch order status from broker
after placing an order and update the database accordingly.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

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


class TestSyncOrderStatusSnapshot:
    """Test immediate order status sync after placement"""

    def test_sync_order_status_rejected(self, auto_trade_engine):
        """Test that rejected order status is synced to DB"""
        order_id = "ORDER123"
        symbol = "RELIANCE"

        # Mock broker order response - order is rejected
        broker_order = {
            "neoOrdNo": order_id,
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "rejected",
            "transactionType": "BUY",
            "rejRsn": "Insufficient balance",
        }
        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        # Mock DB order
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.broker_order_id = order_id
        mock_db_order.status = DbOrderStatus.AMO
        auto_trade_engine.orders_repo.get_by_broker_order_id.return_value = mock_db_order
        auto_trade_engine.orders_repo.mark_rejected = Mock()

        # Call sync
        auto_trade_engine._sync_order_status_snapshot(order_id, symbol)

        # Verify mark_rejected was called
        auto_trade_engine.orders_repo.mark_rejected.assert_called_once()
        call_args = auto_trade_engine.orders_repo.mark_rejected.call_args[0]
        assert call_args[0] == mock_db_order
        assert call_args[1] == "Insufficient balance"

    def test_sync_order_status_executed(self, auto_trade_engine):
        """Test that executed order status is synced to DB"""
        order_id = "ORDER123"
        symbol = "RELIANCE"
        quantity = 10

        # Mock broker order response - order is executed
        broker_order = {
            "neoOrdNo": order_id,
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "executed",
            "transactionType": "BUY",
            "price": 2450.50,
            "quantity": quantity,
        }
        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        # Mock DB order
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.broker_order_id = order_id
        auto_trade_engine.orders_repo.get_by_broker_order_id.return_value = mock_db_order
        auto_trade_engine.orders_repo.mark_executed = Mock()

        # Call sync
        auto_trade_engine._sync_order_status_snapshot(order_id, symbol, quantity=quantity)

        # Verify mark_executed was called
        auto_trade_engine.orders_repo.mark_executed.assert_called_once()
        call_args = auto_trade_engine.orders_repo.mark_executed.call_args[1]
        assert call_args["execution_price"] == 2450.50
        assert call_args["execution_qty"] == quantity

    def test_sync_order_status_pending_execution(self, auto_trade_engine):
        """Test that pending order status is synced to PENDING_EXECUTION in DB"""
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

        # Mock DB order
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.broker_order_id = order_id
        mock_db_order.status = DbOrderStatus.AMO
        auto_trade_engine.orders_repo.get_by_broker_order_id.return_value = mock_db_order
        auto_trade_engine.orders_repo.update = Mock()

        # Call sync
        auto_trade_engine._sync_order_status_snapshot(order_id, symbol)

        # Verify update was called with PENDING_EXECUTION status
        auto_trade_engine.orders_repo.update.assert_called_once()
        call_kwargs = auto_trade_engine.orders_repo.update.call_args[1]
        assert call_kwargs["status"] == DbOrderStatus.PENDING_EXECUTION

    def test_sync_order_status_order_not_found(self, auto_trade_engine):
        """Test that sync handles order not found in broker response gracefully"""
        order_id = "ORDER123"
        symbol = "RELIANCE"

        # Mock broker order response - order not found
        auto_trade_engine.orders.get_orders.return_value = {"data": []}

        # Call sync - should not raise error
        auto_trade_engine._sync_order_status_snapshot(order_id, symbol)

        # Verify no DB operations were called
        assert not auto_trade_engine.orders_repo.mark_rejected.called
        assert not auto_trade_engine.orders_repo.mark_executed.called

    def test_sync_order_status_db_order_not_found(self, auto_trade_engine):
        """Test that sync handles DB order not found gracefully"""
        order_id = "ORDER123"
        symbol = "RELIANCE"

        # Mock broker order response
        broker_order = {
            "neoOrdNo": order_id,
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "pending",
        }
        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        # Mock DB order not found
        auto_trade_engine.orders_repo.get_by_broker_order_id.return_value = None
        auto_trade_engine.orders_repo.get_by_order_id.return_value = None

        # Call sync - should not raise error
        auto_trade_engine._sync_order_status_snapshot(order_id, symbol)

        # Verify no DB operations were called
        assert not auto_trade_engine.orders_repo.mark_rejected.called

