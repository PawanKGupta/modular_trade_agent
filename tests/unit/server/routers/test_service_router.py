from datetime import UTC, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

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


def test_get_service_status_converts_non_utc_timestamps(current_user):
    """Non-UTC aware datetimes are converted to UTC for API serialization."""
    status_obj = SimpleNamespace(
        service_running=True,
        last_heartbeat=datetime(2026, 1, 1, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        last_task_execution=datetime(2026, 1, 1, 13, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        error_count=0,
        last_error=None,
        updated_at=datetime(2026, 1, 2, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
    )
    trading_service = FakeTradingService(status=status_obj)

    response = service_router.get_service_status(
        db=SimpleNamespace(), current=current_user, trading_service=trading_service
    )

    assert response.last_heartbeat.tzinfo == UTC
    assert response.last_task_execution.tzinfo == UTC
    assert response.updated_at.tzinfo == UTC


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
    assert response.last_heartbeat is not None
    assert response.last_heartbeat.tzinfo == UTC
    assert response.last_error == "oops"


def test_get_individual_services_status_parses_and_normalizes_datetimes(current_user):
    class FakeMgr:
        def get_status(self, user_id):
            assert user_id == current_user.id
            return {
                "premarket_retry": {
                    "is_running": True,
                    "started_at": "2026-06-01T08:00:00Z",
                    "last_execution_at": datetime(
                        2026, 6, 1, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata")
                    ),
                    "next_execution_at": "2026-06-01T10:00:00",
                    "process_id": 42,
                    "schedule_enabled": False,
                    "last_execution_status": "success",
                    "last_execution_duration": 1.25,
                    "last_execution_details": {"step": "done"},
                }
            }

    response = service_router.get_individual_services_status(
        db=SimpleNamespace(),
        current=current_user,
        service_manager=FakeMgr(),
    )

    svc = response.services["premarket_retry"]
    assert svc.started_at.tzinfo == UTC
    assert svc.last_execution_at.tzinfo == UTC
    assert svc.next_execution_at.tzinfo == UTC


def test_get_individual_services_status_invalid_iso_yields_none_timestamp(current_user):
    class FakeMgr:
        def get_status(self, user_id):
            return {
                "bad_ts": {
                    "is_running": False,
                    "started_at": "not-a-valid-date",
                    "last_execution_at": None,
                    "next_execution_at": None,
                    "process_id": None,
                    "schedule_enabled": True,
                }
            }

    response = service_router.get_individual_services_status(
        db=SimpleNamespace(),
        current=current_user,
        service_manager=FakeMgr(),
    )

    assert response.services["bad_ts"].started_at is None


def test_get_individual_services_status_propagates_errors(current_user):
    class BoomMgr:
        def get_status(self, user_id):
            raise RuntimeError("status store down")

    with pytest.raises(HTTPException) as excinfo:
        service_router.get_individual_services_status(
            db=SimpleNamespace(),
            current=current_user,
            service_manager=BoomMgr(),
        )

    assert excinfo.value.status_code == 500


def test_get_task_history_repository_error(current_user, monkeypatch):
    class BoomRepo:
        def __init__(self, db):
            self.db = db

        def list(self, **kwargs):
            raise RuntimeError("db error")

    monkeypatch.setattr(service_router, "ServiceTaskRepository", BoomRepo)

    with pytest.raises(HTTPException) as excinfo:
        service_router.get_task_history(
            task_name=None,
            status=None,
            limit=10,
            db=FakeSession(),
            current=current_user,
        )

    assert excinfo.value.status_code == 500


def test_get_position_creation_metrics_error(current_user):
    class ExplodingTrading(FakeTradingService):
        def get_position_creation_metrics(self, user_id):
            raise RuntimeError("metrics unavailable")

    with pytest.raises(HTTPException) as excinfo:
        service_router.get_position_creation_metrics(
            db=SimpleNamespace(),
            current=current_user,
            trading_service=ExplodingTrading(),
        )

    assert excinfo.value.status_code == 500


def test_get_positions_without_sell_orders_error(current_user):
    class ExplodingTrading(FakeTradingService):
        def get_positions_without_sell_orders(self, user_id):
            raise RuntimeError("broker down")

    with pytest.raises(HTTPException) as excinfo:
        service_router.get_positions_without_sell_orders(
            db=SimpleNamespace(),
            current=current_user,
            trading_service=ExplodingTrading(),
        )

    assert excinfo.value.status_code == 500


def test_get_service_logs_reader_error(current_user, monkeypatch):
    class BoomReader:
        def read_logs(self, **kwargs):
            raise RuntimeError("disk full")

        def tail_logs(self, **kwargs):
            raise RuntimeError("disk full")

    monkeypatch.setattr(service_router, "FileLogReader", lambda: BoomReader())

    with pytest.raises(HTTPException) as excinfo:
        service_router.get_service_logs(
            level=None,
            module=None,
            hours=1,
            limit=10,
            tail=False,
            db=SimpleNamespace(),
            current=current_user,
        )

    assert excinfo.value.status_code == 500


def test_get_trading_day_info_weekday_holiday(monkeypatch, current_user):
    fixed_now = datetime(2026, 1, 26, 10, 0, 0)
    monkeypatch.setattr(service_router, "ist_now", lambda: fixed_now)
    monkeypatch.setattr(service_router, "is_nse_holiday", lambda day: day == fixed_now.date())
    monkeypatch.setattr(service_router, "get_holiday_name", lambda day: "Republic Day")
    monkeypatch.setattr(service_router, "is_trading_day", lambda day: False)

    response = service_router.get_trading_day_info(current=current_user)

    assert response.is_holiday is True
    assert response.holiday_name == "Republic Day"
    assert response.is_weekend is False
    assert response.is_trading_day is False


def test_get_trading_day_info_weekend(monkeypatch, current_user):
    saturday = datetime(2026, 1, 10, 12, 0, 0)
    monkeypatch.setattr(service_router, "ist_now", lambda: saturday)
    monkeypatch.setattr(service_router, "is_nse_holiday", lambda day: False)
    monkeypatch.setattr(service_router, "is_trading_day", lambda day: False)

    response = service_router.get_trading_day_info(current=current_user)

    assert response.is_weekend is True
    assert response.is_holiday is False


def test_get_trading_day_info_calendar_error(monkeypatch, current_user):
    monkeypatch.setattr(service_router, "ist_now", lambda: datetime(2026, 2, 2, 9, 0, 0))
    monkeypatch.setattr(
        service_router,
        "is_nse_holiday",
        lambda day: (_ for _ in ()).throw(RuntimeError("calendar")),
    )

    with pytest.raises(HTTPException) as excinfo:
        service_router.get_trading_day_info(current=current_user)

    assert excinfo.value.status_code == 500


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
