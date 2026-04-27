from __future__ import annotations

import importlib
import sys
from datetime import datetime
from types import ModuleType, SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

IST = ZoneInfo("Asia/Kolkata")


class FakeScheduler:
    def __init__(self):
        self.running = False
        self.jobs: list[SimpleNamespace] = []

    def add_job(
        self, func, trigger, id: str, name: str, replace_existing: bool = True
    ):  # noqa: A002
        self.jobs.append(SimpleNamespace(func=func, trigger=trigger, id=id, name=name))

    def start(self):
        self.running = True

    def shutdown(self):
        self.running = False

    def get_jobs(self):
        return list(self.jobs)


def _import_scheduler_module() -> ModuleType:
    """Import server scheduler with apscheduler stubs (apscheduler may not be installed)."""

    apscheduler_asyncio = ModuleType("apscheduler.schedulers.asyncio")

    class _AsyncIOScheduler(FakeScheduler):
        pass

    apscheduler_asyncio.AsyncIOScheduler = _AsyncIOScheduler

    apscheduler_cron = ModuleType("apscheduler.triggers.cron")

    class _CronTrigger:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    apscheduler_cron.CronTrigger = _CronTrigger

    sys.modules.setdefault("apscheduler", ModuleType("apscheduler"))
    sys.modules.setdefault("apscheduler.schedulers", ModuleType("apscheduler.schedulers"))
    sys.modules["apscheduler.schedulers.asyncio"] = apscheduler_asyncio
    sys.modules.setdefault("apscheduler.triggers", ModuleType("apscheduler.triggers"))
    sys.modules["apscheduler.triggers.cron"] = apscheduler_cron

    # Avoid the package-level export `server.app.jobs.scheduler` (an instance) shadowing
    # the actual `server.app.jobs.scheduler` module.
    sys.modules.pop("server.app.jobs.scheduler", None)
    sys.modules.pop("server.app.jobs", None)

    return importlib.import_module("server.app.jobs.scheduler")


def test_start_scheduler_adds_job_and_starts(monkeypatch: pytest.MonkeyPatch):
    mod = _import_scheduler_module()

    fake = FakeScheduler()
    monkeypatch.setattr(mod, "scheduler", fake)

    mod.start_scheduler()

    assert fake.running is True
    assert len(fake.jobs) == 3
    assert {j.id for j in fake.jobs} == {
        "mtm_daily_update",
        "billing_reconcile_daily",
        "performance_bills_month_close",
    }


def test_start_scheduler_is_idempotent(monkeypatch: pytest.MonkeyPatch):
    mod = _import_scheduler_module()

    fake = FakeScheduler()
    fake.running = True
    monkeypatch.setattr(mod, "scheduler", fake)

    mod.start_scheduler()

    assert len(fake.jobs) == 0


def test_stop_scheduler_shuts_down(monkeypatch: pytest.MonkeyPatch):
    mod = _import_scheduler_module()

    fake = FakeScheduler()
    fake.running = True
    monkeypatch.setattr(mod, "scheduler", fake)

    mod.stop_scheduler()

    assert fake.running is False


def test_job_mtm_update_sums_results(monkeypatch: pytest.MonkeyPatch):
    mod = _import_scheduler_module()

    monkeypatch.setattr(
        mod,
        "update_mtm_for_all_users",
        lambda: {
            1: {"updated": 2, "failed": 1, "skipped": 0},
            2: {"updated": 0, "failed": 0, "skipped": 3},
        },
    )

    # Should not raise
    mod.job_mtm_update()


def test_closed_month_to_bill_first_of_month():
    mod = _import_scheduler_module()
    # March 1 00:30 IST → bill February of same year
    assert mod.closed_month_to_bill(datetime(2026, 3, 1, 0, 30, tzinfo=IST)) == (2026, 2)
    # January 1 → December previous year
    assert mod.closed_month_to_bill(datetime(2026, 1, 1, 0, 30, tzinfo=IST)) == (2025, 12)


def test_closed_month_to_bill_mid_month():
    mod = _import_scheduler_module()
    assert mod.closed_month_to_bill(datetime(2026, 3, 18, 12, 0, tzinfo=IST)) == (2026, 2)


def test_job_performance_bills_month_close_calls_service(monkeypatch: pytest.MonkeyPatch):
    mod = _import_scheduler_module()

    captured: dict[str, object] = {}

    class _FakeSvc:
        def __init__(self, db):
            captured["db"] = db

        def close_month_for_all_broker_users(self, year, month):
            captured["year"], captured["month"] = year, month
            return ["bill-a"]

    class _Ctx:
        def __enter__(self):
            return object()

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(mod, "closed_month_to_bill", lambda _now: (2026, 3))
    monkeypatch.setattr(
        "src.infrastructure.db.session.SessionLocal",
        lambda: _Ctx(),
    )
    monkeypatch.setattr(
        "src.application.services.performance_billing_service.PerformanceBillingService",
        _FakeSvc,
    )

    mod.job_performance_bills_month_close()

    assert captured.get("year") == 2026
    assert captured.get("month") == 3
