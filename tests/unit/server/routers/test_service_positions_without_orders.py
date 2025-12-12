"""
Tests for Issue #5: Positions Without Sell Orders API Endpoint

Tests verify:
1. GET /service/positions/without-sell-orders endpoint
2. Response format and schema validation
3. Error handling
4. Integration with MultiUserTradingService
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status

from server.app.routers import service
from server.app.schemas.service import PositionsWithoutSellOrdersResponse


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
        )


class DummyTradingService:
    def __init__(self, db):
        self.db = db
        self.get_positions_without_sell_orders_called = []

    def get_positions_without_sell_orders(self, user_id):
        self.get_positions_without_sell_orders_called.append(user_id)
        return getattr(self, "_positions_result", [])


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def trading_service(mock_db):
    """Create DummyTradingService instance."""
    return DummyTradingService(mock_db)


@pytest.fixture
def current_user():
    """Create dummy user."""
    return DummyUser(id=1, email="test@example.com", name="Test User")


def test_get_positions_without_sell_orders_success(trading_service, current_user, mock_db):
    """Test successful retrieval of positions without sell orders."""
    # Setup: Mock positions without sell orders
    trading_service._positions_result = [
        {
            "symbol": "RELIANCE",
            "entry_price": 2500.0,
            "quantity": 10,
            "reason": "EMA9 calculation failed (Issue #3)",
            "ticker": "RELIANCE.NS",
            "broker_symbol": "RELIANCE-EQ",
        },
        {
            "symbol": "TCS",
            "entry_price": 3500.0,
            "quantity": 5,
            "reason": "Zero or invalid quantity (Issue #2)",
            "ticker": "TCS.NS",
            "broker_symbol": "TCS-EQ",
        },
    ]

    result = service.get_positions_without_sell_orders(
        db=mock_db,
        current=current_user,
        trading_service=trading_service,
    )

    # Verify service was called
    assert len(trading_service.get_positions_without_sell_orders_called) == 1
    assert trading_service.get_positions_without_sell_orders_called[0] == current_user.id

    # Verify response structure
    assert isinstance(result, PositionsWithoutSellOrdersResponse)
    assert result.count == 2
    assert len(result.positions) == 2

    # Verify position details
    assert result.positions[0].symbol == "RELIANCE"
    assert result.positions[0].entry_price == 2500.0
    assert result.positions[0].quantity == 10
    assert result.positions[0].reason == "EMA9 calculation failed (Issue #3)"
    assert result.positions[0].ticker == "RELIANCE.NS"
    assert result.positions[0].broker_symbol == "RELIANCE-EQ"

    assert result.positions[1].symbol == "TCS"
    assert result.positions[1].entry_price == 3500.0
    assert result.positions[1].quantity == 5
    assert result.positions[1].reason == "Zero or invalid quantity (Issue #2)"


def test_get_positions_without_sell_orders_empty(trading_service, current_user, mock_db):
    """Test when there are no positions without sell orders."""
    trading_service._positions_result = []

    result = service.get_positions_without_sell_orders(
        db=mock_db,
        current=current_user,
        trading_service=trading_service,
    )

    assert isinstance(result, PositionsWithoutSellOrdersResponse)
    assert result.count == 0
    assert len(result.positions) == 0


def test_get_positions_without_sell_orders_exception(trading_service, current_user, mock_db):
    """Test error handling when exception occurs."""

    # Mock service to raise exception
    def raise_exception(user_id):
        raise Exception("Service unavailable")

    trading_service.get_positions_without_sell_orders = raise_exception

    with pytest.raises(HTTPException) as exc_info:
        service.get_positions_without_sell_orders(
            db=mock_db,
            current=current_user,
            trading_service=trading_service,
        )

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Error getting positions without sell orders" in str(exc_info.value.detail)


def test_get_positions_without_sell_orders_large_list(trading_service, current_user, mock_db):
    """Test with large list of positions (edge case)."""
    # Create 50 positions
    trading_service._positions_result = [
        {
            "symbol": f"STOCK{i}",
            "entry_price": 1000.0 + i,
            "quantity": 10 + i,
            "reason": f"Reason {i}",
            "ticker": f"STOCK{i}.NS",
            "broker_symbol": f"STOCK{i}-EQ",
        }
        for i in range(50)
    ]

    result = service.get_positions_without_sell_orders(
        db=mock_db,
        current=current_user,
        trading_service=trading_service,
    )

    assert result.count == 50
    assert len(result.positions) == 50
    assert result.positions[0].symbol == "STOCK0"
    assert result.positions[49].symbol == "STOCK49"


def test_get_positions_without_sell_orders_service_not_running(
    trading_service, current_user, mock_db
):
    """Test when service is not running (returns empty list)."""
    # Service not running typically returns empty list
    trading_service._positions_result = []

    result = service.get_positions_without_sell_orders(
        db=mock_db,
        current=current_user,
        trading_service=trading_service,
    )

    assert result.count == 0
    assert len(result.positions) == 0
