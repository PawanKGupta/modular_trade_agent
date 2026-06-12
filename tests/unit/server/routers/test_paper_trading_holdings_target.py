"""
Tests for paper holdings target_price vs pending sell order price.

Uses real OrdersRepository where noted so invalid ``list()`` kwargs cannot hide behind mocks.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from server.app.routers import paper_trading
from src.infrastructure.db.models import OrderStatus, TradeMode, UserSettings, Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.positions_repository import PositionsRepository
def _make_paper_user(db_session, email: str = "paper_target@test.com") -> Users:
    """User with paper trade mode settings."""
    user = Users(
        email=email,
        name="Paper Target User",
        password_hash="hash",
        role="user",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(
        UserSettings(
            user_id=user.id,
            trade_mode=TradeMode.PAPER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )
    db_session.commit()
    return user


def _seed_paper_holding(
    db_session,
    *,
    user_id: int,
    symbol: str,
    sell_symbol: str | None = None,
    sell_price: float | None = None,
    sell_status: str = "pending",
    sell_trade_mode: TradeMode = TradeMode.PAPER,
    include_sell: bool = True,
):
    """Open position + matching paper buy; optional pending sell via real repository."""
    opened_at = ist_now()
    positions_repo = PositionsRepository(db_session)
    orders_repo = OrdersRepository(db_session)

    positions_repo.upsert(
        user_id=user_id,
        symbol=symbol,
        quantity=10.0,
        avg_price=100.0,
        opened_at=opened_at,
    )
    orders_repo.create_amo(
        user_id=user_id,
        symbol=symbol,
        side="buy",
        order_type="market",
        quantity=10,
        price=100.0,
        order_id=f"buy_{symbol}_{user_id}",
        trade_mode=TradeMode.PAPER,
    )

    sell_order = None
    if include_sell and sell_price is not None:
        sell_order = orders_repo.create_amo(
            user_id=user_id,
            symbol=sell_symbol or symbol,
            side="sell",
            order_type="limit",
            quantity=10,
            price=sell_price,
            order_id=f"sell_{symbol}_{user_id}",
            trade_mode=sell_trade_mode,
        )
        if sell_status != "pending":
            sell_order.status = OrderStatus(sell_status)
            db_session.commit()
            db_session.refresh(sell_order)

    db_session.commit()
    return opened_at, sell_order


@pytest.fixture
def portfolio_mocks(monkeypatch):
    """Stub market data so portfolio endpoint stays offline."""
    mock_ticker = MagicMock()
    mock_ticker.info = {"currentPrice": 105.0, "regularMarketPrice": 105.0}
    monkeypatch.setattr(
        "server.app.routers.paper_trading.yf.Ticker",
        lambda _symbol: mock_ticker,
    )
    monkeypatch.setattr(
        "server.app.routers.paper_trading.compute_sell_target",
        lambda *args, **kwargs: 999.0,
    )


class TestTargetPricesFromActivePaperSells:
    """Unit tests for sell-order → target map helper."""

    def test_maps_full_and_base_symbol(self):
        orders = [
            SimpleNamespace(
                symbol="RELIANCE-EQ",
                side="sell",
                status=OrderStatus.PENDING,
                price=110.0,
                trade_mode=TradeMode.PAPER,
            )
        ]
        result = paper_trading._target_prices_from_active_paper_sells(orders)
        assert result["RELIANCE-EQ"] == 110.0
        assert result["RELIANCE"] == 110.0

    def test_ignores_closed_and_broker_sells(self):
        orders = [
            SimpleNamespace(
                symbol="TCS-EQ",
                side="sell",
                status=OrderStatus.CLOSED,
                price=400.0,
                trade_mode=TradeMode.PAPER,
            ),
            SimpleNamespace(
                symbol="INFY-EQ",
                side="sell",
                status=OrderStatus.PENDING,
                price=500.0,
                trade_mode=TradeMode.BROKER,
            ),
        ]
        assert paper_trading._target_prices_from_active_paper_sells(orders) == {}

    def test_base_symbol_sell_matches_eq_position_key(self):
        orders = [
            SimpleNamespace(
                symbol="RELIANCE",
                side="sell",
                status=OrderStatus.PENDING,
                price=112.5,
                trade_mode=TradeMode.PAPER,
            )
        ]
        result = paper_trading._target_prices_from_active_paper_sells(orders)
        assert result["RELIANCE"] == 112.5


class TestPaperHoldingsTargetIntegration:
    """Portfolio endpoint uses DB sell limit, not live EMA9, when a sell is open."""

    def test_holdings_target_from_pending_paper_sell(
        self, db_session, portfolio_mocks, monkeypatch
    ):
        user = _make_paper_user(db_session)
        _seed_paper_holding(
            db_session,
            user_id=user.id,
            symbol="RELIANCE-EQ",
            sell_price=110.0,
        )

        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

        assert len(result.holdings) == 1
        assert result.holdings[0].target_price == 110.0
        assert result.holdings[0].target_price != 999.0

    def test_holdings_target_matches_recent_order_price(
        self, db_session, portfolio_mocks
    ):
        user = _make_paper_user(db_session, email="paper_target_orders@test.com")
        _seed_paper_holding(
            db_session,
            user_id=user.id,
            symbol="TCS-EQ",
            sell_price=135.5,
        )

        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

        sell_rows = [o for o in result.recent_orders.items if o.transaction_type == "SELL"]
        assert len(sell_rows) == 1
        assert sell_rows[0].execution_price == 135.5
        assert result.holdings[0].target_price == sell_rows[0].execution_price

    def test_holdings_target_when_sell_symbol_stripped(
        self, db_session, portfolio_mocks
    ):
        """Placement stores RELIANCE; position row is RELIANCE-EQ."""
        user = _make_paper_user(db_session, email="paper_target_strip@test.com")
        _seed_paper_holding(
            db_session,
            user_id=user.id,
            symbol="RELIANCE-EQ",
            sell_symbol="RELIANCE",
            sell_price=118.0,
        )

        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

        assert result.holdings[0].target_price == 118.0

    def test_holdings_target_falls_back_to_ema9_without_sell(
        self, db_session, portfolio_mocks
    ):
        user = _make_paper_user(db_session, email="paper_target_ema9@test.com")
        _seed_paper_holding(
            db_session,
            user_id=user.id,
            symbol="HDFCBANK-EQ",
            sell_price=None,
            include_sell=False,
        )

        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

        assert result.holdings[0].target_price == 999.0

    def test_holdings_target_ignores_closed_sell(
        self, db_session, portfolio_mocks
    ):
        user = _make_paper_user(db_session, email="paper_target_closed@test.com")
        _seed_paper_holding(
            db_session,
            user_id=user.id,
            symbol="WIPRO-EQ",
            sell_price=120.0,
            sell_status="closed",
        )

        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

        assert result.holdings[0].target_price == 999.0

    def test_holdings_target_ignores_broker_pending_sell(
        self, db_session, portfolio_mocks
    ):
        user = _make_paper_user(db_session, email="paper_target_broker_sell@test.com")
        _seed_paper_holding(
            db_session,
            user_id=user.id,
            symbol="SBIN-EQ",
            sell_price=150.0,
            sell_trade_mode=TradeMode.BROKER,
        )

        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

        assert result.holdings[0].target_price == 999.0

    def test_holdings_target_uses_paper_sell_when_broker_sell_also_exists(
        self, db_session, portfolio_mocks
    ):
        """Same user/symbol: broker sell must not override paper holdings target."""
        user = _make_paper_user(db_session, email="paper_target_mixed@test.com")
        _seed_paper_holding(
            db_session,
            user_id=user.id,
            symbol="AXISBANK-EQ",
            sell_price=142.0,
            sell_trade_mode=TradeMode.PAPER,
        )
        orders_repo = OrdersRepository(db_session)
        orders_repo.create_amo(
            user_id=user.id,
            symbol="AXISBANK-EQ",
            side="sell",
            order_type="limit",
            quantity=10,
            price=999.0,
            order_id=f"broker_sell_axis_{user.id}",
            trade_mode=TradeMode.BROKER,
        )
        db_session.commit()

        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

        assert len(result.holdings) == 1
        assert result.holdings[0].target_price == 142.0
        assert result.holdings[0].target_price != 999.0

    def test_orders_repo_list_called_without_invalid_kwargs(
        self, db_session, portfolio_mocks, monkeypatch
    ):
        """Regression: must not pass unsupported side/status kwargs to OrdersRepository.list."""
        user = _make_paper_user(db_session, email="paper_target_list_sig@test.com")
        _seed_paper_holding(
            db_session,
            user_id=user.id,
            symbol="ITC-EQ",
            sell_price=111.0,
        )

        real_list = OrdersRepository.list
        calls: list[dict] = []

        def spy_list(self, user_id, status=None, limit=None, offset=0):
            calls.append(
                {
                    "user_id": user_id,
                    "status": status,
                    "limit": limit,
                    "offset": offset,
                }
            )
            return real_list(self, user_id, status=status, limit=limit, offset=offset)

        monkeypatch.setattr(OrdersRepository, "list", spy_list)

        paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

        assert calls, "OrdersRepository.list should be invoked"
        for call in calls:
            assert call["user_id"] == user.id
            assert call["status"] is None or isinstance(call["status"], OrderStatus)
