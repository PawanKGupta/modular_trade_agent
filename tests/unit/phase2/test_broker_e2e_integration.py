"""
E2E Integration test for Phase 2.4 Broker Trading History
Tests the complete flow: Orders → FIFO Matching → API Response → Schema Validation
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from server.app.core.security import create_jwt_token
from src.infrastructure.db.models import Orders, OrderStatus, TradeMode, UserRole, Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.settings_repository import SettingsRepository


@pytest.fixture
def test_user(db_session):
    """Get test user from db_session"""
    user = db_session.query(Users).first()
    if not user:
        user = Users(
            email="e2e@example.com",
            name="E2E Test User",
            password_hash="dummy_hash",
            role=UserRole.USER,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers for test user"""
    token = create_jwt_token(
        str(test_user.id), extra={"uid": test_user.id, "roles": [test_user.role.value]}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def broker_settings(test_user, db_session):
    """Create broker mode settings for test user"""
    settings_repo = SettingsRepository(db_session)
    settings = settings_repo.ensure_default(test_user.id)
    settings.trade_mode = TradeMode.BROKER
    db_session.commit()
    return settings


def setup_broker_orders(db, user: Users) -> list[Orders]:
    """
    Create a complete trade scenario:
    1. Buy 100 shares of AAPL at $150
    2. Buy 50 shares of AAPL at $152
    3. Sell 80 shares of AAPL at $155 (partial fill from first lot)
    4. Buy 100 shares of GOOGL at $140
    5. Sell 100 shares of GOOGL at $145 (complete fill)
    """
    base_time = ist_now()
    orders = []

    # Order 1: Buy 100 AAPL @ $150
    order1 = Orders(
        user_id=user.id,
        symbol="AAPL",
        side="buy",
        order_type="market",
        quantity=100,
        execution_price=150.00,
        avg_price=150.00,
        status=OrderStatus.CLOSED,
        placed_at=base_time,
        filled_at=base_time,
        trade_mode=TradeMode.BROKER,
        order_id="ORD-001",
    )
    db.add(order1)
    orders.append(order1)

    # Order 2: Buy 50 AAPL @ $152
    order2 = Orders(
        user_id=user.id,
        symbol="AAPL",
        side="buy",
        order_type="market",
        quantity=50,
        execution_price=152.00,
        avg_price=152.00,
        status=OrderStatus.CLOSED,
        placed_at=base_time + timedelta(hours=1),
        filled_at=base_time + timedelta(hours=1),
        trade_mode=TradeMode.BROKER,
        order_id="ORD-002",
    )
    db.add(order2)
    orders.append(order2)

    # Order 3: Sell 80 AAPL @ $155 (partial FIFO from first buy order)
    order3 = Orders(
        user_id=user.id,
        symbol="AAPL",
        side="sell",
        order_type="market",
        quantity=80,
        execution_price=155.00,
        avg_price=155.00,
        status=OrderStatus.CLOSED,
        placed_at=base_time + timedelta(hours=2),
        filled_at=base_time + timedelta(hours=2),
        trade_mode=TradeMode.BROKER,
        order_id="ORD-003",
    )
    db.add(order3)
    orders.append(order3)

    # Order 4: Buy 100 GOOGL @ $140
    order4 = Orders(
        user_id=user.id,
        symbol="GOOGL",
        side="buy",
        order_type="market",
        quantity=100,
        execution_price=140.00,
        avg_price=140.00,
        status=OrderStatus.CLOSED,
        placed_at=base_time + timedelta(hours=3),
        filled_at=base_time + timedelta(hours=3),
        trade_mode=TradeMode.BROKER,
        order_id="ORD-004",
    )
    db.add(order4)
    orders.append(order4)

    # Order 5: Sell 100 GOOGL @ $145 (complete FIFO)
    order5 = Orders(
        user_id=user.id,
        symbol="GOOGL",
        side="sell",
        order_type="market",
        quantity=100,
        execution_price=145.00,
        avg_price=145.00,
        status=OrderStatus.CLOSED,
        placed_at=base_time + timedelta(hours=4),
        filled_at=base_time + timedelta(hours=4),
        trade_mode=TradeMode.BROKER,
        order_id="ORD-005",
    )
    db.add(order5)
    orders.append(order5)

    db.commit()
    return orders


class TestBrokerE2EIntegration:
    """E2E integration tests for broker trading history."""

    def test_complete_fifo_matching_flow(
        self, client: TestClient, test_user, db_session, auth_headers, broker_settings
    ):
        """
        E2E Test: Orders → FIFO Matching → API Response Validation

        Scenario:
        - Create 5 orders (2 buys AAPL, 1 sell AAPL, 1 buy GOOGL, 1 sell GOOGL)
        - Call /history endpoint
        - Verify FIFO matching produces correct closed positions
        - Verify P&L calculations are accurate
        - Verify response schema matches TradeHistory
        """
        # Setup: Create test orders
        orders = setup_broker_orders(db_session, test_user)
        assert len(orders) == 5

        # Call API endpoint
        response = client.get("/api/v1/user/broker/history", headers=auth_headers)
        assert response.status_code == 200, f"Failed with: {response.text}"

        data = response.json()
        assert "transactions" in data
        assert "closed_positions" in data
        assert "statistics" in data

        # Verify transaction count
        assert len(data["transactions"]) == 5, "Should have all 5 transactions"

        # Verify all transactions are present
        transaction_symbols = [t["symbol"] for t in data["transactions"]]
        assert transaction_symbols.count("AAPL") == 3, "Should have 3 AAPL transactions"
        assert transaction_symbols.count("GOOGL") == 2, "Should have 2 GOOGL transactions"

        # Verify FIFO matching produced closed positions
        closed_positions = data["closed_positions"]
        assert len(closed_positions) > 0, "Should have closed positions from FIFO matching"

        # Find AAPL closed positions
        aapl_positions = [cp for cp in closed_positions if cp["symbol"] == "AAPL"]
        assert (
            len(aapl_positions) == 1
        ), "Should have 1 AAPL closed position (80 shares from first lot)"

        # Verify AAPL position (100 shares @ $150, sold 80 @ $155)
        aapl_pos = aapl_positions[0]
        assert aapl_pos["quantity"] == 80, "AAPL position should be 80 shares"
        assert aapl_pos["entry_price"] == 150.0, "Entry price should be $150"
        assert aapl_pos["exit_price"] == 155.0, "Exit price should be $155"
        assert aapl_pos["realized_pnl"] == 400.0, "P&L should be (155-150)*80 = $400"
        assert aapl_pos["pnl_percentage"] == pytest.approx(3.33, abs=0.01), "P&L% should be ~3.33%"

        # Verify GOOGL position (complete fill)
        googl_positions = [cp for cp in closed_positions if cp["symbol"] == "GOOGL"]
        assert len(googl_positions) == 1, "Should have 1 GOOGL closed position"
        googl_pos = googl_positions[0]
        assert googl_pos["quantity"] == 100, "GOOGL position should be 100 shares"
        assert googl_pos["entry_price"] == 140.0, "Entry price should be $140"
        assert googl_pos["exit_price"] == 145.0, "Exit price should be $145"
        assert googl_pos["realized_pnl"] == 500.0, "P&L should be (145-140)*100 = $500"
        assert googl_pos["pnl_percentage"] == pytest.approx(3.57, abs=0.01), "P&L% should be ~3.57%"

        # Verify statistics
        stats = data["statistics"]
        assert stats["total_trades"] == 2, "Should have 2 closed trades"
        assert stats["profitable_trades"] == 2, "All trades should be profitable"
        assert stats["win_rate"] == 100.0, "Win rate should be 100%"
        assert stats["total_profit"] == 900.0, "Total profit should be $400 + $500 = $900"
        assert stats["net_pnl"] == 900.0, "Net P&L should be $900"
        assert stats["avg_profit_per_trade"] == 450.0, "Average profit per trade should be $450"

    def test_raw_mode_returns_transactions_only(
        self, client: TestClient, test_user, db_session, auth_headers, broker_settings
    ):
        """
        Test raw=true query parameter returns only transactions without FIFO matching.
        """
        orders = setup_broker_orders(db_session, test_user)
        assert len(orders) == 5

        # Call API with raw=true
        response = client.get("/api/v1/user/broker/history?raw=true", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert len(data["transactions"]) == 5
        assert len(data["closed_positions"]) == 0, "Raw mode should have no closed positions"

    def test_date_filtering(
        self, client: TestClient, test_user, db_session, auth_headers, broker_settings
    ):
        """Test date filtering parameters work correctly."""
        orders = setup_broker_orders(db_session, test_user)
        assert len(orders) == 5

        # Get first order date
        first_order_time = orders[0].placed_at
        mid_time = first_order_time + timedelta(hours=2)
        last_order_time = orders[4].placed_at

        # Filter to only get transactions after the middle time
        response = client.get(
            "/api/v1/user/broker/history",
            params={
                "from_date": mid_time.isoformat(),
                "to_date": last_order_time.isoformat(),
            },
            headers=auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        # Should get orders 3, 4, 5 (after mid_time)
        assert len(data["transactions"]) == 3, "Should have 3 transactions in date range"

    def test_non_broker_mode_user_gets_error(self, client: TestClient, test_user, db_session):
        """Test that non-broker-mode users get an error."""
        # Create settings in PAPER mode
        settings_repo = SettingsRepository(db_session)
        settings = settings_repo.ensure_default(test_user.id)
        settings.trade_mode = TradeMode.PAPER
        db_session.commit()

        # Create auth headers for paper mode user
        token = create_jwt_token(
            str(test_user.id), extra={"uid": test_user.id, "roles": [test_user.role.value]}
        )
        auth_headers_paper = {"Authorization": f"Bearer {token}"}

        response = client.get("/api/v1/user/broker/history", headers=auth_headers_paper)
        assert response.status_code == 400
        assert "broker mode" in response.json()["detail"].lower()

    def test_response_schema_validation(
        self, client: TestClient, test_user, db_session, auth_headers, broker_settings
    ):
        """Test that response conforms to TradeHistory schema."""
        orders = setup_broker_orders(db_session, test_user)

        response = client.get("/api/v1/user/broker/history", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()

        # Validate TradeHistory schema
        assert isinstance(data, dict)
        assert "transactions" in data
        assert "closed_positions" in data
        assert "statistics" in data

        # Validate transactions
        assert isinstance(data["transactions"], list)
        for tx in data["transactions"]:
            assert "order_id" in tx
            assert "symbol" in tx
            assert "transaction_type" in tx
            assert "quantity" in tx
            assert "price" in tx
            assert "timestamp" in tx

        # Validate closed positions
        assert isinstance(data["closed_positions"], list)
        for cp in data["closed_positions"]:
            assert "symbol" in cp
            assert "quantity" in cp
            assert "entry_price" in cp
            assert "exit_price" in cp
            assert "realized_pnl" in cp
            assert "pnl_percentage" in cp
            assert "holding_days" in cp

        # Validate statistics
        assert isinstance(data["statistics"], dict)
        assert "total_trades" in data["statistics"]
        assert "win_rate" in data["statistics"]
        assert "net_pnl" in data["statistics"]
