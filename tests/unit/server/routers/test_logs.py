from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status

from server.app.routers import logs
from server.app.schemas.logs import ErrorResolutionRequest
from src.infrastructure.db.models import UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
        )


class DummyServiceLog(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            user_id=kwargs.get("user_id", 1),
            level=kwargs.get("level", "INFO"),
            module=kwargs.get("module", "test_module"),
            message=kwargs.get("message", "Test message"),
            context=kwargs.get("context", None),
            timestamp=kwargs.get("timestamp", datetime.now()),
        )


class DummyErrorLog(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            user_id=kwargs.get("user_id", 1),
            error_type=kwargs.get("error_type", "ValueError"),
            error_message=kwargs.get("error_message", "Test error"),
            traceback=kwargs.get("traceback", None),
            context=kwargs.get("context", None),
            resolved=kwargs.get("resolved", False),
            resolved_at=kwargs.get("resolved_at", None),
            resolved_by=kwargs.get("resolved_by", None),
            resolution_notes=kwargs.get("resolution_notes", None),
            occurred_at=kwargs.get("occurred_at", datetime.now()),
        )


class DummyServiceLogRepo:
    def __init__(self, db):
        self.db = db
        self.list_called = []
        self.list_all_called = []

    def list(  # noqa: PLR0913
        self,
        user_id,
        level=None,
        module=None,
        start_time=None,
        end_time=None,
        search=None,
        limit=200,
    ):
        self.list_called.append(
            {
                "user_id": user_id,
                "level": level,
                "module": module,
                "start_time": start_time,
                "end_time": end_time,
                "search": search,
                "limit": limit,
            }
        )
        return [
            DummyServiceLog(
                id=1,
                user_id=user_id,
                level=level or "INFO",
                module=module or "test_module",
                message="Test log message",
            )
        ]

    def list_all(  # noqa: PLR0913
        self,
        user_id=None,
        level=None,
        module=None,
        start_time=None,
        end_time=None,
        search=None,
        limit=500,
    ):
        self.list_all_called.append(
            {
                "user_id": user_id,
                "level": level,
                "module": module,
                "start_time": start_time,
                "end_time": end_time,
                "search": search,
                "limit": limit,
            }
        )
        return [
            DummyServiceLog(
                id=1,
                user_id=user_id or 1,
                level=level or "INFO",
                module=module or "test_module",
                message="Test log message",
            )
        ]


class DummyErrorLogRepo:
    def __init__(self, db):
        self.db = db
        self.list_called = []
        self.list_all_called = []
        self.resolve_called = []
        self.errors_by_id = {}

    def list(  # noqa: PLR0913
        self,
        user_id,
        resolved=None,
        error_type=None,
        start_time=None,
        end_time=None,
        search=None,
        limit=100,
    ):
        self.list_called.append(
            {
                "user_id": user_id,
                "resolved": resolved,
                "error_type": error_type,
                "start_time": start_time,
                "end_time": end_time,
                "search": search,
                "limit": limit,
            }
        )
        return [
            DummyErrorLog(
                id=1,
                user_id=user_id,
                resolved=resolved if resolved is not None else False,
                error_type=error_type or "ValueError",
                error_message="Test error message",
            )
        ]

    def list_all(  # noqa: PLR0913
        self,
        user_id=None,
        resolved=None,
        error_type=None,
        start_time=None,
        end_time=None,
        search=None,
        limit=200,
    ):
        self.list_all_called.append(
            {
                "user_id": user_id,
                "resolved": resolved,
                "error_type": error_type,
                "start_time": start_time,
                "end_time": end_time,
                "search": search,
                "limit": limit,
            }
        )
        return [
            DummyErrorLog(
                id=1,
                user_id=user_id or 1,
                resolved=resolved if resolved is not None else False,
                error_type=error_type or "ValueError",
                error_message="Test error message",
            )
        ]

    def resolve(self, error_id, resolved_by, resolution_notes=None):
        self.resolve_called.append((error_id, resolved_by, resolution_notes))
        error = self.errors_by_id.get(error_id)
        if not error:
            raise ValueError(f"Error log {error_id} not found")
        error.resolved = True
        error.resolved_at = datetime.now()
        error.resolved_by = resolved_by
        error.resolution_notes = resolution_notes
        return error


@pytest.fixture
def service_log_repo(monkeypatch):
    repo = DummyServiceLogRepo(db=None)
    monkeypatch.setattr(logs, "ServiceLogRepository", lambda db: repo)
    return repo


