"""Tests for reentry data in paper trading portfolio endpoint"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from server.app.routers import paper_trading
from src.infrastructure.db.models import UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
        )


def _install_router_repo_stubs(monkeypatch, *, positions, orders):
    """Patch router-local repository symbols used by get_paper_trading_portfolio."""

    class _PositionsRepo:
        def __init__(self, db):
            self.db = db

        def list(self, user_id):  # noqa: ARG002
            return positions

    class _OrdersRepo:
        def __init__(self, db):
            self.db = db

        def list(self, user_id, **kwargs):  # noqa: ARG002
            if kwargs.get("side") == "sell":
                return ([], 0)
            return (orders, len(orders))

    class _SettingsRepo:
        def __init__(self, db):
            self.db = db

        def get_by_user_id(self, user_id):  # noqa: ARG002
            return SimpleNamespace(trade_mode=paper_trading.TradeMode.PAPER)

    class _UserTradingConfigRepo:
        def __init__(self, db):
            self.db = db

        def get_or_create_default(self, user_id):  # noqa: ARG002
            return SimpleNamespace(paper_trading_initial_capital=100_000.0)

    monkeypatch.setattr(paper_trading, "PositionsRepository", _PositionsRepo)
    monkeypatch.setattr(paper_trading, "OrdersRepository", _OrdersRepo)
    monkeypatch.setattr(paper_trading, "SettingsRepository", _SettingsRepo)
    monkeypatch.setattr(paper_trading, "UserTradingConfigRepository", _UserTradingConfigRepo)
    monkeypatch.setattr(paper_trading, "compute_sell_target", lambda *args, **kwargs: None)


def _run_portfolio(monkeypatch, user, positions, orders, *, current_price: float = 2600.0):
    """Call portfolio with DB repo stubs and mocked live prices."""
    _install_router_repo_stubs(monkeypatch, positions=positions, orders=orders)
    with patch("server.app.routers.paper_trading.yf.Ticker") as mock_ticker_class:
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"currentPrice": current_price}
        mock_ticker_class.return_value = mock_ticker_instance
        db_session = MagicMock()
        db_session.query.return_value.filter.return_value.all.return_value = []
        return paper_trading.get_paper_trading_portfolio(db=db_session, current=user)


def _make_paper_buy_order(*, symbol: str, placed_at: datetime):
    # Minimal shape required by get_paper_trading_portfolio() for recent_orders + stats.
    return SimpleNamespace(
        id=1,
        broker_order_id=None,
        order_id="order-1",
        symbol=symbol,
        side="buy",
        quantity=1,
        order_type="market",
        status="closed",
        price=None,
        avg_price=None,
        placed_at=placed_at,
        filled_at=None,
        trade_mode=paper_trading.TradeMode.PAPER,
        order_metadata={},
    )


def test_get_paper_trading_portfolio_with_reentry_data(monkeypatch):
    """Test that reentry data is fetched from positions table and included in holdings"""
    user = DummyUser(id=42)

    now = datetime.utcnow()
    mock_position = SimpleNamespace(
        symbol="RELIANCE",
        quantity=10,
        avg_price=2500.0,
        opened_at=now,
        closed_at=None,
        reentry_count=2,
        entry_rsi=28.5,
        initial_entry_price=2500.0,
        reentries={
            "reentries": [
                {
                    "qty": 5,
                    "price": 2400.0,
                    "time": "2025-01-15T10:00:00",
                    "level": 20,
                    "rsi": 18.5,
                    "cycle": 1,
                },
                {
                    "qty": 3,
                    "price": 2300.0,
                    "time": "2025-01-20T10:00:00",
                    "level": 10,
                    "rsi": 9.2,
                    "cycle": 2,
                },
            ]
        },
    )
    buy_order = _make_paper_buy_order(symbol="RELIANCE", placed_at=now + timedelta(minutes=1))
    result = _run_portfolio(monkeypatch, user, [mock_position], [buy_order])

    assert len(result.holdings) == 1
    holding = result.holdings[0]
    assert holding.symbol == "RELIANCE"
    assert holding.reentry_count == 2
    assert holding.entry_rsi == 28.5
    assert holding.initial_entry_price == 2500.0
    assert holding.reentries is not None
    assert len(holding.reentries) == 2
    assert holding.reentries[0]["qty"] == 5
    assert holding.reentries[0]["price"] == 2400.0
    assert holding.reentries[0]["level"] == 20
    assert holding.reentries[1]["qty"] == 3
    assert holding.reentries[1]["price"] == 2300.0
    assert holding.reentries[1]["level"] == 10


def test_get_paper_trading_portfolio_with_reentry_data_old_format(monkeypatch):
    """Test that old format reentries (direct array) is handled correctly"""
    user = DummyUser(id=42)

    now = datetime.utcnow()
    mock_position = SimpleNamespace(
        symbol="RELIANCE.NS",
        quantity=10,
        avg_price=2500.0,
        opened_at=now,
        closed_at=None,
        reentry_count=1,
        entry_rsi=29.0,
        initial_entry_price=2500.0,
        reentries=[
            {
                "qty": 5,
                "price": 2400.0,
                "time": "2025-01-15T10:00:00",
            }
        ],
    )
    buy_order = _make_paper_buy_order(symbol="RELIANCE.NS", placed_at=now + timedelta(minutes=1))
    result = _run_portfolio(monkeypatch, user, [mock_position], [buy_order])

    assert len(result.holdings) == 1
    holding = result.holdings[0]
    assert holding.reentry_count == 1
    assert holding.reentries is not None
    assert len(holding.reentries) == 1
    assert holding.reentries[0]["qty"] == 5


def test_get_paper_trading_portfolio_without_reentry_data(monkeypatch):
    """Test that holdings without reentry data return defaults"""
    user = DummyUser(id=42)

    now = datetime.utcnow()
    mock_position = SimpleNamespace(
        symbol="TCS",
        quantity=20,
        avg_price=3500.0,
        opened_at=now,
        closed_at=None,
        reentry_count=0,
        entry_rsi=None,
        initial_entry_price=None,
        reentries=None,
    )
    buy_order = _make_paper_buy_order(symbol="TCS", placed_at=now + timedelta(minutes=1))
    result = _run_portfolio(monkeypatch, user, [mock_position], [buy_order], current_price=3600.0)

    assert len(result.holdings) == 1
    holding = result.holdings[0]
    assert holding.symbol == "TCS"
    assert holding.reentry_count == 0
    assert holding.entry_rsi is None
    assert holding.initial_entry_price is None
    assert holding.reentries == []


def test_get_paper_trading_portfolio_reentry_data_symbol_normalization(monkeypatch):
    """Test that reentry data is included for positions with varying symbol formats."""
    user = DummyUser(id=42)

    now = datetime.utcnow()
    mock_position1 = SimpleNamespace(
        symbol="RELIANCE-EQ",
        quantity=10,
        avg_price=2500.0,
        opened_at=now,
        closed_at=None,
        reentry_count=1,
        entry_rsi=28.0,
        initial_entry_price=2500.0,
        reentries={"reentries": [{"qty": 5, "price": 2400.0, "time": "2025-01-15T10:00:00"}]},
    )
    mock_position2 = SimpleNamespace(
        symbol="TCS.NS",
        quantity=20,
        avg_price=3500.0,
        opened_at=now,
        closed_at=None,
        reentry_count=0,
        entry_rsi=None,
        initial_entry_price=None,
        reentries=None,
    )
    orders = [
        _make_paper_buy_order(symbol="RELIANCE-EQ", placed_at=now + timedelta(minutes=1)),
        _make_paper_buy_order(symbol="TCS.NS", placed_at=now + timedelta(minutes=2)),
    ]
    _install_router_repo_stubs(
        monkeypatch, positions=[mock_position1, mock_position2], orders=orders
    )
    call_count = [0]

    def create_mock_ticker(ticker_symbol):
        call_count[0] += 1
        mock_ticker = MagicMock()
        if "RELIANCE" in ticker_symbol or call_count[0] == 1:
            mock_ticker.info = {"currentPrice": 2600.0}
        else:
            mock_ticker.info = {"currentPrice": 3600.0}
        return mock_ticker

    with patch("server.app.routers.paper_trading.yf.Ticker", side_effect=create_mock_ticker):
        db_session = MagicMock()
        db_session.query.return_value.filter.return_value.all.return_value = []
        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

    assert len(result.holdings) == 2
    reliance_holding = next(h for h in result.holdings if h.symbol == "RELIANCE-EQ")
    assert reliance_holding.reentry_count == 1
    assert reliance_holding.entry_rsi == 28.0
    tcs_holding = next(h for h in result.holdings if h.symbol == "TCS.NS")
    assert tcs_holding.reentry_count == 0
    assert tcs_holding.entry_rsi is None


def test_get_paper_trading_portfolio_reentry_data_invalid_format(monkeypatch):
    """Test that invalid reentries format (neither dict nor list) is handled gracefully"""
    user = DummyUser(id=42)

    now = datetime.utcnow()
    mock_position = SimpleNamespace(
        symbol="RELIANCE",
        quantity=10,
        avg_price=2500.0,
        opened_at=now,
        closed_at=None,
        reentry_count=1,
        entry_rsi=28.5,
        initial_entry_price=2500.0,
        reentries="invalid_format",
    )
    buy_order = _make_paper_buy_order(symbol="RELIANCE", placed_at=now + timedelta(minutes=1))
    result = _run_portfolio(monkeypatch, user, [mock_position], [buy_order])

    assert len(result.holdings) == 1
    holding = result.holdings[0]
    assert holding.reentry_count == 1
    assert holding.entry_rsi == 28.5
    assert holding.reentries == []


def test_get_paper_trading_portfolio_reentry_data_exception_handling(monkeypatch):
    """Test that exceptions in DB position fetch raise an HTTP 500 (current behavior)."""
    user = DummyUser(id=42)

    class _FailingPositionsRepo:
        def __init__(self, db):
            self.db = db

        def list(self, user_id):
            raise Exception("Database connection error")

    class _OrdersRepo:
        def __init__(self, db):
            self.db = db

        def list(self, user_id, **kwargs):  # noqa: ARG002
            return ([], 0)

    class _UserTradingConfigRepo:
        def __init__(self, db):
            self.db = db

        def get_or_create_default(self, user_id):  # noqa: ARG002
            return SimpleNamespace(paper_trading_initial_capital=100_000.0)

    class _SettingsRepo:
        def __init__(self, db):
            self.db = db

        def get_by_user_id(self, user_id):  # noqa: ARG002
            return SimpleNamespace(trade_mode=paper_trading.TradeMode.PAPER)

    monkeypatch.setattr(paper_trading, "PositionsRepository", _FailingPositionsRepo)
    monkeypatch.setattr(paper_trading, "OrdersRepository", _OrdersRepo)
    monkeypatch.setattr(paper_trading, "SettingsRepository", _SettingsRepo)
    monkeypatch.setattr(paper_trading, "UserTradingConfigRepository", _UserTradingConfigRepo)
    monkeypatch.setattr(paper_trading, "compute_sell_target", lambda *args, **kwargs: None)

    db_session = MagicMock()
    with pytest.raises(HTTPException) as exc:
        paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

    assert exc.value.status_code == 500
