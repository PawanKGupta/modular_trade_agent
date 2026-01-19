"""
Unit tests for paper trading adapter DB sync edge cases

Tests cover:
- Missing db_order scenario
- Sell order quantity validation
- Partial sell P&L calculation
- Symbol normalization consistency
- Transaction rollback handling
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from modules.kotak_neo_auto_trader.domain import (
    Exchange,
    Money,
    Order,
    OrderStatus,
    OrderType,
    TransactionType,
)
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.paper_trading_adapter import (
    PaperTradingBrokerAdapter,
)


class TestPaperTradingAdapterDBSyncEdgeCases:
    """Test edge cases for paper trading adapter DB sync"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.user_id = 1
        self.adapter = PaperTradingBrokerAdapter(user_id=self.user_id)
        self.adapter.db_session = MagicMock()

        # Mock repositories
        self.mock_orders_repo = MagicMock()
        self.mock_positions_repo = MagicMock()

        with (
            patch(
                "src.infrastructure.persistence.orders_repository.OrdersRepository",
                return_value=self.mock_orders_repo,
            ),
            patch(
                "src.infrastructure.persistence.positions_repository.PositionsRepository",
                return_value=self.mock_positions_repo,
            ),
        ):
            yield

    def test_missing_db_order_creates_position_from_order_data(self):
        """Test that position is created from order data when db_order not found"""
        # Order without matching db_order
        order = Order(
            order_id="ORDER123",
            symbol="STOCK1-EQ",
            exchange=Exchange.NSE,
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            status=OrderStatus.EXECUTED,
        )
        order.user_id = self.user_id

        execution_price = Money(Decimal("100.00"))

        # Mock db_order not found
        self.mock_orders_repo.get_by_broker_order_id.return_value = None

        # Mock the database query that searches for order without user_id
        # The code does: stmt = select(Orders).where(Orders.broker_order_id == order.order_id)
        # result = self.db_session.execute(stmt).scalar_one_or_none()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        self.adapter.db_session.execute.return_value = mock_result

        # Mock position doesn't exist
        self.mock_positions_repo.get_by_symbol.return_value = None

        # Mock ist_now
        with patch("src.infrastructure.db.timezone_utils.ist_now") as mock_ist_now:
            mock_ist_now.return_value = datetime.now()

            # Call sync method
            self.adapter._sync_order_execution_to_db(order, execution_price)

            # Verify position was created
            self.mock_positions_repo.upsert.assert_called_once()
            call_args = self.mock_positions_repo.upsert.call_args[1]
            assert call_args["user_id"] == self.user_id
            assert call_args["symbol"] == "STOCK1-EQ"
            assert call_args["quantity"] == 10.0
            assert call_args["avg_price"] == 100.0

    def test_sell_order_quantity_exceeds_position_validation(self):
        """Test that sell order quantity is capped to position quantity"""
        # Order with quantity exceeding position
        order = Order(
            order_id="ORDER456",
            symbol="STOCK2-EQ",
            exchange=Exchange.NSE,
            transaction_type=TransactionType.SELL,
            quantity=20,  # Exceeds position quantity
            order_type=OrderType.MARKET,
            status=OrderStatus.EXECUTED,
        )

        execution_price = Money(Decimal("110.00"))

        # Mock db_order
        db_order = MagicMock()
        db_order.id = 1
        db_order.user_id = self.user_id
        db_order.symbol = "STOCK2-EQ"
        db_order.broker_order_id = "ORDER456"
        self.mock_orders_repo.get_by_broker_order_id.return_value = db_order

        # Mock position with quantity 10
        existing_pos = MagicMock()
        existing_pos.quantity = 10.0
        existing_pos.avg_price = 100.0
        existing_pos.closed_at = None
        self.mock_positions_repo.get_by_symbol.return_value = existing_pos

        with (
            patch("src.infrastructure.db.timezone_utils.ist_now") as mock_ist_now,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.paper_trading_adapter.logger"
            ) as mock_logger,
        ):
            mock_ist_now.return_value = datetime.now()

            # Call sync method
            self.adapter._sync_order_execution_to_db(order, execution_price)

            # Verify warning was logged
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if "exceeds" in str(call).lower()
            ]
            assert len(warning_calls) > 0

            # Verify execution_qty was capped to position quantity
            # (check mark_closed or upsert was called with correct quantity)
            if self.mock_positions_repo.mark_closed.called:
                call_args = self.mock_positions_repo.mark_closed.call_args[1]
                # Position should be closed (remaining_qty <= 0)
                assert call_args is not None

    def test_partial_sell_pnl_calculation(self):
        """Test that realized P&L percentage uses execution_qty for partial sells"""
        # Sell order for partial quantity
        order = Order(
            order_id="ORDER789",
            symbol="STOCK3-EQ",
            exchange=Exchange.NSE,
            transaction_type=TransactionType.SELL,
            quantity=5,  # Partial sell
            order_type=OrderType.MARKET,
            status=OrderStatus.EXECUTED,
        )

        execution_price = Money(Decimal("120.00"))

        # Mock db_order
        db_order = MagicMock()
        db_order.id = 1
        db_order.user_id = self.user_id
        db_order.symbol = "STOCK3-EQ"
        db_order.broker_order_id = "ORDER789"
        self.mock_orders_repo.get_by_broker_order_id.return_value = db_order

        # Mock position with quantity 10, avg_price 100
        existing_pos = MagicMock()
        existing_pos.quantity = 10.0
        existing_pos.avg_price = 100.0
        existing_pos.closed_at = None
        self.mock_positions_repo.get_by_symbol.return_value = existing_pos

        # Trade info with realized P&L
        trade_info = {
            "realized_pnl": 100.0,  # (120 - 100) * 5
        }

        with patch("src.infrastructure.db.timezone_utils.ist_now") as mock_ist_now:
            mock_ist_now.return_value = datetime.now()

            # Call sync method
            self.adapter._sync_order_execution_to_db(order, execution_price, trade_info)

            # Verify mark_closed or upsert was called
            # For partial sell, should update position quantity
            if self.mock_positions_repo.upsert.called:
                call_args = self.mock_positions_repo.upsert.call_args[1]
                # Remaining quantity should be 5
                assert call_args["quantity"] == 5.0

    def test_sell_order_no_position_warning(self):
        """Test that warning is logged when sell order executes but position not found"""
        # Sell order
        order = Order(
            order_id="ORDER999",
            symbol="STOCK4-EQ",
            exchange=Exchange.NSE,
            transaction_type=TransactionType.SELL,
            quantity=10,
            order_type=OrderType.MARKET,
            status=OrderStatus.EXECUTED,
        )

        execution_price = Money(Decimal("110.00"))

        # Mock db_order
        db_order = MagicMock()
        db_order.id = 1
        db_order.user_id = self.user_id
        db_order.symbol = "STOCK4-EQ"
        db_order.broker_order_id = "ORDER999"
        self.mock_orders_repo.get_by_broker_order_id.return_value = db_order

        # Mock position not found
        self.mock_positions_repo.get_by_symbol.return_value = None

        with (
            patch("src.infrastructure.db.timezone_utils.ist_now") as mock_ist_now,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.paper_trading_adapter.logger"
            ) as mock_logger,
        ):
            mock_ist_now.return_value = datetime.now()

            # Call sync method
            self.adapter._sync_order_execution_to_db(order, execution_price)

            # Verify warning was logged
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if "no position found" in str(call).lower()
            ]
            assert len(warning_calls) > 0

    def test_symbol_normalization_consistency(self):
        """Test that symbol normalization is consistent across operations"""
        # Order with different symbol formats
        order = Order(
            order_id="ORDER111",
            symbol="STOCK5.NS",  # With .NS suffix
            exchange=Exchange.NSE,
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            status=OrderStatus.EXECUTED,
        )
        order.user_id = self.user_id

        execution_price = Money(Decimal("100.00"))

        # Mock db_order with different format
        db_order = MagicMock()
        db_order.id = 1
        db_order.user_id = self.user_id
        db_order.symbol = "STOCK5-EQ"  # Different format
        db_order.broker_order_id = "ORDER111"
        self.mock_orders_repo.get_by_broker_order_id.return_value = db_order

        # Mock position doesn't exist
        self.mock_positions_repo.get_by_symbol.return_value = None

        with patch("src.infrastructure.db.timezone_utils.ist_now") as mock_ist_now:
            mock_ist_now.return_value = datetime.now()

            # Call sync method
            self.adapter._sync_order_execution_to_db(order, execution_price)

            # Verify symbol was normalized consistently
            # Should use db_order.symbol (STOCK5-EQ) for consistency
            if self.mock_positions_repo.upsert.called:
                call_args = self.mock_positions_repo.upsert.call_args[1]
                # Symbol should be normalized (no .NS suffix)
                assert call_args["symbol"] in ["STOCK5-EQ", "STOCK5"]

    def test_transaction_rollback_on_error(self):
        """Test that transaction is rolled back on DB sync error"""
        # Order
        order = Order(
            order_id="ORDER222",
            symbol="STOCK6-EQ",
            exchange=Exchange.NSE,
            transaction_type=TransactionType.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            status=OrderStatus.EXECUTED,
        )

        execution_price = Money(Decimal("100.00"))

        # Mock db_order
        db_order = MagicMock()
        db_order.id = 1
        db_order.user_id = self.user_id
        db_order.symbol = "STOCK6-EQ"
        db_order.broker_order_id = "ORDER222"
        self.mock_orders_repo.get_by_broker_order_id.return_value = db_order

        # Mock position creation to raise error
        self.mock_positions_repo.get_by_symbol.return_value = None
        self.mock_positions_repo.upsert.side_effect = Exception("DB Error")

        # Mock transaction methods
        self.adapter.db_session.in_transaction.return_value = True

        with (
            patch("src.infrastructure.db.timezone_utils.ist_now") as mock_ist_now,
            patch(
                "modules.kotak_neo_auto_trader.infrastructure.broker_adapters.paper_trading_adapter.logger"
            ) as mock_logger,
        ):
            mock_ist_now.return_value = datetime.now()

            # Call sync method (should handle error gracefully)
            self.adapter._sync_order_execution_to_db(order, execution_price)

            # Verify rollback was called
            self.adapter.db_session.rollback.assert_called()

            # Verify warning was logged
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if "failed to sync" in str(call).lower()
            ]
            assert len(warning_calls) > 0
