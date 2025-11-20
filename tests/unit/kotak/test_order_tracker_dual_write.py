#!/usr/bin/env python3
"""
Tests for OrderTracker dual-write and dual-read (Phase 7)

Tests that OrderTracker can write to both JSON and DB, and read from DB first
with JSON fallback.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
import sys

sys.path.insert(0, str(project_root))


class TestOrderTrackerDualWrite:
    """Test OrderTracker dual-write functionality"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session"""
        return MagicMock()

    @pytest.fixture
    def mock_orders_repo(self):
        """Create mock OrdersRepository"""
        repo = MagicMock()
        repo.get_by_broker_order_id = Mock(return_value=None)
        repo.get_by_order_id = Mock(return_value=None)
        repo.create_amo = Mock()
        repo.update = Mock()
        repo.list = Mock(return_value=[])
        repo.mark_rejected = Mock()
        repo.mark_cancelled = Mock()
        return repo

    @pytest.fixture
    def order_tracker_with_db(self, temp_dir, mock_db_session, mock_orders_repo):
        """Create OrderTracker with database support"""
        from modules.kotak_neo_auto_trader.order_tracker import OrderTracker

        # Create tracker - it will try to initialize OrdersRepository
        # We'll set it directly after creation
        tracker = OrderTracker(
            data_dir=temp_dir, db_session=mock_db_session, user_id=1, use_db=True
        )
        # Set mock repository directly
        tracker.orders_repo = mock_orders_repo
        tracker.use_db = True  # Ensure DB mode is enabled
        return tracker

    @pytest.fixture
    def order_tracker_json_only(self, temp_dir):
        """Create OrderTracker without database (JSON only)"""
        from modules.kotak_neo_auto_trader.order_tracker import OrderTracker

        return OrderTracker(data_dir=temp_dir, use_db=False)

    def test_add_pending_order_dual_write(self, order_tracker_with_db, mock_orders_repo):
        """Test adding pending order writes to both DB and JSON"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        mock_order = Mock()
        mock_order.id = 1
        mock_order.status = DbOrderStatus.PENDING_EXECUTION
        mock_orders_repo.create_amo.return_value = mock_order

        order_tracker_with_db.add_pending_order(
            order_id="ORDER123",
            symbol="RELIANCE",
            ticker="RELIANCE.NS",
            qty=10,
            order_type="MARKET",
            variety="AMO",
            price=0.0,
        )

        # Should write to DB
        mock_orders_repo.create_amo.assert_called_once()
        call_args = mock_orders_repo.create_amo.call_args
        assert call_args.kwargs["user_id"] == 1
        assert call_args.kwargs["symbol"] == "RELIANCE"
        assert call_args.kwargs["quantity"] == 10

        # Should also write to JSON
        json_file = os.path.join(order_tracker_with_db.data_dir, "pending_orders.json")
        assert os.path.exists(json_file)
        with open(json_file) as f:
            data = json.load(f)
            assert len(data["orders"]) == 1
            assert data["orders"][0]["order_id"] == "ORDER123"

    def test_add_pending_order_json_only(self, order_tracker_json_only):
        """Test adding pending order with JSON only (no DB)"""
        order_tracker_json_only.add_pending_order(
            order_id="ORDER123",
            symbol="RELIANCE",
            ticker="RELIANCE.NS",
            qty=10,
        )

        # Should write to JSON
        json_file = os.path.join(order_tracker_json_only.data_dir, "pending_orders.json")
        assert os.path.exists(json_file)
        with open(json_file) as f:
            data = json.load(f)
            assert len(data["orders"]) == 1
            assert data["orders"][0]["order_id"] == "ORDER123"

    def test_add_pending_order_duplicate_prevention(self, order_tracker_with_db, mock_orders_repo):
        """Test that duplicate orders are prevented in both DB and JSON"""

        # Mock existing order in DB
        mock_existing = Mock()
        mock_existing.id = 1
        mock_orders_repo.get_by_broker_order_id.return_value = mock_existing

        order_tracker_with_db.add_pending_order(
            order_id="ORDER123", symbol="RELIANCE", ticker="RELIANCE.NS", qty=10
        )

        # Should not create new order in DB
        mock_orders_repo.create_amo.assert_not_called()

        # Should not add to JSON either (checked in JSON path)
        json_file = os.path.join(order_tracker_with_db.data_dir, "pending_orders.json")
        with open(json_file) as f:
            data = json.load(f)
            # Order should not be added since it exists in DB

    def test_get_pending_orders_dual_read(self, order_tracker_with_db, mock_orders_repo):
        """Test getting pending orders reads from DB first"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock DB orders
        mock_order = Mock()
        mock_order.broker_order_id = "ORDER123"
        mock_order.order_id = "ORDER123"
        mock_order.symbol = "RELIANCE"
        mock_order.quantity = 10
        mock_order.price = 2450.0
        mock_order.order_type = "market"
        mock_order.status = DbOrderStatus.PENDING_EXECUTION
        mock_order.placed_at = datetime.now()
        mock_order.last_status_check = datetime.now()
        mock_order.rejection_reason = None
        mock_order.execution_qty = None
        mock_orders_repo.list.return_value = [mock_order]

        orders = order_tracker_with_db.get_pending_orders()

        # Should read from DB
        assert len(orders) == 1
        assert orders[0]["order_id"] == "ORDER123"
        assert orders[0]["symbol"] == "RELIANCE"
        mock_orders_repo.list.assert_called_once_with(1)

    def test_get_pending_orders_json_fallback(self, order_tracker_with_db, mock_orders_repo):
        """Test that JSON is used as fallback when DB fails"""
        # Mock DB to fail
        mock_orders_repo.list.side_effect = Exception("DB error")

        # Add order to JSON manually
        json_file = os.path.join(order_tracker_with_db.data_dir, "pending_orders.json")
        with open(json_file, "w") as f:
            json.dump(
                {
                    "orders": [
                        {
                            "order_id": "ORDER123",
                            "symbol": "RELIANCE",
                            "ticker": "RELIANCE.NS",
                            "qty": 10,
                            "status": "PENDING",
                        }
                    ]
                },
                f,
            )

        orders = order_tracker_with_db.get_pending_orders()

        # Should fallback to JSON
        assert len(orders) == 1
        assert orders[0]["order_id"] == "ORDER123"

    def test_get_pending_orders_json_only(self, order_tracker_json_only):
        """Test getting pending orders with JSON only"""
        # Add order to JSON
        order_tracker_json_only.add_pending_order(
            order_id="ORDER123", symbol="RELIANCE", ticker="RELIANCE.NS", qty=10
        )

        orders = order_tracker_json_only.get_pending_orders()

        assert len(orders) == 1
        assert orders[0]["order_id"] == "ORDER123"

    def test_update_order_status_dual_write(self, order_tracker_with_db, mock_orders_repo):
        """Test updating order status writes to both DB and JSON"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Add order first
        mock_order = Mock()
        mock_order.id = 1
        mock_order.broker_order_id = "ORDER123"
        mock_order.status = DbOrderStatus.PENDING_EXECUTION
        mock_order.execution_qty = None
        mock_order.rejection_reason = None
        mock_order.last_status_check = None
        mock_orders_repo.get_by_broker_order_id.return_value = mock_order
        mock_orders_repo.create_amo.return_value = mock_order

        order_tracker_with_db.add_pending_order(
            order_id="ORDER123", symbol="RELIANCE", ticker="RELIANCE.NS", qty=10
        )

        # Update status
        result = order_tracker_with_db.update_order_status(
            order_id="ORDER123", status="EXECUTED", executed_qty=10
        )

        # Should update in DB
        assert result is True
        mock_orders_repo.update.assert_called()
        # EXECUTED status maps to ONGOING in DB
        assert mock_order.status == DbOrderStatus.ONGOING
        assert mock_order.execution_qty == 10

        # Should also update JSON
        json_file = os.path.join(order_tracker_with_db.data_dir, "pending_orders.json")
        with open(json_file) as f:
            data = json.load(f)
            assert data["orders"][0]["status"] == "EXECUTED"
            assert data["orders"][0]["executed_qty"] == 10

    def test_get_order_by_id_dual_read(self, order_tracker_with_db, mock_orders_repo):
        """Test getting order by ID reads from DB first"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock DB order
        mock_order = Mock()
        mock_order.broker_order_id = "ORDER123"
        mock_order.order_id = "ORDER123"
        mock_order.symbol = "RELIANCE"
        mock_order.quantity = 10
        mock_order.price = 2450.0
        mock_order.order_type = "market"
        mock_order.status = DbOrderStatus.PENDING_EXECUTION
        mock_order.placed_at = datetime.now()
        mock_order.last_status_check = datetime.now()
        mock_order.rejection_reason = None
        mock_order.execution_qty = None
        mock_orders_repo.get_by_broker_order_id.return_value = mock_order

        order = order_tracker_with_db.get_order_by_id("ORDER123")

        # Should read from DB
        assert order is not None
        assert order["order_id"] == "ORDER123"
        mock_orders_repo.get_by_broker_order_id.assert_called_once_with(1, "ORDER123")

    def test_remove_pending_order_dual_write(self, order_tracker_with_db, mock_orders_repo):
        """Test removing order writes to both DB and JSON"""

        # Add order first
        mock_order = Mock()
        mock_order.id = 1
        mock_order.broker_order_id = "ORDER123"
        mock_orders_repo.get_by_broker_order_id.return_value = mock_order
        mock_orders_repo.create_amo.return_value = mock_order

        order_tracker_with_db.add_pending_order(
            order_id="ORDER123", symbol="RELIANCE", ticker="RELIANCE.NS", qty=10
        )

        # Remove order
        result = order_tracker_with_db.remove_pending_order("ORDER123")

        # Should mark as closed in DB
        assert result is True
        mock_orders_repo.mark_cancelled.assert_called_once()

        # Should also remove from JSON
        json_file = os.path.join(order_tracker_with_db.data_dir, "pending_orders.json")
        with open(json_file) as f:
            data = json.load(f)
            assert len(data["orders"]) == 0

    def test_get_pending_orders_status_filter(self, order_tracker_with_db, mock_orders_repo):
        """Test status filtering works with DB orders"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock orders with different statuses
        mock_order1 = Mock()
        mock_order1.broker_order_id = "ORDER1"
        mock_order1.order_id = "ORDER1"
        mock_order1.symbol = "RELIANCE"
        mock_order1.quantity = 10
        mock_order1.price = 2450.0
        mock_order1.order_type = "market"
        mock_order1.status = DbOrderStatus.PENDING_EXECUTION
        mock_order1.placed_at = datetime.now()
        mock_order1.last_status_check = datetime.now()
        mock_order1.rejection_reason = None
        mock_order1.execution_qty = None

        mock_order2 = Mock()
        mock_order2.broker_order_id = "ORDER2"
        mock_order2.order_id = "ORDER2"
        mock_order2.symbol = "TCS"
        mock_order2.quantity = 5
        mock_order2.price = 3200.0
        mock_order2.order_type = "market"
        mock_order2.status = DbOrderStatus.ONGOING
        mock_order2.placed_at = datetime.now()
        mock_order2.last_status_check = datetime.now()
        mock_order2.rejection_reason = None
        mock_order2.execution_qty = None

        mock_orders_repo.list.return_value = [mock_order1, mock_order2]

        # Filter by PENDING status
        orders = order_tracker_with_db.get_pending_orders(status_filter="PENDING")

        # Should only return PENDING orders
        assert len(orders) == 1
        assert orders[0]["order_id"] == "ORDER1"
        assert orders[0]["status"] == "pending_execution"

    def test_get_pending_orders_symbol_filter(self, order_tracker_with_db, mock_orders_repo):
        """Test symbol filtering works with DB orders"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock orders for different symbols
        mock_order1 = Mock()
        mock_order1.broker_order_id = "ORDER1"
        mock_order1.order_id = "ORDER1"
        mock_order1.symbol = "RELIANCE"
        mock_order1.quantity = 10
        mock_order1.price = 2450.0
        mock_order1.order_type = "market"
        mock_order1.status = DbOrderStatus.PENDING_EXECUTION
        mock_order1.placed_at = datetime.now()
        mock_order1.last_status_check = datetime.now()
        mock_order1.rejection_reason = None
        mock_order1.execution_qty = None

        mock_order2 = Mock()
        mock_order2.broker_order_id = "ORDER2"
        mock_order2.order_id = "ORDER2"
        mock_order2.symbol = "TCS"
        mock_order2.quantity = 5
        mock_order2.price = 3200.0
        mock_order2.order_type = "market"
        mock_order2.status = DbOrderStatus.PENDING_EXECUTION
        mock_order2.placed_at = datetime.now()
        mock_order2.last_status_check = datetime.now()
        mock_order2.rejection_reason = None
        mock_order2.execution_qty = None

        mock_orders_repo.list.return_value = [mock_order1, mock_order2]

        # Filter by symbol
        orders = order_tracker_with_db.get_pending_orders(symbol_filter="RELIANCE")

        # Should only return RELIANCE orders
        assert len(orders) == 1
        assert orders[0]["symbol"] == "RELIANCE"

    def test_update_order_status_rejected(self, order_tracker_with_db, mock_orders_repo):
        """Test updating order status to REJECTED updates DB correctly"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock existing order
        mock_order = Mock()
        mock_order.id = 1
        mock_order.broker_order_id = "ORDER123"
        mock_order.status = DbOrderStatus.PENDING_EXECUTION
        mock_order.execution_qty = None
        mock_order.rejection_reason = None
        mock_order.last_status_check = None
        mock_orders_repo.get_by_broker_order_id.return_value = mock_order

        result = order_tracker_with_db.update_order_status(
            order_id="ORDER123", status="REJECTED", rejection_reason="Insufficient balance"
        )

        # Should mark as rejected in DB
        assert result is True
        mock_orders_repo.mark_rejected.assert_called_once()
        call_args = mock_orders_repo.mark_rejected.call_args
        # mark_rejected takes order as first positional arg, rejection_reason as second
        assert call_args[0][0] == mock_order
        assert call_args[0][1] == "Insufficient balance"

    def test_add_pending_order_db_error_handling(self, order_tracker_with_db, mock_orders_repo):
        """Test that DB errors don't prevent JSON write"""
        # Mock DB to fail
        mock_orders_repo.create_amo.side_effect = Exception("DB error")

        # Should still write to JSON
        order_tracker_with_db.add_pending_order(
            order_id="ORDER123", symbol="RELIANCE", ticker="RELIANCE.NS", qty=10
        )

        json_file = os.path.join(order_tracker_with_db.data_dir, "pending_orders.json")
        assert os.path.exists(json_file)
        with open(json_file) as f:
            data = json.load(f)
            assert len(data["orders"]) == 1

    def test_get_pending_orders_empty_db(self, order_tracker_with_db, mock_orders_repo):
        """Test that empty DB returns empty (doesn't fallback to JSON)"""
        # Mock empty DB
        mock_orders_repo.list.return_value = []

        orders = order_tracker_with_db.get_pending_orders()

        # Should return empty (DB is the source of truth when available)
        assert len(orders) == 0
        mock_orders_repo.list.assert_called_once()

    def test_get_order_by_id_json_fallback(self, order_tracker_with_db, mock_orders_repo):
        """Test that get_order_by_id falls back to JSON when DB fails"""
        # Mock DB to fail
        mock_orders_repo.get_by_broker_order_id.side_effect = Exception("DB error")
        mock_orders_repo.get_by_order_id.side_effect = Exception("DB error")

        # Add order to JSON
        json_file = os.path.join(order_tracker_with_db.data_dir, "pending_orders.json")
        with open(json_file, "w") as f:
            json.dump(
                {
                    "orders": [
                        {
                            "order_id": "ORDER123",
                            "symbol": "RELIANCE",
                            "ticker": "RELIANCE.NS",
                            "qty": 10,
                            "status": "PENDING",
                        }
                    ]
                },
                f,
            )

        order = order_tracker_with_db.get_order_by_id("ORDER123")

        # Should fallback to JSON
        assert order is not None
        assert order["order_id"] == "ORDER123"

    def test_update_order_status_json_only(self, order_tracker_json_only):
        """Test updating order status with JSON only"""
        # Add order first
        order_tracker_json_only.add_pending_order(
            order_id="ORDER123", symbol="RELIANCE", ticker="RELIANCE.NS", qty=10
        )

        # Update status
        result = order_tracker_json_only.update_order_status(
            order_id="ORDER123", status="EXECUTED", executed_qty=10
        )

        assert result is True

        # Check JSON was updated
        json_file = os.path.join(order_tracker_json_only.data_dir, "pending_orders.json")
        with open(json_file) as f:
            data = json.load(f)
            assert data["orders"][0]["status"] == "EXECUTED"
            assert data["orders"][0]["executed_qty"] == 10

    def test_update_order_status_not_found(self, order_tracker_with_db, mock_orders_repo):
        """Test updating order status when order not found"""
        # Mock order not found in DB
        mock_orders_repo.get_by_broker_order_id.return_value = None
        mock_orders_repo.get_by_order_id.return_value = None

        result = order_tracker_with_db.update_order_status(order_id="ORDER123", status="EXECUTED")

        # Should return False (not found)
        assert result is False

    def test_remove_pending_order_not_found(self, order_tracker_with_db, mock_orders_repo):
        """Test removing order when not found"""
        # Mock no orders in DB
        mock_orders_repo.list.return_value = []

        result = order_tracker_with_db.remove_pending_order("ORDER123")

        # Should return False (not found)
        assert result is False
        mock_orders_repo.mark_cancelled.assert_not_called()

    def test_get_pending_orders_status_filter_pending(
        self, order_tracker_with_db, mock_orders_repo
    ):
        """Test status filter with PENDING status"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock order with PENDING_EXECUTION status
        mock_order = Mock()
        mock_order.broker_order_id = "ORDER1"
        mock_order.order_id = "ORDER1"
        mock_order.symbol = "RELIANCE"
        mock_order.quantity = 10
        mock_order.price = 2450.0
        mock_order.order_type = "market"
        mock_order.status = DbOrderStatus.PENDING_EXECUTION
        mock_order.placed_at = datetime.now()
        mock_order.last_status_check = datetime.now()
        mock_order.rejection_reason = None
        mock_order.execution_qty = None

        mock_orders_repo.list.return_value = [mock_order]

        orders = order_tracker_with_db.get_pending_orders(status_filter="PENDING")

        assert len(orders) == 1
        assert orders[0]["status"] == "pending_execution"

    def test_get_pending_orders_status_filter_open(self, order_tracker_with_db, mock_orders_repo):
        """Test status filter with OPEN status"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock order with PENDING_EXECUTION status (OPEN = placed but not executed yet)
        mock_order = Mock()
        mock_order.broker_order_id = "ORDER1"
        mock_order.order_id = "ORDER1"
        mock_order.symbol = "RELIANCE"
        mock_order.quantity = 10
        mock_order.price = 2450.0
        mock_order.order_type = "market"
        mock_order.status = DbOrderStatus.PENDING_EXECUTION
        mock_order.placed_at = datetime.now()
        mock_order.last_status_check = datetime.now()
        mock_order.rejection_reason = None
        mock_order.execution_qty = None

        mock_orders_repo.list.return_value = [mock_order]

        orders = order_tracker_with_db.get_pending_orders(status_filter="OPEN")

        assert len(orders) == 1
        assert orders[0]["status"] == "pending_execution"

    def test_update_order_status_cancelled(self, order_tracker_with_db, mock_orders_repo):
        """Test updating order status to CANCELLED"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock existing order
        mock_order = Mock()
        mock_order.id = 1
        mock_order.broker_order_id = "ORDER123"
        mock_order.status = DbOrderStatus.PENDING_EXECUTION
        mock_order.execution_qty = None
        mock_order.rejection_reason = None
        mock_order.last_status_check = None
        mock_orders_repo.get_by_broker_order_id.return_value = mock_order

        result = order_tracker_with_db.update_order_status(order_id="ORDER123", status="CANCELLED")

        # Should update in DB
        assert result is True
        mock_orders_repo.update.assert_called_once()
        assert mock_order.status == DbOrderStatus.CLOSED

    def test_add_pending_order_existing_in_json(self, order_tracker_with_db, mock_orders_repo):
        """Test that existing order in JSON still syncs to DB (dual-write sync)"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Add order to JSON first
        json_file = os.path.join(order_tracker_with_db.data_dir, "pending_orders.json")
        with open(json_file, "w") as f:
            json.dump(
                {
                    "orders": [
                        {
                            "order_id": "ORDER123",
                            "symbol": "RELIANCE",
                            "ticker": "RELIANCE.NS",
                            "qty": 10,
                            "status": "PENDING",
                        }
                    ]
                },
                f,
            )

        # Mock order not in DB
        mock_orders_repo.get_by_broker_order_id.return_value = None
        mock_orders_repo.get_by_order_id.return_value = None
        mock_new_order = Mock()
        mock_new_order.id = 1
        mock_new_order.status = DbOrderStatus.PENDING_EXECUTION
        mock_orders_repo.create_amo.return_value = mock_new_order

        # Try to add same order
        order_tracker_with_db.add_pending_order(
            order_id="ORDER123", symbol="RELIANCE", ticker="RELIANCE.NS", qty=10
        )

        # Should still create in DB (syncs JSON to DB in dual-write mode)
        # But JSON add should be skipped
        mock_orders_repo.create_amo.assert_called_once()

    def test_get_pending_orders_db_exception_fallback(
        self, order_tracker_with_db, mock_orders_repo
    ):
        """Test that JSON fallback works when DB raises exception"""
        # Mock DB to raise exception
        mock_orders_repo.list.side_effect = Exception("DB connection error")

        # Add order to JSON
        json_file = os.path.join(order_tracker_with_db.data_dir, "pending_orders.json")
        with open(json_file, "w") as f:
            json.dump(
                {
                    "orders": [
                        {
                            "order_id": "ORDER123",
                            "symbol": "RELIANCE",
                            "ticker": "RELIANCE.NS",
                            "qty": 10,
                            "status": "PENDING",
                        }
                    ]
                },
                f,
            )

        orders = order_tracker_with_db.get_pending_orders()

        # Should fallback to JSON
        assert len(orders) == 1
        assert orders[0]["order_id"] == "ORDER123"
