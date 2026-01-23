from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time as dt_time, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from src.infrastructure.db.timezone_utils import IST


class FakeResult:
    def __init__(self, rows: list[Any]):
        self._rows = rows

    def fetchall(self) -> list[Any]:
        return list(self._rows)


class FakeQuery:
    def __init__(self, items: list[Any] | None = None, count_value: int | None = None):
        self._items = list(items or [])
        self._count_value = count_value

    def filter(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
        return self

    def order_by(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
        return self

    def offset(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
        return self

    def limit(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
        return self

    def all(self) -> list[Any]:
        return list(self._items)

    def count(self) -> int:
        if self._count_value is not None:
            return int(self._count_value)
        return len(self._items)


class FakeSession:
    def __init__(
        self,
        *,
        execute_rows: list[Any] | None = None,
        query_plan: dict[Any, list[FakeQuery]] | None = None,
    ):
        self._execute_rows = list(execute_rows or [])
        self._query_plan: dict[Any, list[FakeQuery]] = dict(query_plan or {})

    def execute(self, *_args: Any, **_kwargs: Any) -> FakeResult:
        return FakeResult(self._execute_rows)

    def query(self, model: Any) -> FakeQuery:
        planned = self._query_plan.get(model)
        if planned:
            return planned.pop(0)
        return FakeQuery([])


@dataclass
class StubSchedule:
    task_name: str
    schedule_time: dt_time
    enabled: bool = True
    is_continuous: bool = False
    is_hourly: bool = False
    end_time: dt_time | None = None


class StubScheduleRepo:
    def __init__(self, _db: Any):
        self._db = _db

    def get_all(self) -> list[StubSchedule]:
        return []

    def get_enabled(self) -> list[StubSchedule]:
        return []


class StubAuth:
    def __init__(
        self,
        *,
        session_created_at: float | None = None,
        session_ttl: float | None = None,
        is_authenticated: bool = True,
        client_available: bool = True,
        session_valid: bool = True,
    ):
        self.session_created_at = session_created_at
        self.session_ttl = session_ttl
        self._is_authenticated = is_authenticated
        self._client_available = client_available
        self._session_valid = session_valid

    def is_authenticated(self) -> bool:
        return self._is_authenticated

    def is_session_valid(self) -> bool:
        return self._session_valid

    def get_client(self) -> object | None:
        return object() if self._client_available else None


class StubSessionManager:
    def __init__(self, sessions: dict[int, Any] | None = None, *, include_attr: bool = True):
        if include_attr:
            self._sessions = dict(sessions or {})


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 1, 23, 10, 0, 0, tzinfo=IST)


def _patch_now(monkeypatch: pytest.MonkeyPatch, fixed_now: datetime) -> None:
    from server.app.routers import monitoring

    monkeypatch.setattr(monitoring, "ist_now", lambda: fixed_now)


def test_services_health_impl_converts_timestamps(monkeypatch: pytest.MonkeyPatch, fixed_now: datetime):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)

    # last_heartbeat is naive -> assumed UTC -> converted for age computation.
    last_heartbeat_utc_naive = datetime(2026, 1, 23, 4, 29, 0)  # 09:59 IST

    rows = [
        SimpleNamespace(
            id=1,
            user_id=10,
            service_running=True,
            last_heartbeat=last_heartbeat_utc_naive,
            last_task_execution=None,
            error_count=2,
            last_error="boom",
            created_at=None,
            updated_at=datetime(2026, 1, 23, 4, 30, 0),
        )
    ]

    # _get_user_email_map uses db.query(Users).filter(...).all()
    fake_user = SimpleNamespace(id=10, email="u10@example.com")
    db = FakeSession(
        execute_rows=rows,
        query_plan={
            monitoring.Users: [FakeQuery([fake_user])],
        },
    )

    resp = monitoring._get_services_health_impl(db)
    assert resp.total_running == 1
    assert resp.total_stopped == 0
    assert resp.services_with_recent_errors == 1
    assert resp.services[0].user_email == "u10@example.com"

    # Returned timestamps are made UTC-aware for JSON serialization
    assert resp.services[0].last_heartbeat is not None
    assert resp.services[0].last_heartbeat.tzinfo == UTC

    # Heartbeat age should be ~60s (10:00 IST - 09:59 IST)
    assert resp.services[0].heartbeat_age_seconds is not None
    assert 50 <= resp.services[0].heartbeat_age_seconds <= 70


def test_running_tasks_impl_duration(monkeypatch: pytest.MonkeyPatch, fixed_now: datetime):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)

    running_exec = SimpleNamespace(
        id=1,
        user_id=10,
        task_name="buy_orders",
        executed_at=datetime(2026, 1, 23, 9, 55, 0),  # naive -> treated as IST
        status="running",
        duration_seconds=None,
        execution_type=None,
        details=None,
    )

    fake_user = SimpleNamespace(id=10, email="u10@example.com")
    db = FakeSession(
        query_plan={
            monitoring.IndividualServiceTaskExecution: [FakeQuery([running_exec])],
            monitoring.Users: [FakeQuery([fake_user])],
        }
    )

    resp = monitoring._get_running_tasks_impl(db, None)
    assert resp.total == 1
    assert resp.tasks[0].duration_seconds == pytest.approx(300.0, abs=0.1)


def test_task_metrics_groups_and_rates(monkeypatch: pytest.MonkeyPatch, fixed_now: datetime):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)

    execs = [
        SimpleNamespace(
            id=1,
            user_id=10,
            task_name="t1",
            executed_at=fixed_now - timedelta(minutes=60),
            status="success",
            duration_seconds=1.0,
        ),
        SimpleNamespace(
            id=2,
            user_id=10,
            task_name="t1",
            executed_at=fixed_now - timedelta(minutes=30),
            status="failed",
            duration_seconds=3.0,
        ),
        SimpleNamespace(
            id=3,
            user_id=10,
            task_name="t2",
            executed_at=fixed_now - timedelta(minutes=10),
            status="skipped",
            duration_seconds=2.0,
        ),
    ]

    db = FakeSession(
        query_plan={
            monitoring.IndividualServiceTaskExecution: [FakeQuery(execs)],
        }
    )

    resp = monitoring.get_task_metrics(period_days=7, user_id=None, task_name=None, db=db)

    by_name = {m.task_name: m for m in resp.metrics}
    assert by_name["t1"].total_executions == 2
    assert by_name["t1"].successful_executions == 1
    assert by_name["t1"].failed_executions == 1
    assert by_name["t1"].success_rate == pytest.approx(50.0)

    assert by_name["t2"].total_executions == 1
    assert by_name["t2"].skipped_executions == 1


