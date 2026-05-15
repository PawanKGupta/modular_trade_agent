"""Unit tests: transient paper order failures, price fallback, order timestamps, retry."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from modules.kotak_neo_auto_trader.domain import (
    Money,
    Order,
    OrderType,
    TransactionType,
)
from modules.kotak_neo_auto_trader.domain import (
    OrderStatus as DomainOrderStatus,
)
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.paper_trading_adapter import (
    PaperTradingBrokerAdapter,
    _is_transient_pending_failure,
)
from modules.kotak_neo_auto_trader.infrastructure.simulation.price_provider import PriceProvider
from src.infrastructure.db.models import Users
from src.infrastructure.db.timezone_utils import ist_now_naive
from src.infrastructure.persistence.orders_repository import OrdersRepository


def test_is_transient_pending_failure_phrases():
    assert _is_transient_pending_failure("Price not available for POWERGRID")
    assert _is_transient_pending_failure("Market is closed")
    assert not _is_transient_pending_failure("Insufficient funds")


def test_fetch_live_price_uses_mock_when_providers_fail():
    provider = PriceProvider(mode="live", cache_duration_seconds=60)
    provider.data_fetcher = None
    provider.yfinance_provider = None
    price = provider._fetch_live_price("RELIANCE.NS")
    assert price is not None
    assert price > 0


def test_fetch_live_price_uses_stale_cache_before_mock():
    provider = PriceProvider(mode="live", cache_duration_seconds=60)
    provider.data_fetcher = None
    provider.yfinance_provider = None
    provider._price_cache["RELIANCE.NS"] = (123.45, datetime.now())
    price = provider._fetch_live_price("RELIANCE.NS")
    assert price == 123.45


def test_create_amo_placed_at_is_naive_ist_wall_clock(db_session):
    user = Users(email="naive_ts@example.com", password_hash="x", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    before = ist_now_naive()
    repo = OrdersRepository(db_session)
    order = repo.create_amo(
        user_id=user.id,
        symbol="RELIANCE-EQ",
        side="buy",
        order_type="limit",
        quantity=1,
        price=100.0,
        order_id="TEST_NAIVE_1",
    )
    after = ist_now_naive()

    assert order.placed_at.tzinfo is None
    assert before <= order.placed_at <= after


@pytest.mark.unit
def test_check_pending_skips_off_hours_limit_order(db_session):
    user = Users(email="off_hours@example.com", password_hash="x", role="user")
    db_session.add(user)
    db_session.commit()

    config = PaperTradingConfig.default()
    adapter = PaperTradingBrokerAdapter(user_id=user.id, config=config, db_session=db_session)
    adapter.connect()

    limit_sell = Order(
        order_id="PAPER_OFFHOURS_1",
        symbol="POWERGRID-EQ",
        transaction_type=TransactionType.SELL,
        quantity=10,
        price=Money(308.0),
        order_type=OrderType.LIMIT,
    )
    adapter._save_order(limit_sell)

    with patch.object(adapter.order_simulator, "_is_market_open", return_value=False):
        with patch.object(adapter, "_execute_order") as mock_exec:
            summary = adapter.check_and_execute_pending_orders()
            mock_exec.assert_not_called()
            assert summary["checked"] >= 1
            assert summary["still_pending"] >= 1


@pytest.mark.unit
def test_execute_order_price_unavailable_does_not_sync_failure(db_session):
    user = Users(email="transient@example.com", password_hash="x", role="user")
    db_session.add(user)
    db_session.commit()

    config = PaperTradingConfig.default()
    adapter = PaperTradingBrokerAdapter(user_id=user.id, config=config, db_session=db_session)
    adapter.connect()

    buy_order = Order(
        order_id="PAPER_TRANSIENT_BUY",
        symbol="RELIANCE-EQ",
        transaction_type=TransactionType.BUY,
        quantity=1,
        price=Money(2500.0),
        order_type=OrderType.LIMIT,
    )

    with patch.object(adapter.price_provider, "get_price", return_value=None):
        with patch.object(adapter, "_sync_order_failure_to_db") as mock_sync:
            adapter._execute_order(buy_order)
            mock_sync.assert_not_called()

    assert buy_order.status in (DomainOrderStatus.PENDING, DomainOrderStatus.OPEN)


@pytest.mark.unit
def test_execute_order_transient_simulator_message_does_not_sync_failure(db_session):
    user = Users(email="transient2@example.com", password_hash="x", role="user")
    db_session.add(user)
    db_session.commit()

    config = PaperTradingConfig.default()
    adapter = PaperTradingBrokerAdapter(user_id=user.id, config=config, db_session=db_session)
    adapter.connect()

    sell_order = Order(
        order_id="PAPER_TRANSIENT_SELL",
        symbol="POWERGRID-EQ",
        transaction_type=TransactionType.SELL,
        quantity=10,
        price=Money(308.0),
        order_type=OrderType.LIMIT,
    )

    with patch.object(adapter, "_can_sell_from_database", return_value=(True, "")):
        with patch.object(
            adapter.order_simulator,
            "execute_order",
            return_value=(False, "Market is closed", None),
        ):
            with patch.object(adapter, "_sync_order_failure_to_db") as mock_sync:
                adapter._execute_order(sell_order)
                mock_sync.assert_not_called()


def test_recalculate_skips_sell_orders():
    from server.app.routers.orders import _recalculate_order_quantity

    order = MagicMock()
    order.side = "sell"
    order.quantity = 331
    order.price = 308.0

    _recalculate_order_quantity(order, user_id=1, db=MagicMock(), order_id=99)
    assert order.quantity == 331
