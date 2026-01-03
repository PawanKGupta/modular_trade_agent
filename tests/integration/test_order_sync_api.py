"""
Integration tests for manual order sync API endpoint
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from modules.kotak_neo_auto_trader.utils.order_field_extractor import (
    OrderFieldExtractor,
)
from server.app.routers.orders import sync_order_status
from src.infrastructure.db.models import OrderStatus, TradeMode


class DummyUser:
    def __init__(self, id: int):
        self.id = id


class TestOrderSyncAPI:
    """Integration tests for order sync API"""

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        self.user_id = 1
        self.user = DummyUser(id=self.user_id)
        self.db_session = MagicMock()

        # Mock settings - default to BROKER mode
        self.mock_settings = MagicMock()
        self.mock_settings.trade_mode = TradeMode.BROKER
        self.mock_settings.broker_creds_encrypted = b"encrypted_creds"

        self.mock_settings_repo = MagicMock()
        self.mock_settings_repo.get_by_user_id.return_value = self.mock_settings
        monkeypatch.setattr(
            "server.app.routers.orders.SettingsRepository",
            lambda db: self.mock_settings_repo,
        )

        # Mock broker credentials
        monkeypatch.setattr(
            "server.app.routers.orders.decrypt_broker_credentials",
            lambda creds: {"key": "val"},
        )
        monkeypatch.setattr(
            "server.app.routers.orders.create_temp_env_file", lambda creds: "/tmp/test.env"
        )
        monkeypatch.setattr("pathlib.Path.unlink", MagicMock())

        # Mock shared session manager
        self.mock_auth = MagicMock()
        self.mock_auth.is_authenticated.return_value = True
        self.mock_auth.get_client.return_value = MagicMock()

        self.mock_session_manager = MagicMock()
        self.mock_session_manager.get_or_create_session.return_value = self.mock_auth
        monkeypatch.setattr(
            "server.app.routers.orders.get_shared_session_manager",
            lambda: self.mock_session_manager,
        )

        # Mock broker
        self.mock_broker = MagicMock()
        self.mock_broker.connect.return_value = True

        monkeypatch.setattr(
            "server.app.routers.orders.BrokerFactory.create_broker",
            lambda broker_type, auth_handler: self.mock_broker,
        )

        # Mock KotakNeoOrders
        self.mock_orders_api = MagicMock()
        self.mock_orders_api.get_orders.return_value = {"data": []}
        monkeypatch.setattr(
            "server.app.routers.orders.KotakNeoOrders",
            lambda auth: self.mock_orders_api,
        )

        # Mock orders repository
        self.mock_orders_repo = MagicMock()
        self.mock_orders_repo.list.return_value = []
        self.mock_orders_repo.get.return_value = None
        monkeypatch.setattr(
            "server.app.routers.orders.OrdersRepository",
            lambda db: self.mock_orders_repo,
        )

        # Mock logger
        self.mock_logger = MagicMock()
        monkeypatch.setattr("server.app.routers.orders.logger", self.mock_logger)

        # Mock ConflictDetectionService
        self.mock_conflict_service = MagicMock()
        self.mock_conflict_service.is_unified_service_running.return_value = False
        monkeypatch.setattr(
            "server.app.routers.orders.ConflictDetectionService",
            lambda db: self.mock_conflict_service,
        )

        # Mock IndividualServiceStatusRepository
        self.mock_status_repo = MagicMock()
        self.mock_status_repo.get_by_user_and_task.return_value = None
        monkeypatch.setattr(
            "server.app.routers.orders.IndividualServiceStatusRepository",
            lambda db: self.mock_status_repo,
        )

        # Mock OrderFieldExtractor
        self.mock_order_field_extractor = MagicMock()
        self.mock_order_field_extractor.get_order_id.side_effect = lambda x: x.get("orderId")
        self.mock_order_field_extractor.get_status.side_effect = lambda x: x.get("status")
        self.mock_order_field_extractor.get_price.side_effect = lambda x: x.get("price", 0.0)
        self.mock_order_field_extractor.get_rejection_reason.side_effect = lambda x: x.get(
            "rejectionReason"
        )
        self.mock_order_field_extractor.get_filled_quantity.side_effect = lambda x: x.get(
            "quantity", 0
        )
        self.mock_order_field_extractor.get_quantity.side_effect = lambda x: x.get("quantity", 0)
        monkeypatch.setattr(
            "server.app.routers.orders.OrderFieldExtractor", self.mock_order_field_extractor
        )

    def test_manual_sync_when_monitoring_active(self, monkeypatch):
        """Test that sync endpoint returns message when monitoring is active"""
        # Ensure trade_mode is BROKER and credentials are set
        self.mock_settings.trade_mode = TradeMode.BROKER
        self.mock_settings.broker_creds_encrypted = b"encrypted_creds"

        # Mock monitoring as active
        self.mock_conflict_service.is_unified_service_running.return_value = True

        result = sync_order_status(order_id=None, db=self.db_session, current=self.user)

        assert result["sync_performed"] is False
        assert result["monitoring_active"] is True
        assert "monitoring service is active" in result["message"].lower()
        # Should not fetch broker orders
        self.mock_orders_api.get_orders.assert_not_called()

    def test_manual_sync_specific_order(self, monkeypatch):
        """Test syncing a specific order"""
        # Ensure trade_mode is BROKER and credentials are set
        self.mock_settings.trade_mode = TradeMode.BROKER
        self.mock_settings.broker_creds_encrypted = b"encrypted_creds"

        # Mock monitoring as inactive
        self.mock_conflict_service.is_unified_service_running.return_value = False
        self.mock_status_repo.get_by_user_and_task.return_value = None

        # Mock order
        mock_order = MagicMock()
        mock_order.id = 123
        mock_order.user_id = self.user_id
        mock_order.broker_order_id = "BROKER123"
        mock_order.status = OrderStatus.PENDING

        # Set up the mock repo's get method
        def mock_get(order_id):
            if order_id == 123:
                return mock_order
            return None

        self.mock_orders_repo.get = MagicMock(side_effect=mock_get)

        # Mock broker order response
        mock_broker_order = {
            "orderId": "BROKER123",
            "status": "EXECUTED",
            "price": 100.0,
            "quantity": 10,
        }
        self.mock_orders_api.get_orders.return_value = {"data": [mock_broker_order]}

        # Mock OrderFieldExtractor methods
        with (
            patch.object(OrderFieldExtractor, "get_order_id", return_value="BROKER123"),
            patch.object(OrderFieldExtractor, "get_status", return_value="EXECUTED"),
            patch.object(OrderFieldExtractor, "get_price", return_value=100.0),
            patch.object(OrderFieldExtractor, "get_filled_quantity", return_value=10),
        ):
            result = sync_order_status(order_id=123, db=self.db_session, current=self.user)

        assert result["sync_performed"] is True
        assert result["monitoring_active"] is False
        assert result["synced"] == 1
        assert result["executed"] == 1
        assert result["updated"] == 1
        # Verify mark_executed was called
        self.mock_orders_repo.mark_executed.assert_called_once()

    def test_manual_sync_all_orders(self, monkeypatch):
        """Test syncing all pending/ongoing orders"""
        # Ensure trade_mode is BROKER and credentials are set
        self.mock_settings.trade_mode = TradeMode.BROKER
        self.mock_settings.broker_creds_encrypted = b"encrypted_creds"

        # Mock monitoring as inactive
        self.mock_conflict_service.is_unified_service_running.return_value = False
        self.mock_status_repo.get_by_user_and_task.return_value = None

        # Mock orders
        mock_order1 = MagicMock()
        mock_order1.id = 1
        mock_order1.user_id = self.user_id
        mock_order1.broker_order_id = "BROKER1"
        mock_order1.status = OrderStatus.PENDING

        mock_order2 = MagicMock()
        mock_order2.id = 2
        mock_order2.user_id = self.user_id
        mock_order2.broker_order_id = "BROKER2"
        mock_order2.status = OrderStatus.ONGOING

        # Mock list to return all orders, then filter will happen in code
        all_orders = [mock_order1, mock_order2]
        # Also add some non-pending/ongoing orders that should be filtered out
        mock_order3 = MagicMock()
        mock_order3.id = 3
        mock_order3.user_id = self.user_id
        mock_order3.status = OrderStatus.CLOSED
        all_orders.append(mock_order3)

        def mock_list(user_id, status=None):
            if status is None:
                return all_orders
            return [o for o in all_orders if o.status == status]

        self.mock_orders_repo.list = MagicMock(side_effect=mock_list)

        # Mock broker orders response
        mock_broker_order1 = {
            "orderId": "BROKER1",
            "status": "REJECTED",
            "rejectionReason": "Insufficient funds",
        }
        mock_broker_order2 = {
            "orderId": "BROKER2",
            "status": "EXECUTED",
            "price": 200.0,
            "quantity": 5,
        }
        self.mock_orders_api.get_orders.return_value = {
            "data": [mock_broker_order1, mock_broker_order2]
        }

        # Mock OrderFieldExtractor - these are called as static methods in the actual code
        def get_order_id(order):
            return order.get("orderId") if isinstance(order, dict) else None

        def get_status(order):
            return order.get("status") if isinstance(order, dict) else None

        def get_price(order):
            return order.get("price", 0.0) if isinstance(order, dict) else 0.0

        def get_rejection_reason(order):
            return order.get("rejectionReason") if isinstance(order, dict) else None

        def get_filled_quantity(order):
            return order.get("quantity", 0) if isinstance(order, dict) else 0

        with (
            patch.object(OrderFieldExtractor, "get_order_id", side_effect=get_order_id),
            patch.object(OrderFieldExtractor, "get_status", side_effect=get_status),
            patch.object(OrderFieldExtractor, "get_price", side_effect=get_price),
            patch.object(
                OrderFieldExtractor, "get_rejection_reason", side_effect=get_rejection_reason
            ),
            patch.object(
                OrderFieldExtractor, "get_filled_quantity", side_effect=get_filled_quantity
            ),
        ):
            result = sync_order_status(order_id=None, db=self.db_session, current=self.user)

        assert result["sync_performed"] is True
        assert result["synced"] == 2
        assert result["rejected"] == 1
        assert result["executed"] == 1
        assert result["updated"] == 2
        # Verify both orders were updated
        assert self.mock_orders_repo.mark_rejected.call_count == 1
        assert self.mock_orders_repo.mark_executed.call_count == 1

    def test_manual_sync_paper_trading_mode(self, monkeypatch):
        """Test that sync handles paper trading mode gracefully"""
        # Mock settings as paper mode
        self.mock_settings.trade_mode = TradeMode.PAPER

        # Mock orders repository
        mock_order1 = MagicMock()
        mock_order1.id = 1
        mock_order1.user_id = self.user_id
        mock_order1.trade_mode = TradeMode.PAPER
        mock_order1.status = OrderStatus.PENDING

        mock_order2 = MagicMock()
        mock_order2.id = 2
        mock_order2.user_id = self.user_id
        mock_order2.trade_mode = TradeMode.PAPER
        mock_order2.status = OrderStatus.ONGOING

        # Add a non-paper order that should be filtered out
        mock_order3 = MagicMock()
        mock_order3.id = 3
        mock_order3.user_id = self.user_id
        mock_order3.trade_mode = TradeMode.BROKER
        mock_order3.status = OrderStatus.PENDING

        all_orders = [mock_order1, mock_order2, mock_order3]

        def mock_list(user_id, status=None):
            return all_orders if status is None else []

        self.mock_orders_repo.list = MagicMock(side_effect=mock_list)

        result = sync_order_status(order_id=None, db=self.db_session, current=self.user)

        # Paper trading should return a message that no sync is needed
        assert result["sync_performed"] is False
        assert "paper trading" in result["message"].lower()
        assert result["synced"] == 2  # Found 2 active paper orders (PENDING and ONGOING)

    def test_manual_sync_requires_broker_credentials(self, monkeypatch):
        """Test that sync requires broker credentials"""
        # Mock settings without credentials (but still in broker mode)
        self.mock_settings.trade_mode = TradeMode.BROKER
        self.mock_settings.broker_creds_encrypted = None

        with pytest.raises(HTTPException) as exc_info:
            sync_order_status(order_id=None, db=self.db_session, current=self.user)

        assert exc_info.value.status_code == 400
        assert "credentials not configured" in exc_info.value.detail.lower()

    def test_manual_sync_handles_missing_order(self, monkeypatch):
        """Test that sync handles missing order gracefully"""
        # Ensure trade_mode is BROKER and credentials are set
        self.mock_settings.trade_mode = TradeMode.BROKER
        self.mock_settings.broker_creds_encrypted = b"encrypted_creds"

        # Mock monitoring as inactive
        self.mock_conflict_service.is_unified_service_running.return_value = False
        self.mock_status_repo.get_by_user_and_task.return_value = None

        # Mock order not found
        self.mock_orders_repo.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            sync_order_status(order_id=999, db=self.db_session, current=self.user)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    def test_manual_sync_handles_broker_connection_failure(self, monkeypatch):
        """Test that sync handles broker connection failure"""
        # Ensure trade_mode is BROKER and credentials are set
        self.mock_settings.trade_mode = TradeMode.BROKER
        self.mock_settings.broker_creds_encrypted = b"encrypted_creds"

        # Mock monitoring as inactive
        self.mock_conflict_service.is_unified_service_running.return_value = False
        self.mock_status_repo.get_by_user_and_task.return_value = None

        # Mock broker connection failure
        self.mock_broker.connect.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            sync_order_status(order_id=None, db=self.db_session, current=self.user)

        assert exc_info.value.status_code == 503
        assert "failed to connect" in exc_info.value.detail.lower()
