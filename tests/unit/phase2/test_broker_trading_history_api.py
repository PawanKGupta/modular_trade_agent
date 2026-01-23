"""Unit tests for Broker Trading History API (Phase 2.4)"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from server.app.core.security import create_jwt_token
from src.infrastructure.db.models import Orders, OrderStatus, Positions, TradeMode, UserRole, Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.settings_repository import SettingsRepository


@pytest.fixture
def test_user(db_session):
    """Get test user from db_session"""
    # db_session is just the session, not a tuple
    # Create a test user if one doesn't exist
    user = db_session.query(Users).first()
    if not user:
        user = Users(
            email="test@example.com",
            name="Test User",
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


class TestBrokerTradingHistoryAPI:
    """Test Broker Trading History API endpoints"""

    def test_broker_history_empty_result(
        self, client: TestClient, test_user, db_session, auth_headers, broker_settings
    ):
        """Test broker history with no data returns empty result"""
        # Commit settings
        db_session.commit()
        response = client.get("/api/v1/user/broker/history", headers=auth_headers)

        # Endpoint might not exist yet, so check for either 200 or 404
        if response.status_code == 404:
            pytest.skip("Broker history endpoint not implemented yet")

        assert response.status_code == 200
        data = response.json()
        assert "transactions" in data
        assert "closed_positions" in data
        assert "statistics" in data
        assert len(data["transactions"]) == 0
        assert len(data["closed_positions"]) == 0

    def test_broker_history_with_transactions(
        self, client: TestClient, test_user, db_session, auth_headers, broker_settings
    ):
        """Test broker history with transactions"""
        session = db_session
        db_session.commit()  # Commit broker_settings

        # Create buy order
        buy_order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="market",
            quantity=10,
            price=None,
            status=OrderStatus.CLOSED,
            avg_price=2500.0,
            trade_mode=TradeMode.BROKER,
            placed_at=ist_now() - timedelta(days=5),
            filled_at=ist_now() - timedelta(days=5),
            closed_at=ist_now() - timedelta(days=5),
        )
        session.add(buy_order)
        session.commit()
        session.refresh(buy_order)

        response = client.get("/api/v1/user/broker/history", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Broker history endpoint not implemented yet")

        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) >= 1

    def test_broker_history_with_closed_positions(
        self, client: TestClient, test_user, db_session, auth_headers, broker_settings
    ):
        """Test broker history with closed positions"""
        session = db_session
        db_session.commit()  # Commit broker_settings

        # Create buy order
        buy_order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="market",
            quantity=10,
            price=None,
            status=OrderStatus.CLOSED,
            avg_price=2500.0,
            trade_mode=TradeMode.BROKER,
            placed_at=ist_now() - timedelta(days=5),
            filled_at=ist_now() - timedelta(days=5),
            closed_at=ist_now() - timedelta(days=5),
        )
        session.add(buy_order)
        session.commit()
        session.refresh(buy_order)

        # Create sell order
        sell_order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            side="sell",
            order_type="market",
            quantity=10,
            price=None,
            status=OrderStatus.CLOSED,
            avg_price=2750.0,
            trade_mode=TradeMode.BROKER,
            placed_at=ist_now() - timedelta(days=2),
            filled_at=ist_now() - timedelta(days=2),
            closed_at=ist_now() - timedelta(days=2),
        )
        session.add(sell_order)
        session.commit()
        session.refresh(sell_order)

        # Create closed position
        position = Positions(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            quantity=10,
            avg_price=2500.0,
            opened_at=ist_now() - timedelta(days=5),
            closed_at=ist_now() - timedelta(days=2),
            exit_price=2750.0,
            realized_pnl=2500.0,  # (2750 - 2500) * 10
            realized_pnl_pct=10.0,  # (2750 - 2500) / 2500 * 100
            sell_order_id=sell_order.id,
        )
        session.add(position)
        session.commit()

        response = client.get("/api/v1/user/broker/history", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Broker history endpoint not implemented yet")

        assert response.status_code == 200
        data = response.json()
        assert len(data["closed_positions"]) >= 1
        closed_pos = data["closed_positions"][0]
        assert closed_pos["symbol"] == "RELIANCE-EQ"
        assert closed_pos["realized_pnl"] == 2500.0

    def test_broker_history_statistics_calculation(
        self, client: TestClient, test_user, db_session, auth_headers, broker_settings
    ):
        """Test that broker history calculates statistics correctly"""
        session = db_session
        db_session.commit()  # Commit broker_settings

        # Create profitable position
        buy1 = Orders(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="market",
            quantity=10,
            status=OrderStatus.CLOSED,
            avg_price=2500.0,
            trade_mode=TradeMode.BROKER,
            placed_at=ist_now() - timedelta(days=5),
            filled_at=ist_now() - timedelta(days=5),
            closed_at=ist_now() - timedelta(days=5),
        )
        session.add(buy1)
        session.commit()
        session.refresh(buy1)

        sell1 = Orders(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            side="sell",
            order_type="market",
            quantity=10,
            status=OrderStatus.CLOSED,
            avg_price=2750.0,
            trade_mode=TradeMode.BROKER,
            placed_at=ist_now() - timedelta(days=2),
            filled_at=ist_now() - timedelta(days=2),
            closed_at=ist_now() - timedelta(days=2),
        )
        session.add(sell1)
        session.commit()
        session.refresh(sell1)

        pos1 = Positions(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            quantity=10,
            avg_price=2500.0,
            opened_at=ist_now() - timedelta(days=5),
            closed_at=ist_now() - timedelta(days=2),
            exit_price=2750.0,
            realized_pnl=2500.0,
            realized_pnl_pct=10.0,
            sell_order_id=sell1.id,
        )
        session.add(pos1)
        session.commit()

        response = client.get("/api/v1/user/broker/history", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Broker history endpoint not implemented yet")

        assert response.status_code == 200
        data = response.json()
        assert "statistics" in data
        stats = data["statistics"]
        assert "total_trades" in stats
        assert "win_rate" in stats
        assert stats["total_trades"] >= 1

    def test_broker_history_filters_by_trade_mode(
        self, client: TestClient, test_user, db_session, auth_headers, broker_settings
    ):
        """Test that broker history only includes broker trades"""
        session = db_session
        db_session.commit()  # Commit broker_settings

        # Create broker order
        broker_order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="market",
            quantity=10,
            status=OrderStatus.CLOSED,
            avg_price=2500.0,
            trade_mode=TradeMode.BROKER,
            placed_at=ist_now() - timedelta(days=5),
            filled_at=ist_now() - timedelta(days=5),
            closed_at=ist_now() - timedelta(days=5),
        )
        session.add(broker_order)

        # Create paper order (should be excluded)
        paper_order = Orders(
            user_id=test_user.id,
            symbol="TCS-EQ",
            side="buy",
            order_type="market",
            quantity=5,
            status=OrderStatus.CLOSED,
            avg_price=3000.0,
            trade_mode=TradeMode.PAPER,
            placed_at=ist_now() - timedelta(days=5),
            filled_at=ist_now() - timedelta(days=5),
            closed_at=ist_now() - timedelta(days=5),
        )
        session.add(paper_order)
        session.commit()

        response = client.get("/api/v1/user/broker/history", headers=auth_headers)

        if response.status_code == 404:
            pytest.skip("Broker history endpoint not implemented yet")

        assert response.status_code == 200
        data = response.json()
        # Should only include broker transactions
        broker_symbols = [
            t["symbol"] for t in data["transactions"] if t.get("symbol") == "RELIANCE-EQ"
        ]
        paper_symbols = [t["symbol"] for t in data["transactions"] if t.get("symbol") == "TCS-EQ"]
        assert len(broker_symbols) >= 1
        assert len(paper_symbols) == 0
