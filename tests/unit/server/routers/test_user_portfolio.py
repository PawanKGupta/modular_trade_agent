"""
Tests for unified portfolio endpoint in user router
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from server.app.routers import user
from src.infrastructure.db.models import TradeMode, UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
        )


class DummySettings(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            user_id=kwargs.get("user_id", 1),
            trade_mode=kwargs.get("trade_mode", TradeMode.PAPER),
            broker=kwargs.get("broker", None),
            broker_status=kwargs.get("broker_status", None),
            broker_creds_encrypted=kwargs.get("broker_creds_encrypted", None),
        )


class DummySettingsRepo:
    def __init__(self, db):
        self.db = db
        self.settings = DummySettings(user_id=1, trade_mode=TradeMode.PAPER)

    def get_by_user_id(self, user_id):
        self.settings.user_id = user_id
        return self.settings

    def ensure_default(self, user_id):
        self.settings.user_id = user_id
        return self.settings


def test_get_portfolio_paper_mode(monkeypatch):
    """Test unified portfolio endpoint routes to paper trading in paper mode"""
    user_obj = DummyUser(id=42)

    # Mock settings repository
    repo = DummySettingsRepo(object())
    repo.settings.trade_mode = TradeMode.PAPER
    monkeypatch.setattr(user, "SettingsRepository", lambda db: repo)

    # Mock paper trading portfolio endpoint
    mock_paper_portfolio = MagicMock()
    mock_paper_portfolio.account.initial_capital = 100000.0
    mock_paper_portfolio.account.available_cash = 50000.0
    mock_paper_portfolio.holdings = []
    mock_paper_portfolio.recent_orders = []
    mock_paper_portfolio.order_statistics = {}

    def mock_get_paper_portfolio(*, db, current, **kwargs):
        return mock_paper_portfolio

    monkeypatch.setattr(user, "get_paper_trading_portfolio", mock_get_paper_portfolio)

    db_session = MagicMock()
    result = user.get_portfolio(db=db_session, current=user_obj)

    assert result == mock_paper_portfolio
    assert repo.settings.trade_mode == TradeMode.PAPER


def test_get_portfolio_broker_mode(monkeypatch):
    """Test unified portfolio endpoint routes to broker portfolio in broker mode"""
    user_obj = DummyUser(id=42)

    # Mock settings repository
    repo = DummySettingsRepo(object())
    repo.settings.trade_mode = TradeMode.BROKER
    monkeypatch.setattr(user, "SettingsRepository", lambda db: repo)

    broker_portfolio = SimpleNamespace(
        account={
            "initial_capital": 200000.0,
            "available_cash": 100000.0,
            "total_pnl": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "portfolio_value": 0.0,
            "total_value": 0.0,
            "return_percentage": 0.0,
        },
        holdings=[],
        recent_orders=[],
        order_statistics={},
    )

    broker_portfolio_fn = MagicMock(return_value=broker_portfolio)
    monkeypatch.setattr(user, "get_broker_portfolio", broker_portfolio_fn)

    db_session = MagicMock()
    result = user.get_portfolio(db=db_session, current=user_obj)

    broker_portfolio_fn.assert_called_once()
    assert result.account.initial_capital == 200000.0
    assert result.account.available_cash == 100000.0
    assert result.recent_orders.total == 0
    assert repo.settings.trade_mode == TradeMode.BROKER


def test_get_portfolio_no_settings_defaults_to_paper(monkeypatch):
    """Test unified portfolio endpoint defaults to paper mode if settings don't exist"""
    user_obj = DummyUser(id=42)

    # Mock settings repository - returns None initially, then creates default
    repo = DummySettingsRepo(object())
    repo.settings = None

    def mock_get_by_user_id(user_id):
        if repo.settings is None:
            return None
        return repo.settings

    def mock_ensure_default(user_id):
        repo.settings = DummySettings(user_id=user_id, trade_mode=TradeMode.PAPER)
        return repo.settings

    repo.get_by_user_id = mock_get_by_user_id
    repo.ensure_default = mock_ensure_default
    monkeypatch.setattr(user, "SettingsRepository", lambda db: repo)

    # Mock paper trading portfolio endpoint
    mock_paper_portfolio = MagicMock()
    mock_paper_portfolio.account.initial_capital = 0.0
    mock_paper_portfolio.holdings = []

    def mock_get_paper_portfolio(*, db, current, **kwargs):
        return mock_paper_portfolio

    monkeypatch.setattr(user, "get_paper_trading_portfolio", mock_get_paper_portfolio)

    db_session = MagicMock()
    result = user.get_portfolio(db=db_session, current=user_obj)

    assert result == mock_paper_portfolio
    assert repo.settings.trade_mode == TradeMode.PAPER


def test_get_portfolio_broker_mode_propagates_exception(monkeypatch):
    """Test that exceptions from broker portfolio are propagated"""
    user_obj = DummyUser(id=42)

    # Mock settings repository
    repo = DummySettingsRepo(object())
    repo.settings.trade_mode = TradeMode.BROKER
    monkeypatch.setattr(user, "SettingsRepository", lambda db: repo)

    # Mock broker portfolio endpoint to raise exception
    def mock_get_broker_portfolio(*, db, current, **kwargs):
        raise HTTPException(status_code=400, detail="Broker credentials not configured")

    monkeypatch.setattr(user, "get_broker_portfolio", mock_get_broker_portfolio)

    db_session = MagicMock()
    with pytest.raises(HTTPException) as exc:
        user.get_portfolio(db=db_session, current=user_obj)

    assert exc.value.status_code == 400
    assert "Broker credentials not configured" in exc.value.detail
