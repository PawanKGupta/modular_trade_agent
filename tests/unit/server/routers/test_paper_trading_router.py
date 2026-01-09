import io
import json
import sys
import types
from types import SimpleNamespace

import pytest

from server.app.routers import paper_trading as paper_trading_router


def test_get_paper_trading_portfolio_returns_empty_when_missing(monkeypatch):
    monkeypatch.setattr(paper_trading_router.Path, "exists", lambda self: False)

    result = paper_trading_router.get_paper_trading_portfolio(
        db=SimpleNamespace(),
        current=SimpleNamespace(id=101),
    )

    assert result.account.initial_capital == 0.0
    assert result.holdings == []


def test_get_paper_trading_portfolio_builds_holdings(monkeypatch):
    monkeypatch.setattr(paper_trading_router.Path, "exists", lambda self: True)

    class FakeStore:
        def __init__(self, storage_path, auto_save):
            self.storage_path = storage_path

        def get_account(self):
            return {
                "initial_capital": 1000.0,
                "available_cash": 400.0,
                "realized_pnl": 120.0,
            }

        def get_all_holdings(self):
            return {
                "ABC": {
                    "quantity": 3,
                    "average_price": 100.0,
                    "current_price": 110.0,
                },
            }

        def get_all_orders(self):
            return []

    monkeypatch.setattr(paper_trading_router, "PaperTradeStore", FakeStore)

    class FakeReporter:
        def __init__(self, store):
            self.store = store

        def order_statistics(self):
            return {
                "total_orders": 1,
                "buy_orders": 1,
                "sell_orders": 0,
                "completed_orders": 1,
                "pending_orders": 0,
                "cancelled_orders": 0,
                "rejected_orders": 0,
            }

    monkeypatch.setattr(paper_trading_router, "PaperTradeReporter", FakeReporter)

    class FakeTicker:
        def __init__(self, ticker):
            self._ticker = ticker

        @property
        def info(self):
            return {"currentPrice": 115.0}

    fake_module = types.ModuleType("yfinance")
    fake_module.Ticker = FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", fake_module)

    def fake_open(*args, **kwargs):
        return io.StringIO(json.dumps({"ABC": {"target_price": 130.0}}))

    monkeypatch.setattr(paper_trading_router, "open", fake_open, raising=False)

    # Mock PositionsRepository and OrdersRepository for db=None case
    def mock_positions_repo(db):
        repo = SimpleNamespace()
        repo.list = lambda user_id: []
        return repo

    def mock_orders_repo(db):
        repo = SimpleNamespace()
        repo.list = lambda user_id: []
        return repo

    import server.app.routers.paper_trading as paper_trading_module
    monkeypatch.setattr(
        "src.infrastructure.persistence.positions_repository.PositionsRepository",
        mock_positions_repo,
    )
    monkeypatch.setattr(
        "server.app.routers.paper_trading.OrdersRepository",
        mock_orders_repo,
    )

    result = paper_trading_router.get_paper_trading_portfolio(
        db=None,  # Use None to trigger file-based fallback
        current=SimpleNamespace(id=202),
    )

    assert result.account.total_pnl == pytest.approx(120.0 + 45.0)
    assert len(result.holdings) == 1
    assert result.holdings[0].symbol == "ABC"
    assert result.holdings[0].target_price == 130.0
