from datetime import date, datetime, timedelta
from types import SimpleNamespace
from types import ModuleType

import pytest
from fastapi import HTTPException

from server.app.routers import pnl as pnl_router


class FakePnlRecord:
    def __init__(self, record_date: date, realized_pnl: float, unrealized_pnl: float, fees: float):
        self.date = record_date
        self.realized_pnl = realized_pnl
        self.unrealized_pnl = unrealized_pnl
        self.fees = fees


class _FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def count(self):
        return 0

    def order_by(self, *args, **kwargs):
        return self

    def offset(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return []


class _FakeDb:
    """Minimal DB stub for router helpers that use SQLAlchemy-style `db.query()`."""

    def query(self, *args, **kwargs):
        return _FakeQuery()


class _ListQuery:
    def __init__(self, items):
        self._items = list(items)

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._items)


class _DbWithQueryItems:
    def __init__(self, items):
        self._items = list(items)

    def query(self, *args, **kwargs):
        return _ListQuery(self._items)


class _FakePagedQuery:
    def __init__(self, items):
        self._items = list(items)
        self._offset = 0
        self._limit = None

    def filter(self, *args, **kwargs):
        return self

    def count(self):
        return len(self._items)

    def order_by(self, *args, **kwargs):
        return self

    def offset(self, offset):
        self._offset = int(offset)
        return self

    def limit(self, limit):
        self._limit = int(limit)
        return self

    def all(self):
        end = None if self._limit is None else (self._offset + self._limit)
        return self._items[self._offset : end]


class _FakePagedDb:
    def __init__(self, items):
        self._items = items

    def query(self, *args, **kwargs):
        return _FakePagedQuery(self._items)


def test_daily_pnl_uses_repo_records(monkeypatch):
    fake_db = _FakeDb()
    current = SimpleNamespace(id=42)

    class RepoWithRecords:
        def __init__(self, db):
            self.db = db

        def range(self, user_id, start_date, end_date):
            assert user_id == current.id
            assert isinstance(start_date, date)
            assert isinstance(end_date, date)
            return [FakePnlRecord(date.today(), 12.5, 2.5, 1.0)]

    monkeypatch.setattr(pnl_router, "PnlRepository", RepoWithRecords)

    series = pnl_router.daily_pnl(
        start=date.today() - timedelta(days=2),
        end=date.today(),
        trade_mode=None,
        include_unrealized=False,
        db=fake_db,
        current=current,
    )

    assert len(series) == 1
    assert series[0].pnl == round(12.5 + 2.5 - 1.0, 2)


def test_daily_pnl_service_fallback_includes_unrealized(monkeypatch):
    fake_db = _FakeDb()
    current = SimpleNamespace(id=55)

    class EmptyRepo:
        def __init__(self, db):
            self.db = db

        def range(self, user_id, start_date, end_date):
            return []

    class ServiceStub:
        def __init__(self, db):
            self.db = db

        def calculate_realized_pnl(self, user_id, mode, _):
            return {
                date.today() - timedelta(days=1): 5.25,
                date.today(): 3.0,
            }

    monkeypatch.setattr(pnl_router, "PnlRepository", EmptyRepo)
    monkeypatch.setattr(pnl_router, "PnlCalculationService", ServiceStub)
    # Router implementation may consult OrdersRepository for default ranges; stub it
    # to avoid relying on a real SQLAlchemy Session/Engine.
    monkeypatch.setattr(
        pnl_router,
        "OrdersRepository",
        lambda db: SimpleNamespace(list=lambda user_id: ([], 0)),
    )
    monkeypatch.setattr(
        pnl_router,
        "_calculate_unrealized_from_open_positions",
        lambda user_id, db, mode: 2.75,
    )

    series = pnl_router.daily_pnl(
        start=date.today() - timedelta(days=2),
        end=date.today(),
        trade_mode="paper",
        include_unrealized=True,
        db=fake_db,
        current=current,
    )

    today_entry = next(item for item in series if item.date == date.today())
    assert today_entry.pnl == round(3.0 + 2.75, 2)
    assert any(item.date == date.today() - timedelta(days=1) for item in series)


