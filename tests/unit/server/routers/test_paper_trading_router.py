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
            return {}

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

    # paper_trading_router already imports yfinance as `yf`; patch that directly.
    monkeypatch.setattr(paper_trading_router.yf, "Ticker", FakeTicker)

    # Mock PositionsRepository to return position objects
    from datetime import datetime

    def mock_positions_repo(db):
        class DummyPositionsRepository:
            def list(self, user_id):
                return [
                    SimpleNamespace(
                        id=1,
                        user_id=user_id,
                        symbol="ABC",
                        quantity=3.0,
                        avg_price=100.0,
                        unrealized_pnl=45.0,
                        opened_at=datetime(2025, 1, 1, 10, 0, 0),
                        closed_at=None,
                        reentry_count=0,
                        reentries=None,
                        initial_entry_price=100.0,
                        entry_rsi=None,
                    )
                ]

        return DummyPositionsRepository()

    def mock_orders_repo(db):
        class DummyOrdersRepository:
            def list(self, user_id, **_kwargs):
                return [
                    SimpleNamespace(
                        id=1,
                        user_id=user_id,
                        order_id="order1",
                        broker_order_id=None,
                        symbol="ABC",
                        side="buy",
                        quantity=3,
                        order_type="market",
                        status=SimpleNamespace(value="closed"),
                        avg_price=100.0,
                        price=None,
                        placed_at=datetime(2025, 1, 1, 10, 0, 0),
                        filled_at=datetime(2025, 1, 1, 10, 1, 0),
                        trade_mode=paper_trading_router.TradeMode.PAPER,
                        order_metadata=None,
                        metadata=None,
                    )
                ], 1

        return DummyOrdersRepository()

    def mock_settings_repo(db):
        class DummySettingsRepository:
            def get_by_user_id(self, user_id):
                return SimpleNamespace(trade_mode=paper_trading_router.TradeMode.PAPER)

        return DummySettingsRepository()

    monkeypatch.setattr(paper_trading_router, "PositionsRepository", mock_positions_repo)
    monkeypatch.setattr(paper_trading_router, "OrdersRepository", mock_orders_repo)
    monkeypatch.setattr(paper_trading_router, "SettingsRepository", mock_settings_repo)

    # Avoid any accidental EMA9 fallback network calls
    monkeypatch.setattr(paper_trading_router, "fetch_ohlcv_yf", lambda *args, **kwargs: None)

    mock_db = SimpleNamespace()
    result = paper_trading_router.get_paper_trading_portfolio(
        db=mock_db,
        current=SimpleNamespace(id=202),
    )

    assert result.account.total_pnl == pytest.approx(120.0 + 45.0)
    assert len(result.holdings) == 1
    assert result.holdings[0].symbol == "ABC"
    # Router loads target prices only from DB sell orders (no file fallback).
    assert result.holdings[0].target_price is None
