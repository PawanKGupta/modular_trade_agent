"""
Tests for KotakNeoBrokerAdapter order retrieval and parsing fixes

Tests cover:
1. Different response formats (dict with "data", direct list, etc.)
2. Order parsing with various field formats
3. Field name variations (executed_price, executed_quantity, etc.)
4. Error handling in order conversion
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from modules.kotak_neo_auto_trader.domain import (
    Money,
    Order,
    OrderStatus,
    OrderType,
    TransactionType,
)
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter import (
    KotakNeoBrokerAdapter,
)


@pytest.fixture
def mock_client():
    """Create a mock Kotak Neo client"""
    return MagicMock()


@pytest.fixture
def adapter(mock_client):
    """Create a KotakNeoBrokerAdapter instance"""
    adapter = KotakNeoBrokerAdapter(auth_handler=MagicMock())
    adapter._client = mock_client
    adapter._connected = True
    return adapter


class TestGetAllOrdersResponseFormats:
    """Test get_all_orders() handles different response formats"""

    def test_response_with_data_key(self, adapter, mock_client):
        """Test response format: {"data": [...]}"""
        mock_client.order_report.return_value = {
            "data": [
                {
                    "nOrdNo": "12345",
                    "trdSym": "RELIANCE-EQ",
                    "qty": 10,
                    "prc": 2500.0,
                    "stat": "OPEN",
                    "trnsTp": "B",
                    "prcTp": "L",
                    "ordDtTm": "22-Jan-2025 14:28:01",
                }
            ]
        }

        orders = adapter.get_all_orders()

        assert len(orders) == 1
        assert orders[0].order_id == "12345"
        assert orders[0].symbol == "RELIANCE-EQ"
        mock_client.order_report.assert_called_once()

    def test_response_direct_list(self, adapter, mock_client):
        """Test response format: [...] (direct list)"""
        mock_client.order_report.return_value = [
            {
                "nOrdNo": "12345",
                "trdSym": "TCS-EQ",
                "qty": 5,
                "prc": 3500.0,
                "stat": "EXECUTED",
                "trnsTp": "B",
                "prcTp": "M",
            }
        ]

        orders = adapter.get_all_orders()

        assert len(orders) == 1
        assert orders[0].symbol == "TCS-EQ"
        assert orders[0].quantity == 5

    def test_response_with_orders_key(self, adapter, mock_client):
        """Test response format: {"orders": [...]}"""
        mock_client.order_report.return_value = {
            "orders": [
                {
                    "nOrdNo": "12345",
                    "trdSym": "INFY-EQ",
                    "qty": 15,
                    "stat": "OPEN",
                    "trnsTp": "S",
                }
            ]
        }

        orders = adapter.get_all_orders()

        assert len(orders) == 1
        assert orders[0].symbol == "INFY-EQ"
        assert orders[0].quantity == 15

    def test_response_with_order_list_key(self, adapter, mock_client):
        """Test response format: {"orderList": [...]}"""
        mock_client.order_report.return_value = {
            "orderList": [
                {
                    "nOrdNo": "12345",
                    "trdSym": "HDFC-EQ",
                    "qty": 20,
                    "stat": "CANCELLED",
                }
            ]
        }

        orders = adapter.get_all_orders()

        assert len(orders) == 1
        assert orders[0].symbol == "HDFC-EQ"

    def test_empty_response(self, adapter, mock_client):
        """Test empty response"""
        mock_client.order_report.return_value = {"data": []}

        orders = adapter.get_all_orders()

        assert len(orders) == 0

    def test_no_method_available(self, adapter, mock_client):
        """Test when no order_report method exists"""
        del mock_client.order_report
        del mock_client.get_order_report
        del mock_client.orderBook
        del mock_client.orders

        orders = adapter.get_all_orders()

        assert len(orders) == 0

    def test_fallback_to_alternative_methods(self, adapter, mock_client):
        """Test fallback to alternative method names"""
        # order_report doesn't exist, but get_order_report does
        del mock_client.order_report
        mock_client.get_order_report.return_value = {
            "data": [
                {
                    "nOrdNo": "12345",
                    "trdSym": "RELIANCE-EQ",
                    "qty": 10,
                    "stat": "OPEN",
                    "trnsTp": "B",
                }
            ]
        }

        orders = adapter.get_all_orders()

        assert len(orders) == 1
        mock_client.get_order_report.assert_called_once()

    def test_exception_handling(self, adapter, mock_client):
        """Test exception handling in get_all_orders"""
        mock_client.order_report.side_effect = Exception("API Error")

        orders = adapter.get_all_orders()

        assert len(orders) == 0


class TestParseOrdersResponse:
    """Test _parse_orders_response() with various field formats"""

    def test_parse_order_with_all_fields(self, adapter):
        """Test parsing order with all standard fields"""
        data = [
            {
                "nOrdNo": "12345",
                "trdSym": "RELIANCE-EQ",
                "qty": 10,
                "prc": 2500.0,
                "stat": "OPEN",
                "trnsTp": "B",
                "prcTp": "L",
                "ordDtTm": "22-Jan-2025 14:28:01",
                "avgPrc": 2500.5,
                "fldQty": 10,
            }
        ]

        orders = adapter._parse_orders_response(data)

        assert len(orders) == 1
        order = orders[0]
        assert order.order_id == "12345"
        assert order.symbol == "RELIANCE-EQ"
        assert order.quantity == 10
        assert order.price.amount == Decimal("2500.0")
        assert order.status == OrderStatus.OPEN
        assert order.transaction_type == TransactionType.BUY
        assert order.order_type == OrderType.LIMIT
        assert order.executed_price is not None
        assert order.executed_price.amount == Decimal("2500.5")
        assert order.executed_quantity == 10
        assert order.created_at is not None

    def test_parse_order_with_executed_price(self, adapter):
        """Test parsing order with executed price (avgPrc)"""
        data = [
            {
                "nOrdNo": "12345",
                "trdSym": "TCS-EQ",
                "qty": 5,
                "stat": "EXECUTED",
                "trnsTp": "B",
                "avgPrc": 3500.75,
                "fldQty": 5,
            }
        ]

        orders = adapter._parse_orders_response(data)

        assert len(orders) == 1
        order = orders[0]
        assert order.executed_price is not None
        assert order.executed_price.amount == Decimal("3500.75")
        assert order.executed_quantity == 5

    def test_parse_order_with_zero_executed_price(self, adapter):
        """Test that zero executed price is not set"""
        data = [
            {
                "nOrdNo": "12345",
                "trdSym": "INFY-EQ",
                "qty": 15,
                "stat": "OPEN",
                "trnsTp": "B",
                "avgPrc": 0,
            }
        ]

        orders = adapter._parse_orders_response(data)

        assert len(orders) == 1
        order = orders[0]
        assert order.executed_price is None

    def test_parse_order_with_alternative_field_names(self, adapter):
        """Test parsing with alternative field names"""
        data = [
            {
                "neoOrdNo": "12345",  # Alternative to nOrdNo
                "sym": "RELIANCE",  # Alternative to trdSym
                "quantity": 10,  # Alternative to qty
                "price": 2500.0,  # Alternative to prc
                "orderStatus": "OPEN",  # Alternative to stat
                "transactionType": "BUY",  # Alternative to trnsTp
                "orderType": "LIMIT",  # Alternative to prcTp
            }
        ]

        orders = adapter._parse_orders_response(data)

        assert len(orders) == 1
        order = orders[0]
        assert order.order_id == "12345"
        assert order.symbol == "RELIANCE"
        assert order.quantity == 10

    def test_parse_order_with_datetime_variations(self, adapter):
        """Test parsing datetime with different field names"""
        data = [
            {
                "nOrdNo": "12345",
                "trdSym": "RELIANCE-EQ",
                "qty": 10,
                "stat": "OPEN",
                "trnsTp": "B",
                "ordEntTm": "23-Jan-2025 10:15:30",  # Alternative datetime field
            }
        ]

        orders = adapter._parse_orders_response(data)

        assert len(orders) == 1
        order = orders[0]
        assert order.created_at is not None
        assert order.created_at.year == 2025
        assert order.created_at.month == 1
        assert order.created_at.day == 23

    def test_parse_order_with_empty_symbol_skipped(self, adapter):
        """Test that orders with empty symbol are skipped"""
        data = [
            {
                "nOrdNo": "12345",
                "trdSym": "",  # Empty symbol
                "qty": 10,
                "stat": "OPEN",
            },
            {
                "nOrdNo": "12346",
                "trdSym": "RELIANCE-EQ",  # Valid symbol
                "qty": 5,
                "stat": "OPEN",
            },
        ]

        orders = adapter._parse_orders_response(data)

        # Only one order should be parsed (the one with valid symbol)
        assert len(orders) == 1
        assert orders[0].order_id == "12346"

    def test_parse_order_with_missing_fields(self, adapter):
        """Test parsing order with missing optional fields"""
        data = [
            {
                "nOrdNo": "12345",
                "trdSym": "RELIANCE-EQ",
                "qty": 10,
                # Missing: prc, stat, trnsTp, etc.
            }
        ]

        orders = adapter._parse_orders_response(data)

        assert len(orders) == 1
        order = orders[0]
        assert order.order_id == "12345"
        assert order.symbol == "RELIANCE-EQ"
        # Default values should be used
        assert order.status == OrderStatus.PENDING  # Default from from_string

    def test_parse_order_exception_handling(self, adapter):
        """Test that exceptions during parsing are handled gracefully"""
        data = [
            {
                "nOrdNo": "12345",
                "trdSym": "RELIANCE-EQ",
                "qty": "invalid",  # Invalid quantity type
            },
            {
                "nOrdNo": "12346",
                "trdSym": "TCS-EQ",
                "qty": 5,
                "stat": "OPEN",
            },
        ]

        orders = adapter._parse_orders_response(data)

        # Should parse the valid order and skip the invalid one
        assert len(orders) == 1
        assert orders[0].order_id == "12346"

    def test_parse_order_with_sell_transaction(self, adapter):
        """Test parsing sell order"""
        data = [
            {
                "nOrdNo": "12345",
                "trdSym": "RELIANCE-EQ",
                "qty": 10,
                "stat": "OPEN",
                "trnsTp": "S",  # Sell
            }
        ]

        orders = adapter._parse_orders_response(data)

        assert len(orders) == 1
        order = orders[0]
        assert order.transaction_type == TransactionType.SELL

    def test_parse_order_with_partial_execution(self, adapter):
        """Test parsing order with partial execution"""
        data = [
            {
                "nOrdNo": "12345",
                "trdSym": "RELIANCE-EQ",
                "qty": 10,
                "stat": "PARTIALLY_FILLED",
                "trnsTp": "B",
                "avgPrc": 2500.5,
                "fldQty": 5,  # Partially filled
            }
        ]

        orders = adapter._parse_orders_response(data)

        assert len(orders) == 1
        order = orders[0]
        assert order.executed_quantity == 5
        assert order.quantity == 10
        assert order.executed_price.amount == Decimal("2500.5")


class TestBrokerOrdersAPIEndpoint:
    """Test the API endpoint order conversion (integration with broker adapter)"""

    def test_order_conversion_with_executed_price(self, adapter, mock_client):
        """Test that executed_price is correctly converted in API response"""

        # Create a mock order with executed_price
        mock_order = Order(
            symbol="RELIANCE-EQ",
            quantity=10,
            order_type=OrderType.LIMIT,
            transaction_type=TransactionType.BUY,
            price=Money(Decimal("2500.00")),
            order_id="12345",
            status=OrderStatus.EXECUTED,
            executed_price=Money(Decimal("2500.50")),
            executed_quantity=10,
            created_at=datetime.now(),
        )

        mock_client.order_report.return_value = {"data": []}
        adapter._parse_orders_response = lambda x: [mock_order]

        orders = adapter.get_all_orders()

        assert len(orders) == 1
        assert orders[0].executed_price is not None
        assert orders[0].executed_price.amount == Decimal("2500.50")
        assert orders[0].executed_quantity == 10

    def test_order_conversion_without_executed_price(self, adapter, mock_client):
        """Test order without executed price"""
        mock_order = Order(
            symbol="RELIANCE-EQ",
            quantity=10,
            order_type=OrderType.LIMIT,
            transaction_type=TransactionType.BUY,
            price=Money(Decimal("2500.00")),
            order_id="12345",
            status=OrderStatus.OPEN,
            executed_price=None,
            executed_quantity=0,
            created_at=datetime.now(),
        )

        mock_client.order_report.return_value = {"data": []}
        adapter._parse_orders_response = lambda x: [mock_order]

        orders = adapter.get_all_orders()

        assert len(orders) == 1
        assert orders[0].executed_price is None
        assert orders[0].executed_quantity == 0