@pytest.fixture
def error_log_repo(monkeypatch):
    repo = DummyErrorLogRepo(db=None)
    monkeypatch.setattr(logs, "ErrorLogRepository", lambda db: repo)
    return repo


@pytest.fixture
def current_user():
    return DummyUser(id=42, email="test@example.com")


@pytest.fixture
def admin_user():
    return DummyUser(id=99, email="admin@example.com", role=UserRole.ADMIN)


# _parse_datetime helper function tests
def test_parse_datetime_none():
    """Test _parse_datetime with None"""
    result = logs._parse_datetime(None)
    assert result is None


def test_parse_datetime_date_only():
    """Test _parse_datetime with date-only string"""
    result = logs._parse_datetime("2024-01-15")
    assert result is not None
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15
    assert result.hour == 0
    assert result.minute == 0
    assert result.second == 0


def test_parse_datetime_full_iso():
    """Test _parse_datetime with full ISO string"""
    result = logs._parse_datetime("2024-01-15T14:30:00")
    assert result is not None
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15
    assert result.hour == 14
    assert result.minute == 30


def test_parse_datetime_with_timezone():
    """Test _parse_datetime with timezone"""
    result = logs._parse_datetime("2024-01-15T14:30:00+05:30")
    assert result is not None
    assert result.hour == 14


def test_parse_datetime_with_z_suffix():
    """Test _parse_datetime with Z suffix (UTC)"""
    result = logs._parse_datetime("2024-01-15T14:30:00Z")
    assert result is not None
    assert result.hour == 14


def test_parse_datetime_invalid_format():
    """Test _parse_datetime with invalid format"""
    with pytest.raises(HTTPException) as exc:
        logs._parse_datetime("invalid-date")
    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid datetime format" in exc.value.detail


# GET /user/logs tests
def test_get_user_logs_basic(service_log_repo, current_user):
    """Test get_user_logs with no filters"""
    result = logs.get_user_logs(
        level=None,
        module=None,
        start_time=None,
        end_time=None,
        search=None,
        limit=200,
        current_user=current_user,
        db=None,
    )

    assert len(result.logs) == 1
    assert result.logs[0].user_id == 42
    assert len(service_log_repo.list_called) == 1
    assert service_log_repo.list_called[0]["user_id"] == 42
    assert service_log_repo.list_called[0]["limit"] == 200


def test_get_user_logs_with_filters(service_log_repo, current_user):
    """Test get_user_logs with all filters"""
    result = logs.get_user_logs(
        level="ERROR",
        module="trading_service",
        start_time="2024-01-01",
        end_time="2024-01-31",
        search="failed",
        limit=500,
        current_user=current_user,
        db=None,
    )

    assert len(result.logs) == 1
    call_args = service_log_repo.list_called[0]
    assert call_args["level"] == "ERROR"
    assert call_args["module"] == "trading_service"
    assert call_args["search"] == "failed"
    assert call_args["limit"] == 500
    assert call_args["start_time"] is not None
    assert call_args["end_time"] is not None


def test_get_user_logs_parses_datetime(service_log_repo, current_user):
    """Test get_user_logs correctly parses datetime strings"""
    logs.get_user_logs(
        level=None,
        module=None,
        start_time="2024-01-15T10:30:00",
        end_time="2024-01-16",
        search=None,
        limit=200,
        current_user=current_user,
        db=None,
    )

    call_args = service_log_repo.list_called[0]
    assert call_args["start_time"] is not None
    assert isinstance(call_args["start_time"], datetime)
    assert call_args["end_time"] is not None
    assert isinstance(call_args["end_time"], datetime)
    assert call_args["end_time"].hour == 0  # Date-only becomes midnight


# GET /user/logs/errors tests
def test_get_user_error_logs_basic(error_log_repo, current_user):
    """Test get_user_error_logs with no filters"""
    result = logs.get_user_error_logs(
        resolved=None,
        error_type=None,
        start_time=None,
        end_time=None,
        search=None,
        limit=100,
        current_user=current_user,
        db=None,
    )

    assert len(result.errors) == 1
    assert result.errors[0].user_id == 42
    assert len(error_log_repo.list_called) == 1
    assert error_log_repo.list_called[0]["user_id"] == 42