def test_daily_pnl_fallback_uses_transactions_json(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    fake_db = _FakeDb()
    current = SimpleNamespace(id=101)

    class EmptyRepo:
        def __init__(self, db):
            self.db = db

        def range(self, user_id, start_date, end_date):
            return []

    class ServiceNoRealized:
        def __init__(self, db):
            self.db = db

        def calculate_realized_pnl(self, user_id, mode, _):
            return {}

    monkeypatch.setattr(pnl_router, "PnlRepository", EmptyRepo)
    monkeypatch.setattr(pnl_router, "PnlCalculationService", ServiceNoRealized)
    monkeypatch.setattr(
        pnl_router,
        "OrdersRepository",
        lambda db: SimpleNamespace(list=lambda user_id: ([], 0)),
    )

    tx_dir = tmp_path / "paper_trading" / f"user_{current.id}"
    tx_dir.mkdir(parents=True)
    (tx_dir / "transactions.json").write_text(
        """
[
  {"transaction_type": "BUY", "timestamp": "2024-01-01T10:00:00Z", "realized_pnl": 0},
  {"transaction_type": "SELL", "timestamp": "2024-01-02T10:00:00Z", "realized_pnl": 12.25},
  {"transaction_type": "SELL", "timestamp": "2024-01-02T12:00:00Z", "realized_pnl": -2.25}
]
""".strip(),
        encoding="utf-8",
    )

    series = pnl_router.daily_pnl(
        start=date(2024, 1, 1),
        end=date(2024, 1, 3),
        trade_mode=None,
        include_unrealized=False,
        db=fake_db,
        current=current,
    )

    assert len(series) == 1
    assert series[0].date == date(2024, 1, 2)
    assert series[0].realized_pnl == round(10.0, 2)
    assert series[0].pnl == round(10.0, 2)


def test_pnl_summary_uses_stats_and_unrealized(monkeypatch):
    fake_db = _FakeDb()
    current = SimpleNamespace(id=7)

    def fake_compute_stats(user_id, db, trade_mode):
        assert user_id == current.id
        assert trade_mode == pnl_router.TradeMode.PAPER
        return (20.0, 3, 1, -1.0, 5.0, 1.5)

    monkeypatch.setattr(pnl_router, "_compute_closed_trade_stats", fake_compute_stats)
    monkeypatch.setattr(
        pnl_router,
        "_calculate_unrealized_from_open_positions",
        lambda user_id, db, mode: 4.5,
    )
    monkeypatch.setattr(pnl_router, "_get_paper_trading_account_data", lambda user_id: None)
    monkeypatch.setattr(
        pnl_router,
        "_calculate_portfolio_unrealized_pnl",
        lambda user_id: pytest.fail("portfolio fallback should not run"),
    )

    summary = pnl_router.pnl_summary(
        start=date.today() - timedelta(days=5),
        end=date.today(),
        trade_mode="paper",
        include_unrealized=True,
        db=fake_db,
        current=current,
    )

    assert summary.totalPnl == round(20.0 + 4.5, 2)
    assert summary.totalRealizedPnl == 20.0
    assert summary.totalUnrealizedPnl == round(4.5, 2)
    assert summary.tradesGreen == 3


def test_pnl_summary_fallback_to_paper_trading(monkeypatch):
    fake_db = _FakeDb()
    current = SimpleNamespace(id=9)

    def zero_stats(*args, **kwargs):
        return (0.0, 0, 0, 0.0, 0.0, 0.0)

    monkeypatch.setattr(pnl_router, "_compute_closed_trade_stats", zero_stats)
    monkeypatch.setattr(
        pnl_router,
        "_get_paper_trading_account_data",
        lambda user_id: {"realized_pnl": 15.0},
    )
    monkeypatch.setattr(pnl_router, "_calculate_portfolio_unrealized_pnl", lambda user_id: 5.5)

    summary = pnl_router.pnl_summary(
        start=date.today() - timedelta(days=5),
        end=date.today(),
        trade_mode="broker",
        include_unrealized=True,
        db=fake_db,
        current=current,
    )

    assert summary.totalRealizedPnl == 15.0
    assert summary.totalUnrealizedPnl == round(5.5, 2)
    assert summary.tradesGreen == 1
    assert summary.daysGreen == 1


def test_audit_history_filters(monkeypatch):
    fake_db = _FakeDb()
    current = SimpleNamespace(id=13)
    base_time = datetime(2024, 1, 1, 12, 0, 0)

    def make_record(record_id, status):
        return SimpleNamespace(
            id=record_id,
            calculation_type="daily",
            date_range_start=date.today(),
            date_range_end=date.today(),
            positions_processed=5,
            orders_processed=3,
            pnl_records_created=2,
            pnl_records_updated=1,
            duration_seconds=0.25,
            status=status,
            error_message=None,
            triggered_by="system",
            created_at=base_time,
        )

    class FakeAuditRepo:
        def __init__(self, db):
            self.db = db

        def get_by_status(self, user_id, status, limit=0):
            return [make_record(1, status)]

        def get_by_user(self, user_id, limit=0):
            return [make_record(2, "none")]

    monkeypatch.setattr(pnl_router, "PnlAuditRepository", FakeAuditRepo)

    filtered = pnl_router.audit_history(limit=5, status="running", db=fake_db, current=current)
    assert filtered[0]["status"] == "running"

    fallback = pnl_router.audit_history(limit=5, status=None, db=fake_db, current=current)
    assert fallback[0]["id"] == 2


def test_audit_history_raises_500_on_repo_error(monkeypatch):
    fake_db = _FakeDb()
    current = SimpleNamespace(id=13)

    class BoomRepo:
        def __init__(self, db):
            self.db = db

        def get_by_user(self, user_id, limit=0):
            raise RuntimeError("boom")

    monkeypatch.setattr(pnl_router, "PnlAuditRepository", BoomRepo)

    with pytest.raises(HTTPException) as exc_info:
        pnl_router.audit_history(limit=5, status=None, db=fake_db, current=current)
    assert exc_info.value.status_code == 500


def test_calculate_pnl_success_and_invalid_trade_mode(monkeypatch):
    fake_db = _FakeDb()
    current = SimpleNamespace(id=21)
    calc_date = date(2024, 3, 1)

    class DummyService:
        def __init__(self, db):
            self.db = db

        def calculate_daily_pnl(self, user_id, calculation_date, mode):
            return SimpleNamespace(
                date=calculation_date,
                realized_pnl=8.0,
                unrealized_pnl=2.0,
                fees=1.0,
            )

    monkeypatch.setattr(pnl_router, "PnlCalculationService", DummyService)

    result = pnl_router.calculate_pnl(
        target_date=calc_date,
        trade_mode="broker",
        db=fake_db,
        current=current,
    )

    assert result["date"] == calc_date.isoformat()
    assert result["total_pnl"] == 9.0

    with pytest.raises(HTTPException) as exc_info:
        pnl_router.calculate_pnl(
            target_date=calc_date,
            trade_mode="invalid",
            db=fake_db,
            current=current,
        )
    assert exc_info.value.status_code == 400


def test_calculate_pnl_raises_500_on_unexpected_error(monkeypatch):
    fake_db = _FakeDb()
    current = SimpleNamespace(id=21)

    class BoomService:
        def __init__(self, db):
            self.db = db

        def calculate_daily_pnl(self, user_id, calculation_date, mode):
            raise RuntimeError("boom")

    monkeypatch.setattr(pnl_router, "PnlCalculationService", BoomService)

    with pytest.raises(HTTPException) as exc_info:
        pnl_router.calculate_pnl(
            target_date=date(2024, 3, 1),
            trade_mode="paper",
            db=fake_db,
            current=current,
        )
    assert exc_info.value.status_code == 500


def test_backfill_pnl_success_and_invalid_trade_mode(monkeypatch):
    fake_db = _FakeDb()
    current = SimpleNamespace(id=33)
    start_date = date(2024, 3, 1)
    end_date = date(2024, 3, 5)

    class DummyService:
        def __init__(self, db):
            self.db = db

        def calculate_date_range(self, user_id, s_date, e_date, mode):
            return [SimpleNamespace(), SimpleNamespace()]

    monkeypatch.setattr(pnl_router, "PnlCalculationService", DummyService)

    response = pnl_router.backfill_pnl(
        start_date=start_date,
        end_date=end_date,
        trade_mode="paper",
        db=fake_db,
        current=current,
    )

    assert response["records_created"] == 2
    assert response["trade_mode"] == "paper"

    with pytest.raises(HTTPException) as exc_info:
        pnl_router.backfill_pnl(
            start_date=start_date,
            end_date=end_date,
            trade_mode="unsupported",
            db=fake_db,
            current=current,
        )
    assert exc_info.value.status_code == 400


def test_backfill_pnl_validates_date_range(monkeypatch):
    fake_db = _FakeDb()
    current = SimpleNamespace(id=33)

    with pytest.raises(HTTPException) as exc_info:
        pnl_router.backfill_pnl(
            start_date=date(2024, 3, 10),
            end_date=date(2024, 3, 1),
            trade_mode=None,
            db=fake_db,
            current=current,
        )
    assert exc_info.value.status_code == 400


def test_backfill_pnl_limits_to_one_year(monkeypatch):
    fake_db = _FakeDb()
    current = SimpleNamespace(id=33)

    with pytest.raises(HTTPException) as exc_info:
        pnl_router.backfill_pnl(
            start_date=date(2023, 1, 1),
            end_date=date(2024, 12, 31),
            trade_mode=None,
            db=fake_db,
            current=current,
        )
    assert exc_info.value.status_code == 400


def test_get_stock_name_uses_yfinance_info_fields(monkeypatch):
    yf = ModuleType("yfinance")

    class FakeTicker:
        def __init__(self, ticker):
            self.info = {"longName": "Acme Corp"}

    yf.Ticker = FakeTicker
    monkeypatch.setitem(__import__("sys").modules, "yfinance", yf)

    assert pnl_router._get_stock_name("ACME-EQ") == "Acme Corp"


def test_get_paper_trading_account_data_loads_json(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "paper_trading" / "user_5").mkdir(parents=True)
    (tmp_path / "paper_trading" / "user_5" / "account.json").write_text(
        '{"realized_pnl": 12.5}', encoding="utf-8"
    )

    out = pnl_router._get_paper_trading_account_data(5)
    assert out == {"realized_pnl": 12.5}


def test_calculate_portfolio_unrealized_pnl_uses_live_price_when_available(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    store = tmp_path / "paper_trading" / "user_7"
    store.mkdir(parents=True)
    (store / "holdings.json").write_text(
        '{"AAA": {"quantity": 2, "average_price": 100, "current_price": 110}, "BBB": {"quantity": 1, "average_price": 50, "current_price": 55}}',
        encoding="utf-8",
    )

    yf = ModuleType("yfinance")

    class FakeTicker:
        def __init__(self, ticker: str):
            # AAA uses live price; BBB falls back to holding current_price
            if ticker.startswith("AAA"):
                self.info = {"currentPrice": 120}
            else:
                self.info = {}

    yf.Ticker = FakeTicker
    monkeypatch.setitem(__import__("sys").modules, "yfinance", yf)

    # AAA: 2*(120-100)=40; BBB: 1*(55-50)=5
    assert pnl_router._calculate_portfolio_unrealized_pnl(7) == pytest.approx(45.0)


def test_load_paper_trading_closed_trade_pnls_filters_sell(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    store = tmp_path / "paper_trading" / "user_9"
    store.mkdir(parents=True)
    (store / "transactions.json").write_text(
        '[{"transaction_type": "BUY", "realized_pnl": 0}, {"transaction_type": "SELL", "realized_pnl": 3.5}, {"transaction_type": "SELL", "realized_pnl": -1.0}]',
        encoding="utf-8",
    )

    assert pnl_router._load_paper_trading_closed_trade_pnls(9) == [3.5, -1.0]


def test_compute_closed_trade_stats_uses_position_realized_and_sell_qty_fallback(monkeypatch):
    user_id = 50
    opened_at = datetime(2024, 1, 1, 10, 0, 0)

    positions = [
        SimpleNamespace(
            symbol="AAA",
            opened_at=opened_at,
            closed_at=opened_at + timedelta(days=1),
            realized_pnl=5.0,
            exit_price=None,
            avg_price=None,
            sell_order_id=None,
        ),
        SimpleNamespace(
            symbol="BBB",
            opened_at=opened_at,
            closed_at=opened_at + timedelta(days=2),
            realized_pnl=None,
            exit_price=110.0,
            avg_price=100.0,
            sell_order_id=1,
        ),
    ]

    fake_db = _DbWithQueryItems(positions)

    buy_order = SimpleNamespace(
        symbol="AAA",
        side="buy",
        placed_at=opened_at,
        trade_mode=pnl_router.TradeMode.PAPER,
    )
    buy_order2 = SimpleNamespace(
        symbol="BBB",
        side="buy",
        placed_at=opened_at,
        trade_mode=pnl_router.TradeMode.PAPER,
    )
    sell_order = SimpleNamespace(quantity=2.0, execution_qty=2.0)

    class _OrdersRepo:
        def __init__(self, db):
            self.db = db

        def list(self, _user_id):
            return [buy_order, buy_order2]

        def get(self, order_id):
            assert order_id == 1
            return sell_order

    monkeypatch.setattr(pnl_router, "OrdersRepository", _OrdersRepo)

    total, green, red, min_pnl, max_pnl, avg_pnl = pnl_router._compute_closed_trade_stats(
        user_id, fake_db, pnl_router.TradeMode.PAPER
    )

    # AAA: 5, BBB: (110-100)*2=20
    assert total == pytest.approx(25.0)
    assert green == 2
    assert red == 0
    assert min_pnl == pytest.approx(5.0)
    assert max_pnl == pytest.approx(20.0)
    assert avg_pnl == pytest.approx(12.5)


def test_compute_closed_trade_stats_falls_back_to_paper_trading_when_no_positions(monkeypatch):
    fake_db = _DbWithQueryItems([])
    monkeypatch.setattr(pnl_router, "OrdersRepository", lambda db: SimpleNamespace(list=lambda *_a, **_k: []))
    monkeypatch.setattr(pnl_router, "_load_paper_trading_closed_trade_pnls", lambda _uid: [1.0, -2.0])

    total, green, red, min_pnl, max_pnl, avg_pnl = pnl_router._compute_closed_trade_stats(
        1, fake_db, None
    )
    assert total == pytest.approx(-1.0)
    assert green == 1
    assert red == 1
    assert min_pnl == pytest.approx(-2.0)
    assert max_pnl == pytest.approx(1.0)
    assert avg_pnl == pytest.approx(-0.5)


def test_calculate_unrealized_from_open_positions_uses_live_price(monkeypatch):
    opened_at = datetime(2024, 1, 1, 10, 0, 0)
    positions = [
        SimpleNamespace(symbol="AAA", opened_at=opened_at, closed_at=None, quantity=2.0, avg_price=100.0),
        SimpleNamespace(symbol="BBB", opened_at=opened_at, closed_at=None, quantity=1.0, avg_price=50.0),
    ]
    fake_db = _DbWithQueryItems(positions)

    yf = ModuleType("yfinance")

    class FakeTicker:
        def __init__(self, ticker: str):
            if ticker.startswith("AAA"):
                self.info = {"regularMarketPrice": 120}
            else:
                self.info = {"currentPrice": 55}

    yf.Ticker = FakeTicker
    monkeypatch.setitem(__import__("sys").modules, "yfinance", yf)
    monkeypatch.setattr(pnl_router, "OrdersRepository", lambda db: SimpleNamespace(list=lambda *_a, **_k: []))

    out = pnl_router._calculate_unrealized_from_open_positions(1, fake_db, None)
    # AAA: 2*(120-100)=40, BBB: 1*(55-50)=5
    assert out == pytest.approx(45.0)


def test_get_closed_positions_paginates_and_adds_stock_names(monkeypatch):
    current = SimpleNamespace(id=77)

    pos1 = SimpleNamespace(
        id=1,
        symbol="AAA",
        quantity=10,
        avg_price=100,
        exit_price=110,
        opened_at=datetime(2024, 1, 1, 10, 0, 0),
        closed_at=datetime(2024, 1, 2, 10, 0, 0),
        realized_pnl=100.0,
        realized_pnl_pct=10.0,
        realized_pnl_pct_ignored=None,
        exit_reason="tp",
    )
    pos2 = SimpleNamespace(
        id=2,
        symbol="BBB",
        quantity=5,
        avg_price=200,
        exit_price=190,
        opened_at=datetime(2024, 1, 3, 10, 0, 0),
        closed_at=datetime(2024, 1, 4, 10, 0, 0),
        realized_pnl=-50.0,
        realized_pnl_pct=-5.0,
        exit_reason="sl",
    )

    fake_db = _FakePagedDb([pos1, pos2])
    monkeypatch.setattr(pnl_router, "_get_stock_name", lambda symbol: f"Name({symbol})")
    monkeypatch.setattr(
        pnl_router,
        "OrdersRepository",
        lambda db: SimpleNamespace(
            list=lambda user_id: (
                [
                    SimpleNamespace(
                        symbol="AAA",
                        side="buy",
                        trade_mode=pnl_router.TradeMode.PAPER,
                    )
                ],
                1,
            )
        ),
    )

    result = pnl_router.get_closed_positions(
        page=1,
        page_size=1,
        trade_mode=None,
        sort_by="closed_at",
        sort_order="desc",
        db=fake_db,
        current=current,
    )

    assert result.total == 2
    assert result.page == 1
    assert result.page_size == 1
    assert result.total_pages == 2
    assert len(result.items) == 1
    assert result.items[0].stock_name == "Name(AAA)"


def test_get_closed_positions_rejects_invalid_trade_mode(monkeypatch):
    current = SimpleNamespace(id=77)
    fake_db = _FakePagedDb([])

    with pytest.raises(HTTPException) as exc_info:
        pnl_router.get_closed_positions(
            page=1,
            page_size=10,
            trade_mode="not-a-mode",
            sort_by="closed_at",
            sort_order="desc",
            db=fake_db,
            current=current,
        )
    assert exc_info.value.status_code == 400