def test_task_executions_includes_schedule_and_timezone_conversion(
    monkeypatch: pytest.MonkeyPatch, fixed_now: datetime
):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)

    schedule = StubSchedule(task_name="t1", schedule_time=dt_time(10, 0), enabled=True)

    class _Repo(StubScheduleRepo):
        def get_all(self) -> list[StubSchedule]:
            return [schedule]

    monkeypatch.setattr(monitoring, "ServiceScheduleRepository", _Repo)

    exec1 = SimpleNamespace(
        id=1,
        user_id=10,
        task_name="t1",
        executed_at=datetime(2026, 1, 23, 10, 5, 0),  # naive -> treated as IST
        status="success",
        duration_seconds=2.0,
        execution_type="scheduled",
        details={},
    )
    fake_user = SimpleNamespace(id=10, email="u10@example.com")

    db = FakeSession(
        query_plan={
            monitoring.IndividualServiceTaskExecution: [
                FakeQuery([exec1], count_value=1),
                FakeQuery([exec1]),
            ],
            monitoring.Users: [FakeQuery([fake_user])],
        }
    )

    resp = monitoring.get_task_executions(
        page=1,
        page_size=50,
        user_id=None,
        task_name=None,
        status=None,
        start_date=None,
        end_date=None,
        db=db,
    )

    assert resp.total == 1
    assert resp.items[0].scheduled_time == "10:00"
    assert resp.items[0].time_difference_seconds == pytest.approx(300.0, abs=0.1)
    assert resp.items[0].executed_at is not None
    assert resp.items[0].executed_at.tzinfo == UTC


def test_schedule_compliance_missed_delayed_and_on_track(monkeypatch: pytest.MonkeyPatch, fixed_now: datetime):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)

    sched_missed = StubSchedule(task_name="t_missed", schedule_time=dt_time(9, 0), enabled=True)
    # Note: implementation converts last_execution to UTC before comparing .time() vs schedule_time,
    # so use a schedule_time that is still earlier than the UTC time component to exercise the
    # "delayed" branch.
    sched_delayed = StubSchedule(task_name="t_delayed", schedule_time=dt_time(2, 0), enabled=True)
    sched_on_track = StubSchedule(task_name="t_ok", schedule_time=dt_time(11, 0), enabled=True)

    class _Repo(StubScheduleRepo):
        def get_enabled(self) -> list[StubSchedule]:
            return [sched_missed, sched_delayed, sched_on_track]

    monkeypatch.setattr(monitoring, "ServiceScheduleRepository", _Repo)

    today = fixed_now.date()
    delayed_exec = SimpleNamespace(
        executed_at=datetime.combine(today, dt_time(9, 20), tzinfo=IST),
        status="success",
    )

    db = FakeSession(
        query_plan={
            monitoring.IndividualServiceTaskExecution: [
                FakeQuery([]),
                FakeQuery([delayed_exec]),
                FakeQuery([]),
            ]
        }
    )

    resp = monitoring.get_schedule_compliance(db=db)
    by_task = {t.task_name: t for t in resp.tasks}

    assert resp.total_missed == 1
    assert resp.total_delayed == 1

    assert by_task["t_missed"].compliance_status == "missed"
    assert by_task["t_delayed"].compliance_status == "delayed"
    # For a future schedule time, it should be on_track and next_expected set for today
    assert by_task["t_ok"].compliance_status == "on_track"
    assert by_task["t_ok"].next_expected_execution is not None


