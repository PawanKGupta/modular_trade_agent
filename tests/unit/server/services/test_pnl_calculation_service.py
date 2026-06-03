from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from server.app.services import pnl_calculation_service as pnl_module
from server.app.services.pnl_calculation_service import PnlCalculationService
from src.infrastructure.db.models import Orders, PnlDaily, Positions, TradeMode, Users


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeOrderRepo:
    def __init__(self, buy_orders=None, sell_orders=None):
        self._buy_orders = buy_orders or []
        self._sell_orders_map = {o.id: o for o in (sell_orders or [])}

    def list(self, user_id):
        return (self._buy_orders, len(self._buy_orders))

    def get(self, order_id):
        return self._sell_orders_map.get(order_id)


class FakePositionsRepo:
    pass


class DummyPnlRepo:
    def __init__(self):
        self.last_record = None

    def upsert(self, record):
        self.last_record = record
        return record


def _make_position(**kwargs):
    defaults = dict(
        id=1,
        user_id=1,
        symbol="ABC",
        closed_at=datetime(2025, 1, 2, 12, 0),
        opened_at=datetime(2025, 1, 1, 12, 0),
        realized_pnl=100.0,
        unrealized_pnl=10.0,
        exit_price=110.0,
        avg_price=100.0,
        sell_order_id=2,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_order(**kwargs):
    defaults = dict(
        id=1,
        user_id=1,
        symbol="ABC",
        side="buy",
        placed_at=datetime(2025, 1, 1, 12, 0),
        quantity=5.0,
        price=100.0,
        avg_price=100.0,
        trade_mode=TradeMode.PAPER,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _build_service(execute_results):
    db = SimpleNamespace()
    result_iter = iter(execute_results)

    def execute(stmt):
        return FakeResult(next(result_iter))

    db.execute = execute
    db.bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    service = pnl_module.PnlCalculationService(db=db)
    return service


def _normalize_orders_repo_list(service: PnlCalculationService) -> None:
    """Match production contract: OrdersRepository.list() -> (items, total_count)."""

    original_list = service.orders_repo.list

    def list_items(*args, **kwargs):
        result = original_list(*args, **kwargs)
        if isinstance(result, tuple) and len(result) == 2:
            return result
        items = result or []
        return (items, len(items))

    service.orders_repo.list = list_items


def test_calculate_realized_pnl_filters_trade_mode(monkeypatch):
    position = _make_position(trade_mode=TradeMode.PAPER, realized_pnl=200.0)
    buy_order = _make_order(id=10, symbol="ABC", placed_at=position.opened_at)
    service = _build_service([[position]])
    service.orders_repo = FakeOrderRepo(
        buy_orders=[buy_order],
        sell_orders=[_make_order(id=2, quantity=3.0)],
    )

    result = service.calculate_realized_pnl(user_id=1, trade_mode=TradeMode.PAPER)
    assert result[position.closed_at.date()] == 200.0


def test_calculate_realized_pnl_falls_back_to_exit_price(monkeypatch):
    position = _make_position(realized_pnl=None, exit_price=120.0, avg_price=100.0)
    position.sell_order_id = 5
    service = _build_service([[position]])
    service.orders_repo = FakeOrderRepo(
        buy_orders=[],
        sell_orders=[_make_order(id=5, quantity=4.0)],
    )

    result = service.calculate_realized_pnl(user_id=1)

    expected = (120.0 - 100.0) * 4.0
    assert result[position.closed_at.date()] == expected


def test_calculate_realized_pnl_skips_when_sold_quantity_zero():
    position = _make_position(
        realized_pnl=None,
        exit_price=120.0,
        avg_price=100.0,
        sell_order_id=9,
    )
    service = _build_service([[position]])
    service.orders_repo = FakeOrderRepo(
        buy_orders=[],
        sell_orders=[_make_order(id=9, quantity=0.0)],
    )

    assert service.calculate_realized_pnl(user_id=1) == {}


def test_calculate_realized_pnl_skips_without_exit_or_realized():
    position = _make_position(realized_pnl=None, exit_price=None, avg_price=100.0)
    service = _build_service([[position]])
    service.orders_repo = FakeOrderRepo()

    assert service.calculate_realized_pnl(user_id=1) == {}


def test_calculate_realized_pnl_respects_target_date():
    target = date(2026, 5, 1)
    position = _make_position(
        closed_at=datetime(2026, 5, 1, 15, 30),
        realized_pnl=33.0,
    )
    service = _build_service([[position]])

    assert service.calculate_realized_pnl(1, target_date=target) == {target: 33.0}


def test_calculate_fees_non_sqlite_uses_datetime_window():
    target = date(2026, 4, 10)
    order = SimpleNamespace(
        quantity=2.0,
        avg_price=50.0,
        price=None,
        placed_at=datetime(2026, 4, 10, 14, 0, 0),
    )
    service = _build_service([[order]])
    service.db.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    fees = service.calculate_fees(1, target_date=target)

    assert fees[target] == pytest.approx(100.0 * service.DEFAULT_FEE_RATE)


def test_calculate_unrealized_pnl_placeholder_when_field_missing(db_session, sample_user):
    service = PnlCalculationService(db_session)
    _create_position(
        db_session,
        sample_user.id,
        closed_at=None,
        unrealized_pnl=None,
        symbol="NOPNL.NS",
    )

    target = date(2026, 6, 15)
    result = service.calculate_unrealized_pnl(sample_user.id, target_date=target)

    assert result.get(target) == 0.0


def test_get_buy_order_for_position_returns_none_without_opened_at(db_session, sample_user):
    service = PnlCalculationService(db_session)
    assert service._get_buy_order_for_position(sample_user.id, "ANY.NS", None) is None


@pytest.fixture
def sample_user(db_session):
    user = Users(email="pnl@example.com", password_hash="hash123")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_position(db_session, user_id: int, **kwargs) -> Positions:
    defaults = dict(
        symbol="TCS.NS",
        quantity=1.0,
        avg_price=100.0,
        unrealized_pnl=0.0,
        opened_at=datetime.utcnow(),
        closed_at=None,
        realized_pnl=None,
    )
    defaults.update(kwargs)
    position = Positions(user_id=user_id, **defaults)
    db_session.add(position)
    db_session.commit()
    db_session.refresh(position)
    return position


def _create_order(db_session, user_id: int, **kwargs) -> Orders:
    defaults = dict(
        symbol="TCS.NS",
        side="buy",
        order_type="market",
        quantity=1.0,
        price=100.0,
        placed_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    order = Orders(user_id=user_id, **defaults)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


def test_calculate_realized_pnl_returns_entries_by_date(db_session, sample_user):
    service = PnlCalculationService(db_session)
    closed_at = datetime(2026, 1, 2, 10, 30)
    _create_position(
        db_session,
        sample_user.id,
        closed_at=closed_at,
        realized_pnl=150.0,
    )

    result = service.calculate_realized_pnl(sample_user.id)

    assert result == {date(2026, 1, 2): 150.0}


def test_calculate_realized_pnl_filters_by_trade_mode(db_session, sample_user):
    service = PnlCalculationService(db_session)
    _normalize_orders_repo_list(service)
    now = datetime.utcnow()
    # Position without matching buy order (should be skipped when filtering)
    _create_position(
        db_session,
        sample_user.id,
        symbol="NO_ORDER.NS",
        realized_pnl=50.0,
        closed_at=now,
    )

    # Position that should match broker trade mode
    position = _create_position(
        db_session,
        sample_user.id,
        symbol="BROKER.NS",
        realized_pnl=75.0,
        opened_at=now - timedelta(minutes=5),
        closed_at=now,
    )
    _create_order(
        db_session,
        sample_user.id,
        symbol=position.symbol,
        side="buy",
        order_type="market",
        quantity=1.0,
        price=100.0,
        trade_mode=TradeMode.BROKER,
        placed_at=position.opened_at,
    )

    filtered = service.calculate_realized_pnl(sample_user.id, trade_mode=TradeMode.BROKER)

    assert filtered == {position.closed_at.date(): 75.0}


def test_calculate_unrealized_pnl_uses_unrealized_values(db_session, sample_user):
    service = PnlCalculationService(db_session)
    target_date = date(2026, 1, 5)
    _create_position(
        db_session,
        sample_user.id,
        closed_at=None,
        unrealized_pnl=42.0,
        opened_at=datetime(2026, 1, 4, 10, 0),
    )

    result = service.calculate_unrealized_pnl(sample_user.id, target_date=target_date)

    assert result == {target_date: 42.0}


def test_calculate_fees_respects_target_date(db_session, sample_user):
    service = PnlCalculationService(db_session)
    target_date = date(2026, 2, 1)
    placed_at = datetime(2026, 2, 1, 9, 0)
    _create_order(
        db_session,
        sample_user.id,
        quantity=10,
        avg_price=200.0,
        placed_at=placed_at,
    )

    fees = service.calculate_fees(sample_user.id, target_date=target_date)

    expected_fee = 10 * 200.0 * service.DEFAULT_FEE_RATE
    assert fees == {target_date: expected_fee}


def test_calculate_daily_pnl_upserts_record(db_session, sample_user):
    service = PnlCalculationService(db_session)
    target_date = date(2026, 3, 1)
    _create_position(
        db_session,
        sample_user.id,
        closed_at=datetime(2026, 3, 1, 10, 0),
        realized_pnl=100.0,
    )
    _create_position(
        db_session,
        sample_user.id,
        closed_at=None,
        unrealized_pnl=25.0,
        opened_at=datetime(2026, 3, 1, 9, 0),
    )
    _create_order(
        db_session,
        sample_user.id,
        quantity=2,
        avg_price=150.0,
        placed_at=datetime(2026, 3, 1, 8, 0),
    )

    record = service.calculate_daily_pnl(sample_user.id, target_date)

    assert isinstance(record, PnlDaily)
    assert record.realized_pnl == 100.0
    assert record.unrealized_pnl == 25.0
    assert record.fees == pytest.approx(2 * 150.0 * service.DEFAULT_FEE_RATE)


def test_get_buy_order_returns_none_if_outside_window(db_session, sample_user):
    service = PnlCalculationService(db_session)
    _normalize_orders_repo_list(service)
    order = _create_order(
        db_session,
        sample_user.id,
        symbol="LATE.NS",
        placed_at=datetime.utcnow() - timedelta(hours=5),
    )
    position = _create_position(
        db_session,
        sample_user.id,
        symbol=order.symbol,
        opened_at=datetime.utcnow(),
        closed_at=datetime.utcnow(),
    )

    found = service._get_buy_order_for_position(sample_user.id, position.symbol, position.opened_at)

    assert found is None
