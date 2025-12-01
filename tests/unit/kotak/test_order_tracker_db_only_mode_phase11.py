"""
Tests for Phase 11: DB-Only Mode in OrderTracker

Tests DB-only mode functionality (no JSON fallback).
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.order_tracker import OrderTracker


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    return Mock()


@pytest.fixture
def mock_orders_repo():
    """Mock OrdersRepository"""
    repo = Mock()
    repo.list = Mock(return_value=[])
    repo.get_by_broker_order_id = Mock(return_value=None)
    repo.get_by_order_id = Mock(return_value=None)
    repo.create_amo = Mock(return_value=Mock())
    repo.update = Mock()
    repo.mark_rejected = Mock()
    repo.mark_cancelled = Mock()
    return repo


@pytest.fixture
def temp_data_dir(tmp_path):
    """Temporary data directory"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return str(data_dir)


class TestOrderTrackerDBOnlyModePhase11:
    """Test Phase 11 DB-only mode"""

    def test_initialization_db_only_mode(self, mock_db_session, mock_orders_repo, temp_data_dir):
        """Test initialization with DB-only mode enabled"""
        with patch(
            "src.infrastructure.persistence.orders_repository.OrdersRepository",
            return_value=mock_orders_repo,
        ):
            tracker = OrderTracker(
                data_dir=temp_data_dir,
                db_session=mock_db_session,
                user_id=1,
                use_db=True,
                db_only_mode=True,
            )

            assert tracker.db_only_mode is True
            assert tracker.use_db is True
            assert tracker.orders_repo == mock_orders_repo

    def test_add_pending_order_db_only_mode(self, mock_db_session, mock_orders_repo, temp_data_dir):
        """Test adding pending order in DB-only mode"""
        with patch(
            "src.infrastructure.persistence.orders_repository.OrdersRepository",
            return_value=mock_orders_repo,
        ):
            from src.infrastructure.db.models import OrderStatus as DbOrderStatus

            db_order = Mock()
            db_order.status = DbOrderStatus.PENDING  # AMO merged into PENDING
            mock_orders_repo.create_amo.return_value = db_order

            tracker = OrderTracker(
                data_dir=temp_data_dir,
                db_session=mock_db_session,
                user_id=1,
                use_db=True,
                db_only_mode=True,
            )

            tracker.add_pending_order(
                order_id="ORDER123",
                symbol="RELIANCE",
                ticker="RELIANCE.NS",
                qty=10,
                order_type="MARKET",
                variety="AMO",
                price=0,
            )

            # Verify DB was called
            mock_orders_repo.create_amo.assert_called_once()

            # Verify JSON file was NOT created
            json_file = os.path.join(temp_data_dir, "pending_orders.json")
            assert not os.path.exists(json_file)

    def test_get_pending_orders_db_only_mode(self, mock_db_session, mock_orders_repo, temp_data_dir):
        """Test getting pending orders in DB-only mode"""
        with patch(
            "src.infrastructure.persistence.orders_repository.OrdersRepository",
            return_value=mock_orders_repo,
        ):
            # Mock DB order
            from src.infrastructure.db.models import OrderStatus as DbOrderStatus

            mock_db_order = Mock()
            mock_db_order.broker_order_id = "ORDER123"
            mock_db_order.order_id = None
            mock_db_order.symbol = "RELIANCE"
            mock_db_order.quantity = 10
            mock_db_order.order_type = "market"
            mock_db_order.price = None
            mock_db_order.status = DbOrderStatus.PENDING
            mock_db_order.placed_at = None
            mock_db_order.last_status_check = None
            mock_db_order.rejection_reason = None
            mock_db_order.execution_qty = None

            mock_orders_repo.list.return_value = [mock_db_order]

            tracker = OrderTracker(
                data_dir=temp_data_dir,
                db_session=mock_db_session,
                user_id=1,
                use_db=True,
                db_only_mode=True,
            )

            orders = tracker.get_pending_orders()

            # Verify DB was called
            mock_orders_repo.list.assert_called_once_with(1)

            # Verify orders were returned
            assert len(orders) == 1
            assert orders[0]["order_id"] == "ORDER123"

            # Verify JSON file was NOT read
            json_file = os.path.join(temp_data_dir, "pending_orders.json")
            if os.path.exists(json_file):
                with open(json_file, "r") as f:
                    data = json.load(f)
                    assert len(data.get("orders", [])) == 0  # Should be empty

    def test_get_pending_orders_db_only_mode_db_error(self, mock_db_session, mock_orders_repo, temp_data_dir):
        """Test getting pending orders in DB-only mode when DB fails"""
        with patch(
            "src.infrastructure.persistence.orders_repository.OrdersRepository",
            return_value=mock_orders_repo,
        ):
            mock_orders_repo.list.side_effect = Exception("DB error")

            tracker = OrderTracker(
                data_dir=temp_data_dir,
                db_session=mock_db_session,
                user_id=1,
                use_db=True,
                db_only_mode=True,
            )

            # Should return empty list (not fallback to JSON)
            orders = tracker.get_pending_orders()

            assert orders == []

    def test_update_order_status_db_only_mode(self, mock_db_session, mock_orders_repo, temp_data_dir):
        """Test updating order status in DB-only mode"""
        with patch(
            "src.infrastructure.persistence.orders_repository.OrdersRepository",
            return_value=mock_orders_repo,
        ):
            from src.infrastructure.db.models import OrderStatus as DbOrderStatus

            mock_db_order = Mock()
            mock_db_order.status = DbOrderStatus.PENDING
            mock_db_order.execution_qty = None
            mock_db_order.rejection_reason = None

            mock_orders_repo.get_by_broker_order_id.return_value = mock_db_order

            tracker = OrderTracker(
                data_dir=temp_data_dir,
                db_session=mock_db_session,
                user_id=1,
                use_db=True,
                db_only_mode=True,
            )

            result = tracker.update_order_status(order_id="ORDER123", status="EXECUTED")

            # Verify DB was called
            mock_orders_repo.get_by_broker_order_id.assert_called_once_with(1, "ORDER123")
            mock_orders_repo.update.assert_called_once()

            # Verify JSON file was NOT updated
            json_file = os.path.join(temp_data_dir, "pending_orders.json")
            if os.path.exists(json_file):
                with open(json_file, "r") as f:
                    data = json.load(f)
                    assert len(data.get("orders", [])) == 0  # Should be empty

            assert result is True

    def test_update_order_status_db_only_mode_db_error(self, mock_db_session, mock_orders_repo, temp_data_dir):
        """Test updating order status in DB-only mode when DB fails"""
        with patch(
            "src.infrastructure.persistence.orders_repository.OrdersRepository",
            return_value=mock_orders_repo,
        ):
            mock_orders_repo.get_by_broker_order_id.side_effect = Exception("DB error")

            tracker = OrderTracker(
                data_dir=temp_data_dir,
                db_session=mock_db_session,
                user_id=1,
                use_db=True,
                db_only_mode=True,
            )

            # Should raise exception (not fallback to JSON)
            with pytest.raises(Exception):
                tracker.update_order_status(order_id="ORDER123", status="EXECUTED")

    def test_remove_pending_order_db_only_mode(self, mock_db_session, mock_orders_repo, temp_data_dir):
        """Test removing pending order in DB-only mode"""
        with patch(
            "src.infrastructure.persistence.orders_repository.OrdersRepository",
            return_value=mock_orders_repo,
        ):
            mock_db_order = Mock()
            mock_orders_repo.get_by_broker_order_id.return_value = mock_db_order

            tracker = OrderTracker(
                data_dir=temp_data_dir,
                db_session=mock_db_session,
                user_id=1,
                use_db=True,
                db_only_mode=True,
            )

            result = tracker.remove_pending_order(order_id="ORDER123")

            # Verify DB was called
            mock_orders_repo.get_by_broker_order_id.assert_called_once_with(1, "ORDER123")
            mock_orders_repo.mark_cancelled.assert_called_once()

            # Verify JSON file was NOT updated
            json_file = os.path.join(temp_data_dir, "pending_orders.json")
            if os.path.exists(json_file):
                with open(json_file, "r") as f:
                    data = json.load(f)
                    assert len(data.get("orders", [])) == 0  # Should be empty

            assert result is True

    def test_remove_pending_order_db_only_mode_db_error(self, mock_db_session, mock_orders_repo, temp_data_dir):
        """Test removing pending order in DB-only mode when DB fails"""
        with patch(
            "src.infrastructure.persistence.orders_repository.OrdersRepository",
            return_value=mock_orders_repo,
        ):
            mock_orders_repo.get_by_broker_order_id.side_effect = Exception("DB error")

            tracker = OrderTracker(
                data_dir=temp_data_dir,
                db_session=mock_db_session,
                user_id=1,
                use_db=True,
                db_only_mode=True,
            )

            # Should raise exception (not fallback to JSON)
            with pytest.raises(Exception):
                tracker.remove_pending_order(order_id="ORDER123")

    def test_get_order_by_id_db_only_mode(self, mock_db_session, mock_orders_repo, temp_data_dir):
        """Test getting order by ID in DB-only mode"""
        with patch(
            "src.infrastructure.persistence.orders_repository.OrdersRepository",
            return_value=mock_orders_repo,
        ):
            from src.infrastructure.db.models import OrderStatus as DbOrderStatus

            mock_db_order = Mock()
            mock_db_order.broker_order_id = "ORDER123"
            mock_db_order.order_id = None
            mock_db_order.symbol = "RELIANCE"
            mock_db_order.quantity = 10
            mock_db_order.order_type = "market"
            mock_db_order.price = None
            mock_db_order.status = DbOrderStatus.PENDING
            mock_db_order.placed_at = None
            mock_db_order.last_status_check = None
            mock_db_order.rejection_reason = None
            mock_db_order.execution_qty = None

            mock_orders_repo.get_by_broker_order_id.return_value = mock_db_order

            tracker = OrderTracker(
                data_dir=temp_data_dir,
                db_session=mock_db_session,
                user_id=1,
                use_db=True,
                db_only_mode=True,
            )

            order = tracker.get_order_by_id(order_id="ORDER123")

            # Verify DB was called
            mock_orders_repo.get_by_broker_order_id.assert_called_once_with(1, "ORDER123")

            # Verify order was returned
            assert order is not None
            assert order["order_id"] == "ORDER123"

            # Verify JSON file was NOT read
            json_file = os.path.join(temp_data_dir, "pending_orders.json")
            if os.path.exists(json_file):
                with open(json_file, "r") as f:
                    data = json.load(f)
                    assert len(data.get("orders", [])) == 0  # Should be empty

    def test_get_order_by_id_db_only_mode_not_found(self, mock_db_session, mock_orders_repo, temp_data_dir):
        """Test getting order by ID in DB-only mode when order not found"""
        with patch(
            "src.infrastructure.persistence.orders_repository.OrdersRepository",
            return_value=mock_orders_repo,
        ):
            mock_orders_repo.get_by_broker_order_id.return_value = None
            mock_orders_repo.get_by_order_id.return_value = None

            tracker = OrderTracker(
                data_dir=temp_data_dir,
                db_session=mock_db_session,
                user_id=1,
                use_db=True,
                db_only_mode=True,
            )

            order = tracker.get_order_by_id(order_id="ORDER123")

            # Should return None (not fallback to JSON)
            assert order is None

    def test_db_only_mode_disabled_by_default(self, mock_db_session, mock_orders_repo, temp_data_dir):
        """Test that DB-only mode is disabled by default"""
        with patch(
            "src.infrastructure.persistence.orders_repository.OrdersRepository",
            return_value=mock_orders_repo,
        ):
            tracker = OrderTracker(
                data_dir=temp_data_dir,
                db_session=mock_db_session,
                user_id=1,
                use_db=True,
                # db_only_mode not specified (default: False)
            )

            assert tracker.db_only_mode is False

    def test_db_only_mode_disabled_when_db_not_available(self, temp_data_dir):
        """Test that DB-only mode is disabled when DB is not available"""
        tracker = OrderTracker(
            data_dir=temp_data_dir,
            db_session=None,
            user_id=None,
            use_db=False,
            db_only_mode=True,  # Try to enable
        )

        # Should be disabled because DB is not available
        assert tracker.db_only_mode is False