def test_get_user_error_logs_with_filters(error_log_repo, current_user):
    """Test get_user_error_logs with all filters"""
    result = logs.get_user_error_logs(
        resolved=False,
        error_type="ValueError",
        start_time="2024-01-01",
        end_time="2024-01-31T23:59:59",
        search="connection",
        limit=50,
        current_user=current_user,
        db=None,
    )

    assert len(result.errors) == 1
    call_args = error_log_repo.list_called[0]
    assert call_args["resolved"] is False
    assert call_args["error_type"] == "ValueError"
    assert call_args["search"] == "connection"
    assert call_args["limit"] == 50
    assert call_args["start_time"] is not None
    assert call_args["end_time"] is not None


def test_get_user_error_logs_resolved_filter(error_log_repo, current_user):
    """Test get_user_error_logs with resolved filter"""
    logs.get_user_error_logs(
        resolved=True,
        error_type=None,
        start_time=None,
        end_time=None,
        search=None,
        limit=100,
        current_user=current_user,
        db=None,
    )

    call_args = error_log_repo.list_called[0]
    assert call_args["resolved"] is True


# GET /admin/logs tests
def test_get_admin_logs_basic(service_log_repo, admin_user):
    """Test get_admin_logs with no filters"""
    result = logs.get_admin_logs(
        user_id=None,
        level=None,
        module=None,
        start_time=None,
        end_time=None,
        search=None,
        limit=500,
        admin=admin_user,
        db=None,
    )

    assert len(result.logs) == 1
    assert len(service_log_repo.list_all_called) == 1
    call_args = service_log_repo.list_all_called[0]
    assert call_args["user_id"] is None


def test_get_admin_logs_with_user_id(service_log_repo, admin_user):
    """Test get_admin_logs with user_id filter"""
    result = logs.get_admin_logs(
        user_id=42,
        level=None,
        module=None,
        start_time=None,
        end_time=None,
        search=None,
        limit=500,
        admin=admin_user,
        db=None,
    )

    assert len(result.logs) == 1
    call_args = service_log_repo.list_all_called[0]
    assert call_args["user_id"] == 42


def test_get_admin_logs_with_filters(service_log_repo, admin_user):
    """Test get_admin_logs with all filters"""
    logs.get_admin_logs(
        user_id=42,
        level="ERROR",
        module="broker",
        start_time="2024-01-01",
        end_time="2024-01-31",
        search="timeout",
        limit=1000,
        admin=admin_user,
        db=None,
    )

    call_args = service_log_repo.list_all_called[0]
    assert call_args["user_id"] == 42
    assert call_args["level"] == "ERROR"
    assert call_args["module"] == "broker"
    assert call_args["limit"] == 1000


# GET /admin/logs/errors tests
def test_get_admin_error_logs_basic(error_log_repo, admin_user):
    """Test get_admin_error_logs with no filters"""
    result = logs.get_admin_error_logs(
        user_id=None,
        resolved=None,
        error_type=None,
        start_time=None,
        end_time=None,
        search=None,
        limit=200,
        admin=admin_user,
        db=None,
    )

    assert len(result.errors) == 1
    assert len(error_log_repo.list_all_called) == 1
    call_args = error_log_repo.list_all_called[0]
    assert call_args["user_id"] is None


def test_get_admin_error_logs_with_filters(error_log_repo, admin_user):
    """Test get_admin_error_logs with all filters"""
    logs.get_admin_error_logs(
        user_id=42,
        resolved=False,
        error_type="ConnectionError",
        start_time="2024-01-01",
        end_time="2024-01-31",
        search="timeout",
        limit=500,
        admin=admin_user,
        db=None,
    )

    call_args = error_log_repo.list_all_called[0]
    assert call_args["user_id"] == 42
    assert call_args["resolved"] is False
    assert call_args["error_type"] == "ConnectionError"
    assert call_args["search"] == "timeout"
    assert call_args["limit"] == 500


# POST /admin/logs/errors/{error_id}/resolve tests
def test_resolve_error_log_success(error_log_repo, admin_user):
    """Test resolve_error_log successfully"""
    error = DummyErrorLog(id=123, user_id=42, resolved=False)
    error_log_repo.errors_by_id[123] = error

    payload = ErrorResolutionRequest(notes="Fixed in version 2.0")

    result = logs.resolve_error_log(
        error_id=123,
        payload=payload,
        admin=admin_user,
        db=None,
    )

    assert result.message == "Error marked as resolved"
    assert result.error.id == 123
    assert result.error.resolved is True
    assert error.resolved is True
    assert error.resolved_by == admin_user.id
    assert error.resolution_notes == "Fixed in version 2.0"
    assert len(error_log_repo.resolve_called) == 1


