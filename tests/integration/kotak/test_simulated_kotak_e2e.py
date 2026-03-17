"""
E2E-style integration test with a simulated Kotak broker + stock feed.

Validates split-quantity behavior:
- holdings reports base symbol qty (e.g. AXISBANK=7)
- positions reports full symbol qty (AXISBANK-EQ=5)
- DB open position qty is 12
- existing active sell order qty=7 is updated/replaced to qty=12
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor
from src.infrastructure.db.base import Base
from src.infrastructure.db.models import OrderStatus, UserRole, Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.positions_repository import PositionsRepository
from tests.integration.kotak.cleanup_simulated_test_data import cleanup_simulated_test_data
from tests.integration.kotak.simulated_components import (
    FakeKotakAuth,
    FakeKotakRestClient,
    FakeStockSignalFeed,
)


class _DummyScripMaster:
    """Avoid network/cache access in SellOrderManager init."""

    def __init__(self, auth_client=None, exchanges=None):
        self.auth_client = auth_client
        self.exchanges = exchanges or ["NSE"]

    def load_scrip_master(self, force_download: bool = False) -> bool:
        _ = force_download
        return True

    def get_token(self, symbol: str, exchange: str = "NSE") -> str:
        _ = (symbol, exchange)
        return "1001"


TEST_EMAIL = "sim-e2e@example.com"
TEST_SYMBOL = "AXISBANK-EQ"


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        cleanup_simulated_test_data(db, emails=[TEST_EMAIL], symbols=[TEST_SYMBOL])
        yield db
    finally:
        # Per-test cleanup script/hook for targeted test data.
        cleanup_simulated_test_data(db, emails=[TEST_EMAIL], symbols=[TEST_SYMBOL])
        db.close()


def _build_monitor(
    db,
    *,
    existing_sell_qty: int,
    db_open_qty: float,
    holdings_qty: int = 7,
    positions_qty: int = 5,
):
    # Seed user required for FK relationships.
    user = Users(
        email=TEST_EMAIL,
        name="Sim User",
        password_hash="dummy_hash",
        role=UserRole.USER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id

    orders_repo = OrdersRepository(db)
    positions_repo = PositionsRepository(db)

    # Executed buy for today (re-entry) - this is what UnifiedOrderMonitor picks up.
    buy_order = orders_repo.create_amo(
        user_id=user_id,
        symbol=TEST_SYMBOL,
        side="buy",
        order_type="market",
        quantity=5,
        price=1212.10,
        order_id="260316000547451",
        broker_order_id="260316000547451",
        entry_type="reentry",
        order_metadata={"ticker": "AXISBANK.NS"},
    )
    buy_order.status = OrderStatus.CLOSED
    buy_order.execution_qty = 5
    buy_order.execution_price = 1212.10
    buy_order.execution_time = ist_now()
    orders_repo.update(buy_order)

    # Open position reflects consolidated qty across lots.
    positions_repo.upsert(
        user_id=user_id,
        symbol=TEST_SYMBOL,
        quantity=db_open_qty,
        avg_price=1288.30,
        entry_rsi=29.5,
    )

    fake_rest = FakeKotakRestClient(
        holdings_rows=[{"tradingSymbol": "AXISBANK", "sellableQuantity": holdings_qty}],
        positions_rows=[{"trdSym": TEST_SYMBOL, "qty": str(positions_qty), "netQty": str(positions_qty)}],
        order_book_rows=[
            {
                "nOrdNo": "260316000554938",
                "neoOrdNo": "260316000554938",
                "orderId": "260316000554938",
                "trdSym": "AXISBANK",
                "ts": "AXISBANK",
                "qty": str(existing_sell_qty),
                "prc": "1215.70",
                "trnsTp": "S",
                "tt": "S",
                "ordSt": "open",
                "stat": "open",
                "prcTp": "L",
                "pt": "L",
                "es": "nse_cm",
                "tk": "1001",
                "pc": "CNC",
            }
        ],
    )
    auth = FakeKotakAuth(fake_rest)
    stock_feed = FakeStockSignalFeed({"AXISBANK.NS": 1266.10})

    with patch(
        "modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster",
        _DummyScripMaster,
    ):
        sell_manager = SellOrderManager(
            auth=auth,
            positions_repo=positions_repo,
            user_id=user_id,
            orders_repo=orders_repo,
        )

    # Deterministic stock/indicator component
    sell_manager._get_ema9_with_retry = stock_feed.get_ema9
    sell_manager.lowest_ema9 = {}
    sell_manager.active_sell_orders = {}
    sell_manager._register_order = Mock(wraps=sell_manager._register_order)
    sell_manager.place_sell_order = Mock(wraps=sell_manager.place_sell_order)

    monitor = UnifiedOrderMonitor(
        sell_order_manager=sell_manager,
        db_session=db,
        user_id=user_id,
    )
    return monitor, sell_manager, fake_rest


def test_simulated_kotak_replaces_existing_sell_with_aggregated_qty(db_session):
    monitor, sell_manager, fake_rest = _build_monitor(
        db_session,
        existing_sell_qty=7,
        db_open_qty=12.0,
    )

    placed_count = monitor.check_and_place_sell_orders_for_new_holdings()

    # Existing sell was updated to 12 instead of placing a duplicate.
    assert placed_count == 0
    assert len(fake_rest.modified_orders) == 1
    modify = fake_rest.modified_orders[0]
    assert modify["order_id"] == "260316000554938"
    assert str(modify["payload"].get("qt")) == "12"
    assert sell_manager._register_order.call_count >= 1
    sell_manager.place_sell_order.assert_not_called()


def test_simulated_kotak_skips_when_existing_sell_qty_already_sufficient(db_session):
    monitor, sell_manager, fake_rest = _build_monitor(
        db_session,
        existing_sell_qty=12,
        db_open_qty=12.0,
    )

    placed_count = monitor.check_and_place_sell_orders_for_new_holdings()

    assert placed_count == 0
    assert fake_rest.modified_orders == []
    sell_manager.place_sell_order.assert_not_called()


def test_simulated_kotak_no_new_sell_when_replace_fails(db_session):
    monitor, sell_manager, fake_rest = _build_monitor(
        db_session,
        existing_sell_qty=7,
        db_open_qty=12.0,
    )

    # Force replacement failure path.
    sell_manager.update_sell_order = Mock(return_value=False)

    placed_count = monitor.check_and_place_sell_orders_for_new_holdings()

    assert placed_count == 0
    assert fake_rest.modified_orders == []
    sell_manager.place_sell_order.assert_not_called()


def test_simulated_kotak_skips_when_no_sellable_qty_available(db_session):
    monitor, sell_manager, fake_rest = _build_monitor(
        db_session,
        existing_sell_qty=0,
        db_open_qty=5.0,
        holdings_qty=0,
        positions_qty=0,
    )
    # Ensure no pre-existing open sell order in this scenario.
    fake_rest.order_book_rows = []

    placed_count = monitor.check_and_place_sell_orders_for_new_holdings()

    assert placed_count == 0
    assert fake_rest.modified_orders == []
    assert fake_rest.placed_orders == []
    sell_manager.place_sell_order.assert_not_called()