def test_reauth_statistics_calculates_success_rate_and_avg_time(monkeypatch: pytest.MonkeyPatch, fixed_now: datetime):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)

    errs = [
        SimpleNamespace(
            user_id=10,
            occurred_at=fixed_now - timedelta(minutes=120),
            error_message="reauth successful",
        ),
        SimpleNamespace(
            user_id=10,
            occurred_at=fixed_now - timedelta(minutes=60),
            error_message="reauth failed",
        ),
    ]
    fake_user = SimpleNamespace(id=10, email="u10@example.com")

    db = FakeSession(
        query_plan={
            monitoring.ErrorLog: [FakeQuery(errs)],
            monitoring.Users: [FakeQuery([fake_user])],
        }
    )

    resp = monitoring.get_reauth_statistics(period_days=1, user_id=None, db=db)
    assert len(resp.statistics) == 1
    stat = resp.statistics[0]
    assert stat.reauth_count_24h == 2
    assert stat.success_rate == pytest.approx(50.0)
    assert stat.avg_time_between_reauth_minutes is not None
    assert stat.avg_time_between_reauth_minutes == pytest.approx(60.0, abs=0.1)


def test_active_sessions_impl_handles_session_manager_access_error(
    monkeypatch: pytest.MonkeyPatch, fixed_now: datetime
):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)

    class _BadSessions:
        @property
        def items(self):  # pragma: no cover
            raise RuntimeError("boom")

    class _Mgr:
        @property
        def _sessions(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(monitoring, "get_shared_session_manager", lambda: _Mgr())

    db = FakeSession(query_plan={monitoring.Users: [FakeQuery([])]})
    resp = monitoring._get_active_sessions_impl(db)
    assert resp.sessions == []


def test_active_sessions_impl_handles_missing_or_empty_sessions(
    monkeypatch: pytest.MonkeyPatch, fixed_now: datetime
):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)

    # Missing _sessions attribute
    monkeypatch.setattr(
        monitoring,
        "get_shared_session_manager",
        lambda: StubSessionManager(include_attr=False),
    )

    db = FakeSession(query_plan={monitoring.Users: [FakeQuery([])]})
    resp = monitoring._get_active_sessions_impl(db)
    assert resp.total_active == 0

    # Empty sessions dict
    monkeypatch.setattr(
        monitoring,
        "get_shared_session_manager",
        lambda: StubSessionManager({}, include_attr=True),
    )

    resp2 = monitoring._get_active_sessions_impl(db)
    assert resp2.total_active == 0
    assert resp2.sessions == []


def test_active_sessions_impl_classifies_expiring(monkeypatch: pytest.MonkeyPatch, fixed_now: datetime):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)

    created_at = (fixed_now - timedelta(minutes=50)).timestamp()
    auth_valid = StubAuth(session_created_at=created_at, session_ttl=55 * 60, is_authenticated=True)
    auth_expiring = StubAuth(
        session_created_at=(fixed_now - timedelta(minutes=53)).timestamp(),
        session_ttl=55 * 60,
        is_authenticated=True,
    )

    monkeypatch.setattr(
        monitoring,
        "get_shared_session_manager",
        lambda: StubSessionManager({10: auth_valid, 11: auth_expiring}),
    )

    users = [
        SimpleNamespace(id=10, email="u10@example.com"),
        SimpleNamespace(id=11, email="u11@example.com"),
    ]
    db = FakeSession(query_plan={monitoring.Users: [FakeQuery(users)]})

    resp = monitoring._get_active_sessions_impl(db)
    assert resp.total_active == 0  # 50min age => remaining ~5min -> expiring_soon
    assert resp.expiring_soon == 2
    assert resp.expired == 0


