from __future__ import annotations

import asyncio
import csv
import io
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.responses import StreamingResponse

from server.app.routers import export as export_router


def _read_streaming_response_text(resp: StreamingResponse) -> str:
    iterator = resp.body_iterator

    # Starlette may provide either a sync iterator (common when we pass `iter([...])`)
    # or an async iterator depending on internals/version.
    if hasattr(iterator, "__aiter__"):

        async def _collect_async() -> str:
            chunks: list[str] = []
            async for chunk in iterator:  # type: ignore[union-attr]
                if isinstance(chunk, (bytes, bytearray)):
                    chunks.append(chunk.decode("utf-8"))
                else:
                    chunks.append(str(chunk))
            return "".join(chunks)

        return asyncio.run(_collect_async())

    chunks = []
    for chunk in iterator:  # type: ignore[not-an-iterable]
        if isinstance(chunk, (bytes, bytearray)):
            chunks.append(chunk.decode("utf-8"))
        else:
            chunks.append(str(chunk))
    return "".join(chunks)


def test_list_export_jobs_filters_status_and_data_type(monkeypatch):
    fake_db = object()
    current = SimpleNamespace(id=1)

    now = datetime(2024, 1, 1, 12, 0, 0)
    jobs = [
        SimpleNamespace(
            id=1,
            user_id=current.id,
            export_type="csv",
            data_type="orders",
            date_range_start=date(2024, 1, 1),
            date_range_end=date(2024, 1, 2),
            status="completed",
            progress=100,
            file_path="/tmp/a.csv",
            file_size=12,
            records_exported=1,
            duration_seconds=0.1,
            error_message=None,
            created_at=now,
            started_at=now,
            completed_at=now,
        ),
        SimpleNamespace(
            id=2,
            user_id=current.id,
            export_type="csv",
            data_type="pnl",
            date_range_start=None,
            date_range_end=None,
            status="running",
            progress=50,
            file_path=None,
            file_size=None,
            records_exported=0,
            duration_seconds=None,
            error_message=None,
            created_at=now,
            started_at=None,
            completed_at=None,
        ),
    ]

    class FakeRepo:
        def __init__(self, db):
            self.db = db

        def get_by_user(self, user_id, status=None, limit=0):
            assert user_id == current.id
            if status:
                return [j for j in jobs if j.status == status]
            return list(jobs)

    monkeypatch.setattr(export_router, "ExportJobRepository", FakeRepo)

    # Status filter uses repo
    out = export_router.list_export_jobs(
        status="running",
        data_type=None,
        limit=50,
        db=fake_db,
        current=current,
    )
    assert len(out) == 1
    assert out[0]["status"] == "running"

    # data_type filter is applied in router
    out2 = export_router.list_export_jobs(
        status=None,
        data_type="orders",
        limit=50,
        db=fake_db,
        current=current,
    )
    assert len(out2) == 1
    assert out2[0]["data_type"] == "orders"


def test_get_export_job_success_404_and_403(monkeypatch):
    fake_db = object()
    current = SimpleNamespace(id=10)

    now = datetime(2024, 1, 1, 12, 0, 0)
    job = SimpleNamespace(
        id=5,
        user_id=current.id,
        export_type="csv",
        data_type="orders",
        date_range_start=None,
        date_range_end=None,
        status="completed",
        progress=100,
        file_path="/tmp/a.csv",
        file_size=12,
        records_exported=1,
        duration_seconds=0.1,
        error_message=None,
        created_at=now,
        started_at=now,
        completed_at=now,
    )

    class FakeRepo:
        def __init__(self, db):
            self.db = db

        def get_by_id(self, job_id):
            return job if job_id == 5 else None

    monkeypatch.setattr(export_router, "ExportJobRepository", FakeRepo)

    ok = export_router.get_export_job(job_id=5, db=fake_db, current=current)
    assert ok["id"] == 5

    with pytest.raises(HTTPException) as exc_info:
        export_router.get_export_job(job_id=404, db=fake_db, current=current)
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info2:
        export_router.get_export_job(job_id=5, db=fake_db, current=SimpleNamespace(id=999))
    assert exc_info2.value.status_code == 403


def test_export_portfolio_csv_builds_rows(monkeypatch):
    current = SimpleNamespace(id=99)

    class FakeQuery:
        def __init__(self, items):
            self._items = list(items)

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            return list(self._items)

    class FakeDb:
        def __init__(self, items):
            self._items = items

        def query(self, *args, **kwargs):
            return FakeQuery(self._items)

    opened = datetime.utcnow() - timedelta(days=10)
    positions = [
        SimpleNamespace(symbol="AAA", quantity=2.0, avg_price=100.0, opened_at=opened, closed_at=None),
        SimpleNamespace(symbol="BBB", quantity=1.0, avg_price=200.0, opened_at=opened, closed_at=None),
    ]

    resp = export_router.export_portfolio_csv(
        trade_mode=export_router.TradeMode.PAPER,
        db=FakeDb(positions),
        current=current,
    )

    assert isinstance(resp, StreamingResponse)
    text = _read_streaming_response_text(resp)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 2
    assert {r["symbol"] for r in rows} == {"AAA", "BBB"}
    assert {r["trade_mode"] for r in rows} == {export_router.TradeMode.PAPER.value}


def test_list_export_jobs_raises_500_on_repo_error(monkeypatch):
    fake_db = object()
    current = SimpleNamespace(id=1)

    class BoomRepo:
        def __init__(self, db):
            self.db = db

        def get_by_user(self, user_id, status=None, limit=0):
            raise RuntimeError("boom")

    monkeypatch.setattr(export_router, "ExportJobRepository", BoomRepo)

    with pytest.raises(HTTPException) as exc_info:
        export_router.list_export_jobs(
            status=None,
            data_type=None,
            limit=50,
            db=fake_db,
            current=current,
        )
    assert exc_info.value.status_code == 500
