from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from server.app.routers import service as service_router


class FakeSession(SimpleNamespace):
    def __init__(self):
        super().__init__(committed=False, rolled_back=False)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeTradingService:
    def __init__(self, *, start=True, stop=True, status=None, metrics=None):
        self.start = start
        self.stop = stop
        self.status = status
        self.metrics = metrics
        self.started = []
        self.stopped = []

    def start_service(self, user_id):
        self.started.append(user_id)
        if isinstance(self.start, Exception):
            raise self.start
        return self.start

    def stop_service(self, user_id):
        self.stopped.append(user_id)
        if isinstance(self.stop, Exception):
            raise self.stop
        return self.stop

    def get_service_status(self, user_id):
        return self.status

    def get_position_creation_metrics(self, user_id):
        return self.metrics


@pytest.fixture
def current_user():
    return SimpleNamespace(id=99)


def test_start_service_commits_on_success(current_user):
    db = FakeSession()
    trading_service = FakeTradingService(start=True)

    response = service_router.start_service(
        db=db, current=current_user, trading_service=trading_service
    )

    assert response.success
    assert response.service_running
    assert db.committed
    assert trading_service.started == [current_user.id]


def test_start_service_rolls_back_on_value_error(current_user):
    db = FakeSession()
    trading_service = FakeTradingService(start=ValueError("cannot start"))

    with pytest.raises(HTTPException) as excinfo:
        service_router.start_service(db=db, current=current_user, trading_service=trading_service)

    assert excinfo.value.status_code == 400
    assert db.rolled_back
    assert trading_service.started == [current_user.id]


def test_stop_service_returns_failure_and_commits(current_user):
    db = FakeSession()
    trading_service = FakeTradingService(stop=False)

    response = service_router.stop_service(
        db=db, current=current_user, trading_service=trading_service
    )

    assert response.success is False
    assert response.service_running is True
    assert db.committed
    assert trading_service.stopped == [current_user.id]


def test_stop_service_rolls_back_on_exception(current_user):
    db = FakeSession()
    trading_service = FakeTradingService(stop=RuntimeError("boom"))

    with pytest.raises(HTTPException) as excinfo:
        service_router.stop_service(db=db, current=current_user, trading_service=trading_service)

    assert excinfo.value.status_code == 500
    assert db.rolled_back
    assert trading_service.stopped == [current_user.id]


def test_get_service_status_falls_back_to_repo(monkeypatch, current_user):
    status_obj = SimpleNamespace(
        service_running=False,
        last_heartbeat=datetime(2026, 1, 1, 12, 0),
        last_task_execution=datetime(2026, 1, 1, 13, 0),
        error_count=3,
        last_error="oops",
        updated_at=datetime(2026, 1, 2, 0, 0),
    )

    class FakeRepo:
        def __init__(self, db):
            self.db = db

        def get_or_create(self, user_id):
            assert user_id == current_user.id
            return status_obj

    monkeypatch.setattr(service_router, "ServiceStatusRepository", lambda db: FakeRepo(db))

    trading_service = FakeTradingService(status=None)

    response = service_router.get_service_status(
        db=SimpleNamespace(), current=current_user, trading_service=trading_service
    )

    assert response.service_running is False
    assert response.last_heartbeat == status_obj.last_heartbeat
    assert response.last_error == "oops"


def test_get_service_logs_tail(monkeypatch, current_user):
    class FakeReader:
        def tail_logs(self, *, user_id, log_type, tail_lines):
            assert user_id == current_user.id
            assert log_type == "service"
            assert tail_lines == 200
            return [
                {
                    "id": "service:1",
                    "level": "INFO",
                    "module": "service",
                    "message": "running",
                    "timestamp": datetime(2026, 1, 1, 0, 0),
                }
            ]

        def read_logs(self, **kwargs):
            raise AssertionError("should not read when tail=True")

    monkeypatch.setattr(service_router, "FileLogReader", lambda: FakeReader())

    response = service_router.get_service_logs(
        level=None,
        module=None,
        hours=1,
        limit=10,
        tail=True,
        db=SimpleNamespace(),
        current=current_user,
    )

    assert response.total == 1
    assert response.logs[0].module == "service"


def test_get_service_logs_range(monkeypatch, current_user):
    class FakeReader:
        def tail_logs(self, **kwargs):
            raise AssertionError("tail should be False")

        def read_logs(self, **kwargs):
            assert kwargs["level"] == "ERROR"
            assert kwargs["module"] == "engine"
            return [
                {
                    "id": 2,
                    "level": "ERROR",
                    "module": "engine",
                    "message": "failed",
                    "timestamp": datetime(2026, 1, 2, 0, 0),
                }
            ]

    monkeypatch.setattr(service_router, "FileLogReader", lambda: FakeReader())

    response = service_router.get_service_logs(
        level="ERROR",
        module="engine",
        hours=12,
        limit=5,
        tail=False,
        db=SimpleNamespace(),
        current=current_user,
    )

    assert response.total == 1
    assert response.logs[0].level == "ERROR"


def test_position_creation_metrics_handles_none(current_user):
    trading_service = FakeTradingService(metrics=None)

    response = service_router.get_position_creation_metrics(
        db=SimpleNamespace(), current=current_user, trading_service=trading_service
    )

    assert response.total_attempts == 0
    assert response.success_rate == 0.0
    assert response.success == 0


def test_position_creation_metrics_calculates_rate(current_user):
    trading_service = FakeTradingService(
        metrics={
            "success": 2,
            "failed_missing_repos": 1,
            "failed_missing_symbol": 1,
            "failed_exception": 1,
        }
    )

    response = service_router.get_position_creation_metrics(
        db=SimpleNamespace(), current=current_user, trading_service=trading_service
    )

    assert response.total_attempts == 5
    assert response.success == 2
    assert response.success_rate == 40.0