def test_reauth_history_and_auth_errors(monkeypatch: pytest.MonkeyPatch, fixed_now: datetime):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)

    errors = [
        SimpleNamespace(
            id=1,
            user_id=10,
            occurred_at=fixed_now,
            error_message="Reauth successful: jwt token expired",
            context={"method": "get_client"},
        ),
        SimpleNamespace(
            id=2,
            user_id=10,
            occurred_at=fixed_now,
            error_message="900901 JWT token expired unauthorized",
            context={"endpoint": "/api/x", "method": "call"},
            error_type="auth",
        ),
    ]

    fake_user = SimpleNamespace(id=10, email="u10@example.com")

    db = FakeSession(
        query_plan={
            monitoring.ErrorLog: [
                FakeQuery(errors, count_value=2),
                FakeQuery(errors, count_value=2),
            ],
            monitoring.Users: [FakeQuery([fake_user]), FakeQuery([fake_user])],
        }
    )

    history = monitoring.get_reauth_history(
        page=1,
        page_size=50,
        user_id=None,
        start_date=None,
        end_date=None,
        db=db,
    )
    assert history.total == 2
    assert history.events[0].status in {"success", "failed", "rate_limited"}

    auth_errs = monitoring.get_auth_errors(
        page=1,
        page_size=50,
        user_id=None,
        start_date=None,
        end_date=None,
        db=db,
    )
    assert auth_errs.total == 2
    assert any(e.error_code == "900901" for e in auth_errs.errors)


def test_monitoring_dashboard_happy_path(monkeypatch: pytest.MonkeyPatch, fixed_now: datetime):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)

    # Patch schedule repository to provide predictable schedules
    schedule = StubSchedule(task_name="buy_orders", schedule_time=dt_time(10, 0))

    class _Repo(StubScheduleRepo):
        def get_all(self) -> list[StubSchedule]:
            return [schedule]

    monkeypatch.setattr(monitoring, "ServiceScheduleRepository", _Repo)

    # Use small internal impl results to exercise alert generation
    def _services_health(_db: Any):
        return monitoring.ServicesHealthResponse(
            services=[
                monitoring.ServiceHealthStatus(
                    user_id=10,
                    user_email="u10@example.com",
                    service_running=True,
                    last_heartbeat=fixed_now.astimezone(UTC),
                    heartbeat_age_seconds=400.0,
                    last_task_execution=None,
                    last_task_name=None,
                    error_count=6,
                    last_error=None,
                    updated_at=fixed_now.astimezone(UTC),
                )
            ],
            total_running=1,
            total_stopped=0,
            services_with_recent_errors=1,
        )

    def _sessions(_db: Any):
        return monitoring.ActiveSessionsResponse(
            sessions=[
                monitoring.ActiveSession(
                    user_id=10,
                    user_email="u10@example.com",
                    session_created_at=fixed_now,
                    session_age_minutes=1.0,
                    session_status="expired",
                    ttl_remaining_minutes=0.0,
                    is_authenticated=False,
                    client_available=False,
                )
            ],
            total_active=0,
            expiring_soon=0,
            expired=1,
        )

    def _running(_db: Any, _user_id: int | None = None):
        return monitoring.RunningTasksResponse(tasks=[], total=0)

    monkeypatch.setattr(monitoring, "_get_services_health_impl", _services_health)
    monkeypatch.setattr(monitoring, "_get_active_sessions_impl", _sessions)
    monkeypatch.setattr(monitoring, "_get_running_tasks_impl", _running)

    # Provide DB query plan used by dashboard (counts + samples + recent lists)
    exec1 = SimpleNamespace(
        id=1,
        user_id=10,
        task_name="buy_orders",
        executed_at=fixed_now,
        status="success",
        duration_seconds=1.0,
        execution_type="scheduled",
        details={},
    )

    reauth_error = SimpleNamespace(
        id=1,
        user_id=10,
        occurred_at=fixed_now,
        error_message="reauth successful",
        context={"action": "get_client"},
    )

    users = [SimpleNamespace(id=10, email="u10@example.com")]

    db = FakeSession(
        query_plan={
            monitoring.IndividualServiceTaskExecution: [
                FakeQuery([], count_value=3),
                FakeQuery([], count_value=2),
                FakeQuery([], count_value=1),
                FakeQuery([exec1]),
            ],
            monitoring.ErrorLog: [
                FakeQuery([], count_value=5),
                FakeQuery([reauth_error]),
                FakeQuery([], count_value=2),
                FakeQuery([reauth_error]),
            ],
            monitoring.Users: [FakeQuery(users), FakeQuery(users)],
        }
    )

    resp = monitoring.get_monitoring_dashboard(db=db)
    assert resp.summary.total_services == 1
    assert resp.alerts.critical_count >= 1
