from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest


class FakeScheduler:
    def __init__(self):
        self.running = False
        self.jobs: list[SimpleNamespace] = []

    def add_job(self, func, trigger, id: str, name: str, replace_existing: bool = True):  # noqa: A002
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

    import importlib

    return importlib.import_module("server.app.jobs.scheduler")


def test_start_scheduler_adds_job_and_starts(monkeypatch: pytest.MonkeyPatch):
    mod = _import_scheduler_module()

    fake = FakeScheduler()
    monkeypatch.setattr(mod, "scheduler", fake)

    mod.start_scheduler()

    assert fake.running is True
    assert len(fake.jobs) == 1
    assert fake.jobs[0].id == "mtm_daily_update"


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
