# ruff: noqa: E501, PLC0415
"""Extra branch coverage for export router (errors, dialect paths, CSV helpers)."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.responses import StreamingResponse

from server.app.routers import export as export_router


def _read_streaming_response_text(resp: StreamingResponse) -> str:
    it = resp.body_iterator
    if hasattr(it, "__aiter__"):

        async def _go():
            parts: list[str] = []
            async for c in it:  # type: ignore[union-attr]
                parts.append(c.decode() if isinstance(c, (bytes, bytearray)) else str(c))
            return "".join(parts)

        return asyncio.run(_go())
    parts = []
    for c in it:  # type: ignore[not-an-iterable]
        parts.append(c.decode() if isinstance(c, (bytes, bytearray)) else str(c))
    return "".join(parts)


def test_list_export_jobs_wraps_repository_errors(monkeypatch):
    class _Bad:
        def __init__(self, _db):
            pass

        def get_by_user(self, *_a, **_k):
            raise RuntimeError("db")

    monkeypatch.setattr(export_router, "ExportJobRepository", _Bad)
    with pytest.raises(HTTPException) as ei:
        export_router.list_export_jobs(
            status=None, data_type=None, limit=10, db=object(), current=SimpleNamespace(id=1)
        )
    assert ei.value.status_code == 500


def test_get_export_job_wraps_non_http_errors(monkeypatch):
    class _Bad:
        def __init__(self, _db):
            pass

        def get_by_id(self, _jid):
            raise OSError("disk")

    monkeypatch.setattr(export_router, "ExportJobRepository", _Bad)
    with pytest.raises(HTTPException) as ei:
        export_router.get_export_job(job_id=1, db=object(), current=SimpleNamespace(id=1))
    assert ei.value.status_code == 500


def test_export_pnl_csv_include_unrealized_false(monkeypatch):
    rec = SimpleNamespace(
        date=date(2024, 2, 1),
        realized_pnl=10.0,
        unrealized_pnl=99.0,
        fees=1.0,
    )

    class _Repo:
        def __init__(self, _db):
            pass

        def range(self, **kwargs):
            return [rec]

    monkeypatch.setattr(export_router, "PnlRepository", _Repo)
    resp = export_router.export_pnl_csv(
        start_date=date(2024, 2, 1),
        end_date=date(2024, 2, 1),
        include_unrealized=False,
        trade_mode=export_router.TradeMode.PAPER,
        db=object(),
        current=SimpleNamespace(id=1),
    )
    body = _read_streaming_response_text(resp)
    assert "9.00" in body or "10.00" in body


def test_export_pnl_csv_wraps_errors(monkeypatch):
    class _Bad:
        def __init__(self, _db):
            pass

        def range(self, **_k):
            raise RuntimeError("pnl")

    monkeypatch.setattr(export_router, "PnlRepository", _Bad)
    with pytest.raises(HTTPException) as ei:
        export_router.export_pnl_csv(
            start_date=None,
            end_date=None,
            include_unrealized=True,
            trade_mode=export_router.TradeMode.PAPER,
            db=object(),
            current=SimpleNamespace(id=1),
        )
    assert ei.value.status_code == 500


class _FakeQ:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def all(self):
        return list(self._rows)


class _FakeDbTrades:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *_a, **_k):
        return _FakeQ(self._rows)


def test_export_trades_csv_closed_position_rows(monkeypatch):
    closed = datetime(2024, 3, 10, 15, 0, 0)
    opened = datetime(2024, 3, 1, 10, 0, 0)
    pos = SimpleNamespace(
        symbol="AAA-EQ",
        quantity=2.0,
        avg_price=100.0,
        exit_price=110.0,
        opened_at=opened,
        closed_at=closed,
        realized_pnl=15.5,
    )
    resp = export_router.export_trades_csv(
        start_date=date(2024, 3, 1),
        end_date=date(2024, 3, 15),
        trade_mode=export_router.TradeMode.PAPER,
        db=_FakeDbTrades([pos]),
        current=SimpleNamespace(id=7),
    )
    text = _read_streaming_response_text(resp)
    assert "AAA-EQ" in text
    assert "15.50" in text or "15.5" in text


def test_export_trades_csv_wraps_errors(monkeypatch):
    class _Bad:
        def query(self, *_a, **_k):
            raise RuntimeError("q")

    with pytest.raises(HTTPException) as ei:
        export_router.export_trades_csv(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 2),
            trade_mode=export_router.TradeMode.PAPER,
            db=_Bad(),
            current=SimpleNamespace(id=1),
        )
    assert ei.value.status_code == 500


def test_export_signals_csv_sqlite_path_list_and_dict_buy_range(monkeypatch):
    monkeypatch.setattr(export_router, "is_postgresql", lambda _db: False)
    sig = SimpleNamespace(
        symbol="S1",
        ts=datetime(2024, 4, 1, 12, 0, 0),
        verdict="buy",
        buy_range=[10.0, 12.0],
        target=15.0,
        stop=9.0,
        last_close=11.0,
        rsi10=44.1,
        signals=["a", "b"],
        justification=["j1"],
        ml_verdict="bull",
        ml_confidence=0.88,
    )
    sig2 = SimpleNamespace(
        symbol="S2",
        ts=datetime(2024, 4, 2, 12, 0, 0),
        verdict=None,
        buy_range={"low": 1.0, "high": 2.0},
        target=None,
        stop=None,
        last_close=None,
        rsi10=None,
        signals=None,
        justification=None,
        ml_verdict=None,
        ml_confidence=None,
    )

    class _Db:
        def query(self, *_a, **_k):
            return _FakeQ([sig, sig2])

    resp = export_router.export_signals_csv(
        start_date=date(2024, 4, 1),
        end_date=date(2024, 4, 3),
        verdict=None,
        db=_Db(),
        current=SimpleNamespace(id=1),
    )
    text = _read_streaming_response_text(resp)
    assert "S1" in text and "S2" in text
    assert "1.00" in text


def test_export_signals_csv_postgresql_path(monkeypatch):
    monkeypatch.setattr(export_router, "is_postgresql", lambda _db: True)
    sig = SimpleNamespace(
        symbol="PG",
        ts=datetime(2024, 5, 1, 12, 0, 0),
        verdict="hold",
        buy_range=None,
        target=1.0,
        stop=1.0,
        last_close=1.0,
        rsi10=50.0,
        signals=None,
        justification=None,
        ml_verdict=None,
        ml_confidence=None,
    )

    class _Db:
        def query(self, *_a, **_k):
            return _FakeQ([sig])

    resp = export_router.export_signals_csv(
        start_date=date(2024, 5, 1),
        end_date=date(2024, 5, 2),
        verdict="hold",
        db=_Db(),
        current=SimpleNamespace(id=1),
    )
    assert "PG" in _read_streaming_response_text(resp)


def test_export_signals_csv_wraps_errors(monkeypatch):
    monkeypatch.setattr(export_router, "is_postgresql", lambda _db: False)

    class _Bad:
        def query(self, *_a, **_k):
            raise RuntimeError("sig")

    with pytest.raises(HTTPException) as ei:
        export_router.export_signals_csv(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 2),
            verdict=None,
            db=_Bad(),
            current=SimpleNamespace(id=1),
        )
    assert ei.value.status_code == 500


class _FakeOrderQ:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def all(self):
        return list(self._rows)


class _FakeDbOrders:
    def __init__(self, rows, dialect_name: str = "sqlite"):
        self._rows = rows
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect_name))

    def query(self, *_a, **_k):
        return _FakeOrderQ(self._rows)


def test_export_orders_csv_sqlite_and_status_filter():
    od = SimpleNamespace(
        id=1,
        order_id="O1",
        symbol="X",
        side="buy",
        order_type="LIMIT",
        status="closed",
        quantity=1,
        execution_qty=1,
        price=10.5,
        avg_price=10.0,
        placed_at=datetime(2024, 6, 1, 10, 0, 0),
        updated_at=None,
        trade_mode=export_router.TradeMode.PAPER,
    )
    resp = export_router.export_orders_csv(
        start_date=date(2024, 6, 1),
        end_date=date(2024, 6, 2),
        status="closed",
        trade_mode=export_router.TradeMode.PAPER,
        db=_FakeDbOrders([od], "sqlite"),
        current=SimpleNamespace(id=1),
    )
    assert "O1" in _read_streaming_response_text(resp)


def test_export_orders_csv_non_sqlite_datetime_filter():
    od = SimpleNamespace(
        id=2,
        order_id=None,
        symbol="Y",
        side="sell",
        order_type="MKT",
        status="pending",
        quantity=2,
        execution_qty=0,
        price=None,
        avg_price=None,
        placed_at=datetime(2024, 7, 1, 12, 0, 0),
        updated_at=datetime(2024, 7, 1, 13, 0, 0),
        trade_mode=export_router.TradeMode.BROKER,
    )
    resp = export_router.export_orders_csv(
        start_date=date(2024, 7, 1),
        end_date=date(2024, 7, 2),
        status=None,
        trade_mode=export_router.TradeMode.BROKER,
        db=_FakeDbOrders([od], "postgresql"),
        current=SimpleNamespace(id=1),
    )
    text = _read_streaming_response_text(resp)
    assert "Y" in text


def test_export_orders_csv_wraps_errors():
    class _Bad:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

        def query(self, *_a, **_k):
            raise RuntimeError("ord")

    with pytest.raises(HTTPException) as ei:
        export_router.export_orders_csv(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 2),
            status=None,
            trade_mode=export_router.TradeMode.PAPER,
            db=_Bad(),
            current=SimpleNamespace(id=1),
        )
    assert ei.value.status_code == 500


def test_export_portfolio_csv_wraps_errors():
    class _Bad:
        def query(self, *_a, **_k):
            raise RuntimeError("pf")

    with pytest.raises(HTTPException) as ei:
        export_router.export_portfolio_csv(
            trade_mode=export_router.TradeMode.PAPER,
            db=_Bad(),
            current=SimpleNamespace(id=1),
        )
    assert ei.value.status_code == 500
