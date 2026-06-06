from types import SimpleNamespace

import pytest

from server.app.routers import paper_trading as paper_trading_router


def test_get_paper_trading_portfolio_returns_empty_when_no_db(monkeypatch):
    result = paper_trading_router.get_paper_trading_portfolio(
        db=None,
        current=SimpleNamespace(id=101),
    )

    assert result.account.initial_capital == 0.0
    assert result.holdings == []


def test_get_paper_trading_portfolio_builds_holdings(monkeypatch):
    class DummyUserTradingConfigRepository:
        def __init__(self, _db):
            pass

        def get_or_create_default(self, user_id):  # noqa: ARG002
            return SimpleNamespace(paper_trading_initial_capital=1000.0)

    monkeypatch.setattr(
        paper_trading_router,
        "UserTradingConfigRepository",
        DummyUserTradingConfigRepository,
    )

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
    monkeypatch.setattr(paper_trading_router, "compute_sell_target", lambda *args, **kwargs: None)

    from unittest.mock import MagicMock

    closed_at = datetime(2025, 2, 1, 10, 0, 0)
    closed_pos = SimpleNamespace(
        symbol="ABC",
        opened_at=datetime(2025, 1, 1, 10, 0, 0),
        closed_at=closed_at,
        realized_pnl=120.0,
    )
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = [closed_pos]

    result = paper_trading_router.get_paper_trading_portfolio(
        db=mock_db,
        current=SimpleNamespace(id=202),
    )

    assert result.account.realized_pnl == pytest.approx(120.0)
    assert result.account.total_pnl == pytest.approx(120.0 + 45.0)
    assert result.account.total_value == pytest.approx(1000.0 + 120.0 + 45.0)
    assert len(result.holdings) == 1
    assert result.holdings[0].symbol == "ABC"
    # Router loads target prices only from DB sell orders (no file fallback).
    assert result.holdings[0].target_price is None
