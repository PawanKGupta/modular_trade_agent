"""Regression: one paper place_order must yield one orders row (no adapter double-insert)."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from config.strategy_config import StrategyConfig
from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from modules.kotak_neo_auto_trader.domain import Order, OrderType, TransactionType
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.paper_trading_adapter import (
    PaperTradingBrokerAdapter,
)
from src.application.services.paper_trading_service_adapter import PaperTradingEngineAdapter
from src.infrastructure.db.models import Orders, Users
from src.infrastructure.persistence.orders_repository import OrdersRepository


@pytest.fixture
def test_user(db_session):
    user = Users(email="single_row@example.com", password_hash="hash", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def paper_broker_with_db(db_session, test_user, tmp_path):
    config = PaperTradingConfig(
        enforce_market_hours=False,
        market_open_time="09:15",
        market_close_time="15:30",
        max_position_size=200_000.0,
        initial_capital=1_000_000.0,
    )
    broker = PaperTradingBrokerAdapter(
        user_id=test_user.id,
        config=config,
        db_session=db_session,
        storage_path=str(tmp_path / "paper"),
    )
    broker.connect()
    broker.price_provider.get_price = Mock(return_value=831.65)
    yield broker


def test_market_buy_place_order_creates_single_db_row(db_session, test_user, paper_broker_with_db):
    """Fast market fill + duplicate create_amo must not add a ghost pending row."""
    order = Order(
        symbol="INDIANB",
        quantity=10,
        order_type=OrderType.MARKET,
        transaction_type=TransactionType.BUY,
    )
    order._metadata = {"original_ticker": "INDIANB.NS"}

    order_id = paper_broker_with_db.place_order(order)
    assert order_id

    orders = db_session.query(Orders).filter(Orders.user_id == test_user.id).all()
    assert len(orders) == 1
    assert orders[0].broker_order_id == order_id

    repo = OrdersRepository(db_session)
    dup = repo.create_amo(
        user_id=test_user.id,
        symbol="INDIANB",
        side="buy",
        order_type="market",
        quantity=10,
        price=831.65,
        broker_order_id=order_id,
    )
    assert dup.id == orders[0].id
    assert db_session.query(Orders).filter(Orders.user_id == test_user.id).count() == 1


@pytest.fixture
def mock_paper_broker():
    broker = MagicMock()
    broker.is_connected.return_value = True
    broker.get_holdings.return_value = []
    broker.get_all_orders.return_value = []
    broker.get_available_balance.return_value = MagicMock(amount=100000.0)
    broker.place_order.return_value = "PAPER_ORDER_123"
    broker.store.get_account.return_value = {"available_cash": 1_000_000_000.0}
    broker.store.storage_path = "paper_trading/test"
    broker.price_provider.get_prices.return_value = {}
    broker.config = MagicMock()
    broker.config.max_position_size = 100000.0
    return broker


def test_place_new_entries_does_not_call_create_amo_from_adapter(
    db_session,
    test_user,
    mock_paper_broker,
):
    """Engine adapter must rely on broker.place_order for DB persistence."""
    strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)
    adapter = PaperTradingEngineAdapter(
        broker=mock_paper_broker,
        user_id=test_user.id,
        db_session=db_session,
        strategy_config=strategy_config,
        logger=MagicMock(),
    )

    recommendations = [
        Recommendation(
            ticker="RELIANCE.NS",
            verdict="buy",
            last_close=2500.0,
            execution_capital=100000.0,
        )
    ]

    with (
        patch("core.volume_analysis.is_market_hours", return_value=False),
        patch.object(OrdersRepository, "create_amo") as mock_create_amo,
    ):
        adapter.place_new_entries(recommendations)

    mock_create_amo.assert_not_called()