def test_resolve_error_log_without_notes(error_log_repo, admin_user):
    """Test resolve_error_log without resolution notes"""
    error = DummyErrorLog(id=456, user_id=42, resolved=False)
    error_log_repo.errors_by_id[456] = error

    payload = ErrorResolutionRequest(notes=None)

    result = logs.resolve_error_log(
        error_id=456,
        payload=payload,
        admin=admin_user,
        db=None,
    )

    assert result.error.resolved is True
    assert error.resolved_by == admin_user.id
    assert error.resolution_notes is None


def test_resolve_error_log_not_found(error_log_repo, admin_user):
    """Test resolve_error_log with non-existent error_id"""
    payload = ErrorResolutionRequest(notes="Test notes")

    with pytest.raises(HTTPException) as exc:
        logs.resolve_error_log(
            error_id=999,
            payload=payload,
            admin=admin_user,
            db=None,
        )

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert "Error log not found" in exc.value.detail
    assert len(error_log_repo.resolve_called) == 1


# Edge cases
def test_get_user_logs_empty_result(service_log_repo, current_user):
    """Test get_user_logs with empty result"""
    original_list = service_log_repo.list
    service_log_repo.list = lambda user_id, level=None, module=None, start_time=None, end_time=None, search=None, limit=200: []  # noqa: E501
    result = logs.get_user_logs(
        level=None,
        module=None,
        start_time=None,
        end_time=None,
        search=None,
        limit=200,
        current_user=current_user,
        db=None,
    )
    service_log_repo.list = original_list
    assert len(result.logs) == 0


def test_get_user_error_logs_empty_result(error_log_repo, current_user):
    """Test get_user_error_logs with empty result"""
    original_list = error_log_repo.list
    error_log_repo.list = lambda user_id, resolved=None, error_type=None, start_time=None, end_time=None, search=None, limit=100: []  # noqa: E501
    result = logs.get_user_error_logs(
        resolved=None,
        error_type=None,
        start_time=None,
        end_time=None,
        search=None,
        limit=100,
        current_user=current_user,
        db=None,
    )
    error_log_repo.list = original_list
    assert len(result.errors) == 0


def test_get_user_logs_invalid_start_time(service_log_repo, current_user):
    """Test get_user_logs with invalid start_time format"""
    with pytest.raises(HTTPException) as exc:
        logs.get_user_logs(
            level=None,
            module=None,
            start_time="invalid-date",
            end_time=None,
            search=None,
            limit=200,
            current_user=current_user,
            db=None,
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid datetime format" in exc.value.detail


def test_get_user_logs_invalid_end_time(service_log_repo, current_user):
    """Test get_user_logs with invalid end_time format"""
    with pytest.raises(HTTPException) as exc:
        logs.get_user_logs(
            level=None,
            module=None,
            start_time=None,
            end_time="not-a-date",
            search=None,
            limit=200,
            current_user=current_user,
            db=None,
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


def test_get_admin_logs_invalid_datetime(service_log_repo, admin_user):
    """Test get_admin_logs with invalid datetime"""
    with pytest.raises(HTTPException) as exc:
        logs.get_admin_logs(
            user_id=None,
            level=None,
            module=None,
            start_time="bad-format",
            end_time=None,
            search=None,
            limit=500,
            admin=admin_user,
            db=None,
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


def test_get_admin_error_logs_invalid_datetime(error_log_repo, admin_user):
    """Test get_admin_error_logs with invalid datetime"""
    with pytest.raises(HTTPException) as exc:
        logs.get_admin_error_logs(
            user_id=None,
            resolved=None,
            error_type=None,
            start_time=None,
            end_time="invalid",
            search=None,
            limit=200,
            admin=admin_user,
            db=None,
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


def test_get_user_logs_custom_limit(service_log_repo, current_user):
    """Test get_user_logs with custom limit"""
    logs.get_user_logs(
        level=None,
        module=None,
        start_time=None,
        end_time=None,
        search=None,
        limit=50,
        current_user=current_user,
        db=None,
    )
    assert service_log_repo.list_called[0]["limit"] == 50


def test_get_user_error_logs_custom_limit(error_log_repo, current_user):
    """Test get_user_error_logs with custom limit"""
    logs.get_user_error_logs(
        resolved=None,
        error_type=None,
        start_time=None,
        end_time=None,
        search=None,
        limit=25,
        current_user=current_user,
        db=None,
    )
    assert error_log_repo.list_called[0]["limit"] == 25
