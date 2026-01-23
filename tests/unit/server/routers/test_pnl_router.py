from datetime import date, datetime, timedelta
from types import SimpleNamespace

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

    def all(self):
        return []


class _FakeDb:
    """Minimal DB stub for router helpers that use SQLAlchemy-style `db.query()`."""

    def query(self, *args, **kwargs):
        return _FakeQuery()


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
