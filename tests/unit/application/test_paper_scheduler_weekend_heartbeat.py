# ruff: noqa: PLC0415
"""
Regression: the paper-trading scheduler must keep writing its liveness heartbeat on
weekends, even though it runs no trading tasks.

Previously the per-minute ``update_heartbeat`` call sat *below* the weekend ``continue``
in ``_run_paper_trading_scheduler``, so on Sat/Sun the heartbeat froze for the whole
weekend while the thread was still alive — and the monitoring dashboard flagged the
healthy service as critically "stale". This drives a single weekend loop iteration and
asserts the heartbeat is written.
"""

from datetime import datetime
from unittest.mock import MagicMock

from src.application.services import multi_user_trading_service as mus
from src.application.services.multi_user_trading_service import MultiUserTradingService


def test_weekend_iteration_writes_heartbeat(monkeypatch):
    # Clear module-level shared state so lock/thread checks start clean.
    mus._shared_services.clear()
    mus._shared_service_threads.clear()
    mus._shared_locks.clear()
    mus._shared_start_locks.clear()
    mus._shared_lock_keys.clear()

    # No-op user logger (avoid file I/O and emoji encoding on Windows).
    monkeypatch.setattr(mus, "get_user_logger", lambda **_kwargs: MagicMock())

    # Lock acquisition always succeeds; cleanup + release are no-ops.
    monkeypatch.setattr(
        mus, "_try_acquire_paper_scheduler_lock", lambda *_a, **_k: (True, "lock-1")
    )
    monkeypatch.setattr(mus, "_cleanup_stale_paper_scheduler_lock", lambda *_a, **_k: None)
    monkeypatch.setattr(mus, "_release_paper_scheduler_lock", lambda *_a, **_k: None)

    # ScheduleManager is only used on the weekday task path; stub it.
    monkeypatch.setattr(mus, "ScheduleManager", lambda *_a, **_k: MagicMock())

    # Skip the thread-exit status bookkeeping in the finally block.
    monkeypatch.setattr(mus, "should_apply_thread_exit_status", lambda *_a, **_k: False)

    # Thread-local DB session factory (imported inside the method).
    monkeypatch.setattr(
        "src.infrastructure.db.session.SessionLocal",
        lambda: MagicMock(name="thread_db"),
    )

    # Spy on the heartbeat repository (same return_value instance for every construction).
    repo_instance = MagicMock(name="ServiceStatusRepository_instance")
    monkeypatch.setattr(mus, "ServiceStatusRepository", MagicMock(return_value=repo_instance))

    # Freeze "now" to a Saturday (2026-06-27 is a Saturday).
    saturday = datetime(2026, 6, 27, 10, 0, 0)
    assert saturday.weekday() == 5  # sanity: Saturday
    monkeypatch.setattr(mus, "ist_now", lambda: saturday)

    # Alive service; stop the loop the first time it sleeps (after the weekend heartbeat).
    service = MagicMock(name="service")
    service.running = True
    service.shutdown_requested = False

    def _stop_after_first_sleep(_seconds):
        service.running = False

    monkeypatch.setattr(
        mus, "time", type("_T", (), {"sleep": staticmethod(_stop_after_first_sleep)})
    )

    manager = MultiUserTradingService(db=MagicMock())
    manager._run_paper_trading_scheduler(service, user_id=1, service_generation=1)

    # Initial heartbeat (pre-loop) + weekend-branch heartbeat = 2.
    # Without the weekend fix this would be 1 (only the initial heartbeat).
    assert repo_instance.update_heartbeat.call_count == 2
    repo_instance.update_heartbeat.assert_called_with(1)
