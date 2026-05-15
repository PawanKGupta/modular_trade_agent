# ruff: noqa: E501, PLC0415
"""Additional branch coverage for monitoring router (health tz paths, auth logs, dashboard)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from datetime import time as dt_time
from types import SimpleNamespace

import pytest

from src.infrastructure.db.timezone_utils import IST
from tests.unit.server.routers.test_monitoring_router import (
    FakeQuery,
    FakeSession,
    StubSchedule,
    StubScheduleRepo,
    _patch_now,
)


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 1, 23, 10, 0, 0, tzinfo=IST)


def test_services_health_stale_running_warns(
    monkeypatch: pytest.MonkeyPatch, fixed_now: datetime, caplog
):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)
    # Naive UTC heartbeat >10 minutes before "now" (IST) so age > 600s and service_running.
    last_hb = datetime(2026, 1, 23, 3, 0, 0)
    rows = [
        SimpleNamespace(
            id=1,
            user_id=10,
            service_running=True,
            last_heartbeat=last_hb,
            last_task_execution=None,
            error_count=0,
            last_error=None,
            created_at=None,
            updated_at=last_hb,
        )
    ]
    fake_user = SimpleNamespace(id=10, email="u10@example.com")
    db = FakeSession(
        execute_rows=rows,
        query_plan={monitoring.Users: [FakeQuery([fake_user])]},
    )
    monitoring._get_services_health_impl(db)
    assert any("stale" in r.message.lower() for r in caplog.records)


def test_services_health_converts_non_utc_timestamps_on_status(
    monkeypatch: pytest.MonkeyPatch, fixed_now: datetime
):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)
    last_hb = datetime(2026, 1, 23, 9, 55, 0, tzinfo=IST)
    last_task = datetime(2026, 1, 23, 9, 56, 0, tzinfo=IST)
    updated = datetime(2026, 1, 23, 9, 57, 0, tzinfo=IST)
    rows = [
        SimpleNamespace(
            id=2,
            user_id=11,
            service_running=False,
            last_heartbeat=last_hb,
            last_task_execution=last_task,
            error_count=1,
            last_error="x",
            created_at=None,
            updated_at=updated,
        )
    ]
    fake_user = SimpleNamespace(id=11, email="u11@example.com")
    db = FakeSession(
        execute_rows=rows,
        query_plan={monitoring.Users: [FakeQuery([fake_user])]},
    )
    resp = monitoring._get_services_health_impl(db)
    svc = resp.services[0]
    assert svc.last_heartbeat is not None
    assert svc.last_heartbeat.tzinfo == UTC
    assert svc.last_task_execution is not None
    assert svc.last_task_execution.tzinfo == UTC
    assert svc.updated_at is not None
    assert svc.updated_at.tzinfo == UTC


def test_get_task_executions_filters_and_http_error(
    monkeypatch: pytest.MonkeyPatch, fixed_now: datetime
):
    from fastapi import HTTPException

    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)

    class _Repo(StubScheduleRepo):
        def get_all(self):
            return []

    monkeypatch.setattr(monitoring, "ServiceScheduleRepository", _Repo)

    fake_user = SimpleNamespace(id=10, email="u10@example.com")

    class _BadSession(FakeSession):
        def query(self, model):
            if model is monitoring.IndividualServiceTaskExecution:
                raise RuntimeError("db exploded")
            return super().query(model)

    bad = _BadSession(
        query_plan={
            monitoring.Users: [FakeQuery([fake_user])],
        },
    )
    with pytest.raises(HTTPException) as ei:
        monitoring.get_task_executions(
            page=1,
            page_size=50,
            user_id=10,
            task_name="t1",
            status="success",
            start_date=date(2026, 1, 22),
            end_date=date(2026, 1, 24),
            db=bad,
        )
    assert ei.value.status_code == 500
    assert "db exploded" in str(ei.value.detail)


def test_get_running_tasks_http_error(monkeypatch: pytest.MonkeyPatch):
    from fastapi import HTTPException

    from server.app.routers import monitoring

    monkeypatch.setattr(
        monitoring,
        "_get_running_tasks_impl",
        lambda db, user_id=None: (_ for _ in ()).throw(RuntimeError("no tasks")),
    )
    with pytest.raises(HTTPException) as ei:
        monitoring.get_running_tasks(user_id=None, db=FakeSession())
    assert ei.value.status_code == 500


def test_get_task_metrics_filters_and_non_utc_last_execution(
    monkeypatch: pytest.MonkeyPatch, fixed_now: datetime
):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)
    ex = SimpleNamespace(
        id=1,
        user_id=10,
        task_name="alpha",
        executed_at=fixed_now - timedelta(hours=1),
        status="success",
        duration_seconds=2.0,
    )
    ex2 = SimpleNamespace(
        id=2,
        user_id=10,
        task_name="alpha",
        executed_at=datetime(2026, 1, 23, 8, 0, 0, tzinfo=IST),
        status="failed",
        duration_seconds=1.0,
    )
    db = FakeSession(
        query_plan={
            monitoring.IndividualServiceTaskExecution: [FakeQuery([ex, ex2])],
        },
    )
    resp = monitoring.get_task_metrics(
        period_days=7,
        user_id=10,
        task_name="alpha",
        db=db,
    )
    assert len(resp.metrics) == 1
    m = resp.metrics[0]
    assert m.last_execution_at is not None
    assert m.last_execution_at.tzinfo == UTC


def test_get_task_metrics_http_error(monkeypatch: pytest.MonkeyPatch):
    from fastapi import HTTPException

    from server.app.routers import monitoring

    class _Bad(FakeSession):
        def query(self, model):
            raise OSError("metrics down")

    with pytest.raises(HTTPException) as ei:
        monitoring.get_task_metrics(period_days=7, user_id=None, task_name=None, db=_Bad())
    assert ei.value.status_code == 500


def test_get_schedule_compliance_http_error(monkeypatch: pytest.MonkeyPatch):
    from fastapi import HTTPException

    from server.app.routers import monitoring

    class _BoomRepo:
        def __init__(self, _db):
            raise RuntimeError("sched")

    monkeypatch.setattr(monitoring, "ServiceScheduleRepository", _BoomRepo)
    with pytest.raises(HTTPException) as ei:
        monitoring.get_schedule_compliance(db=FakeSession())
    assert ei.value.status_code == 500


def test_get_active_sessions_http_error(monkeypatch: pytest.MonkeyPatch):
    from fastapi import HTTPException

    from server.app.routers import monitoring

    monkeypatch.setattr(
        monitoring,
        "_get_active_sessions_impl",
        lambda db: (_ for _ in ()).throw(RuntimeError("sessions")),
    )
    with pytest.raises(HTTPException) as ei:
        monitoring.get_active_sessions(db=FakeSession())
    assert ei.value.status_code == 500


def test_get_reauth_history_filters_and_branches(monkeypatch: pytest.MonkeyPatch):
    from server.app.routers import monitoring

    errs = [
        SimpleNamespace(
            id=1,
            user_id=5,
            error_message="reauth successful after jwt expired",
            occurred_at=datetime(2026, 1, 20, 12, 0, 0),
            context={"method": "POST"},
        ),
        SimpleNamespace(
            id=2,
            user_id=5,
            error_message="re-authentication rate limited",
            occurred_at=datetime(2026, 1, 21, 12, 0, 0),
            context=None,
        ),
        SimpleNamespace(
            id=3,
            user_id=6,
            error_message="unauthorized access",
            occurred_at=datetime(2026, 1, 22, 12, 0, 0),
            context=None,
        ),
    ]
    u5 = SimpleNamespace(id=5, email="a@b.c")
    u6 = SimpleNamespace(id=6, email="c@d.e")
    fq = FakeQuery(errs, count_value=3)
    db = FakeSession(
        query_plan={
            monitoring.ErrorLog: [fq],
            monitoring.Users: [FakeQuery([u5, u6])],
        },
    )
    out = monitoring.get_reauth_history(
        page=1,
        page_size=10,
        user_id=5,
        start_date=date(2026, 1, 19),
        end_date=date(2026, 1, 23),
        db=db,
    )
    assert out.total == 3
    statuses = {e.status for e in out.events}
    assert "success" in statuses
    assert "rate_limited" in statuses


def test_get_auth_errors_branches(monkeypatch: pytest.MonkeyPatch):
    from server.app.routers import monitoring

    errs = [
        SimpleNamespace(
            id=1,
            user_id=1,
            error_message="900901 jwt token expired",
            error_type="x",
            occurred_at=datetime(2026, 1, 1),
            context={"endpoint": "/x", "method": "GET"},
        ),
        SimpleNamespace(
            id=2,
            user_id=1,
            error_message="Invalid JWT token format",
            error_type="x",
            occurred_at=datetime(2026, 1, 2),
            context=None,
        ),
        SimpleNamespace(
            id=3,
            user_id=1,
            error_message="invalid credentials for user",
            error_type="x",
            occurred_at=datetime(2026, 1, 3),
            context=None,
        ),
        SimpleNamespace(
            id=4,
            user_id=1,
            error_message="Unauthorized request",
            error_type="x",
            occurred_at=datetime(2026, 1, 4),
            context=None,
        ),
    ]
    u1 = SimpleNamespace(id=1, email="u@u.u")
    fq = FakeQuery(errs, count_value=4)
    db = FakeSession(
        query_plan={
            monitoring.ErrorLog: [fq],
            monitoring.Users: [FakeQuery([u1])],
        },
    )
    out = monitoring.get_auth_errors(
        page=1, page_size=10, user_id=1, start_date=None, end_date=None, db=db
    )
    types_found = {e.error_type for e in out.errors}
    assert "JWT expired" in types_found
    assert "Invalid JWT token" in types_found
    assert "Invalid credentials" in types_found
    assert "Unauthorized" in types_found


def test_get_reauth_statistics_user_filter_and_avg_gap(
    monkeypatch: pytest.MonkeyPatch, fixed_now: datetime
):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)
    t0 = fixed_now - timedelta(hours=3)
    t1 = fixed_now - timedelta(hours=2)
    t2 = fixed_now - timedelta(hours=1)
    errs = [
        SimpleNamespace(id=1, user_id=9, error_message="reauth successful", occurred_at=t0),
        SimpleNamespace(id=2, user_id=9, error_message="reauth failed", occurred_at=t1),
        SimpleNamespace(id=3, user_id=9, error_message="reauth successful", occurred_at=t2),
    ]
    u9 = SimpleNamespace(id=9, email="n@n.n")
    db = FakeSession(
        query_plan={
            monitoring.ErrorLog: [FakeQuery(errs)],
            monitoring.Users: [FakeQuery([u9])],
        },
    )
    out = monitoring.get_reauth_statistics(period_days=30, user_id=9, db=db)
    assert len(out.statistics) == 1
    st = out.statistics[0]
    assert st.success_rate > 0
    assert st.avg_time_between_reauth_minutes is not None


def test_get_reauth_statistics_http_error(monkeypatch: pytest.MonkeyPatch):
    from fastapi import HTTPException

    from server.app.routers import monitoring

    class _Bad(FakeSession):
        def query(self, model):
            raise RuntimeError("x")

    with pytest.raises(HTTPException) as ei:
        monitoring.get_reauth_statistics(period_days=1, user_id=None, db=_Bad())
    assert ei.value.status_code == 500


def test_get_monitoring_dashboard_happy_path(monkeypatch: pytest.MonkeyPatch, fixed_now: datetime):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)
    today = fixed_now.date()

    status_row = SimpleNamespace(
        id=1,
        user_id=10,
        service_running=True,
        last_heartbeat=datetime(2020, 1, 1, 0, 0, 0),
        last_task_execution=None,
        error_count=10,
        last_error="errors",
        created_at=None,
        updated_at=datetime.combine(today, dt_time(9, 30, 0)),
    )
    u10 = SimpleNamespace(id=10, email="u10@example.com")

    ex_recent = SimpleNamespace(
        id=100,
        user_id=10,
        task_name="buy_orders",
        executed_at=datetime.combine(today, dt_time(10, 5, 0)),
        status="success",
        duration_seconds=1.0,
        execution_type="scheduled",
        details={},
    )
    sched = StubSchedule(task_name="buy_orders", schedule_time=dt_time(10, 0), enabled=True)

    class _SchedRepo(StubScheduleRepo):
        def get_all(self):
            return [sched]

    running_ex = SimpleNamespace(
        id=200,
        user_id=10,
        task_name="sell_monitor",
        executed_at=fixed_now - timedelta(minutes=2),
        status="running",
        duration_seconds=None,
        execution_type=None,
        details=None,
    )

    reauth_sample = [
        SimpleNamespace(id=1, user_id=10, error_message="reauth successful", occurred_at=fixed_now),
        SimpleNamespace(id=2, user_id=10, error_message="reauth failed", occurred_at=fixed_now),
    ]
    recent_reauth = [
        SimpleNamespace(
            id=3,
            user_id=10,
            error_message="reauth successful with jwt",
            occurred_at=fixed_now,
            context={"method": "PATCH"},
        )
    ]

    monkeypatch.setattr(monitoring, "ServiceScheduleRepository", _SchedRepo)

    class _SM:
        _sessions = {}

    monkeypatch.setattr(monitoring, "get_shared_session_manager", lambda: _SM())

    db = FakeSession(
        execute_rows=[status_row],
        query_plan={
            monitoring.Users: [
                FakeQuery([u10]),
                FakeQuery([u10]),
                FakeQuery([u10]),
                FakeQuery([u10]),
            ],
            monitoring.IndividualServiceTaskExecution: [
                FakeQuery([], count_value=12),
                FakeQuery([], count_value=9),
                FakeQuery([], count_value=2),
                FakeQuery([ex_recent]),
                FakeQuery([running_ex]),
            ],
            monitoring.ErrorLog: [
                FakeQuery([], count_value=4),
                FakeQuery(reauth_sample),
                FakeQuery([], count_value=3),
                FakeQuery(recent_reauth),
            ],
        },
    )

    dash = monitoring.get_monitoring_dashboard(db=db)
    assert dash.summary.tasks_executed_today == 12
    assert dash.summary.reauth_count_24h == 4
    assert dash.alerts.critical_count + dash.alerts.warning_count >= 1
    assert len(dash.recent_task_executions) == 1
    assert dash.recent_task_executions[0].scheduled_time == "10:00"
    assert len(dash.recent_reauth_events) == 1
    assert len(dash.running_tasks) == 1


def test_get_monitoring_dashboard_with_minimal_queries(
    monkeypatch: pytest.MonkeyPatch, fixed_now: datetime
):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)
    status_row = SimpleNamespace(
        id=1,
        user_id=10,
        service_running=False,
        last_heartbeat=None,
        last_task_execution=None,
        error_count=0,
        last_error=None,
        created_at=None,
        updated_at=None,
    )
    u10 = SimpleNamespace(id=10, email="u10@example.com")
    ex = SimpleNamespace(
        id=1,
        user_id=10,
        task_name="t",
        executed_at=fixed_now,
        status="success",
        duration_seconds=1.0,
        execution_type="scheduled",
        details=None,
    )

    monkeypatch.setattr(monitoring, "ServiceScheduleRepository", StubScheduleRepo)
    monkeypatch.setattr(
        monitoring,
        "_get_running_tasks_impl",
        lambda db, user_id=None: (_ for _ in ()).throw(RuntimeError("rt")),
    )

    class _SM:
        _sessions = {}

    monkeypatch.setattr(monitoring, "get_shared_session_manager", lambda: _SM())

    db = FakeSession(
        execute_rows=[status_row],
        query_plan={
            monitoring.Users: [
                FakeQuery([u10]),
                FakeQuery([u10]),
                FakeQuery([u10]),
                FakeQuery([u10]),
            ],
            monitoring.IndividualServiceTaskExecution: [
                FakeQuery([], count_value=0),
                FakeQuery([], count_value=0),
                FakeQuery([], count_value=0),
                FakeQuery([ex]),
                FakeQuery([]),
            ],
            monitoring.ErrorLog: [
                FakeQuery([], count_value=0),
                FakeQuery([]),
                FakeQuery([], count_value=0),
                FakeQuery([]),
            ],
        },
    )
    dash = monitoring.get_monitoring_dashboard(db=db)
    assert dash.running_tasks == []


def test_get_monitoring_dashboard_outer_http_exception_passthrough(monkeypatch: pytest.MonkeyPatch):
    from fastapi import HTTPException

    from server.app.routers import monitoring

    def _raise_http(db):
        raise HTTPException(status_code=418, detail="nope")

    monkeypatch.setattr(monitoring, "_get_services_health_impl", _raise_http)
    with pytest.raises(HTTPException) as ei:
        monitoring.get_monitoring_dashboard(db=FakeSession())
    assert ei.value.status_code == 418


def test_get_active_sessions_impl_no_sessions_attr(monkeypatch: pytest.MonkeyPatch):
    from server.app.routers import monitoring

    class _SM:
        pass

    monkeypatch.setattr(monitoring, "get_shared_session_manager", lambda: _SM())
    out = monitoring._get_active_sessions_impl(FakeSession())
    assert out.total_active == 0


def test_get_active_sessions_impl_snapshot_access_error(monkeypatch: pytest.MonkeyPatch):
    from server.app.routers import monitoring

    class _SM:
        @property
        def _sessions(self):
            raise RuntimeError("locked")

    monkeypatch.setattr(monitoring, "get_shared_session_manager", lambda: _SM())
    out = monitoring._get_active_sessions_impl(FakeSession())
    assert out.sessions == []


def test_get_active_sessions_impl_auth_inner_error(
    monkeypatch: pytest.MonkeyPatch, fixed_now: datetime
):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)

    class _BadAuth:
        session_created_at = fixed_now.timestamp()
        session_ttl = 3600.0

        def is_authenticated(self):
            raise RuntimeError("auth check")

        def is_session_valid(self):
            return True

        def get_client(self):
            return object()

    class _SM:
        _sessions = {42: _BadAuth()}

    u42 = SimpleNamespace(id=42, email="z@z.z")
    monkeypatch.setattr(monitoring, "get_shared_session_manager", lambda: _SM())
    db = FakeSession(query_plan={monitoring.Users: [FakeQuery([u42])]})
    out = monitoring._get_active_sessions_impl(db)
    assert len(out.sessions) == 1
    assert out.sessions[0].is_authenticated is False


def test_get_active_sessions_impl_slow_get_client_logs(
    monkeypatch: pytest.MonkeyPatch, fixed_now: datetime, caplog
):
    from server.app.routers import monitoring

    _patch_now(monkeypatch, fixed_now)

    ticks = iter([1000.0, 1000.01, 1000.02, 1000.03, 1000.80, 1000.81])
    monkeypatch.setattr(monitoring.time, "time", lambda: next(ticks))

    class _Auth:
        session_created_at = fixed_now.timestamp()
        session_ttl = 7200.0

        def is_authenticated(self):
            return True

        def is_session_valid(self):
            return False

        def get_client(self):
            return object()

    class _SM:
        _sessions = {7: _Auth()}

    u7 = SimpleNamespace(id=7, email="s@s.s")
    monkeypatch.setattr(monitoring, "get_shared_session_manager", lambda: _SM())
    db = FakeSession(query_plan={monitoring.Users: [FakeQuery([u7])]})
    monitoring._get_active_sessions_impl(db)
    assert any("MONITORING_DEBUG" in r.getMessage() for r in caplog.records)


def test_get_active_sessions_impl_outer_exception_returns_empty(monkeypatch: pytest.MonkeyPatch):
    from server.app.routers import monitoring

    class _SM:
        _sessions = {1: object()}

    monkeypatch.setattr(monitoring, "get_shared_session_manager", lambda: _SM())

    class _BadEmailSession(FakeSession):
        def query(self, model):
            if model is monitoring.Users:
                raise RuntimeError("user query failed")
            return super().query(model)

    out = monitoring._get_active_sessions_impl(_BadEmailSession())
    assert out.sessions == []
