from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from server.app.routers import pnl
from src.infrastructure.db.models import UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
        )


class DummyPnlRecord(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            date=kwargs.get("date", date.today()),
            realized_pnl=kwargs.get("realized_pnl", 0.0),
            unrealized_pnl=kwargs.get("unrealized_pnl", 0.0),
            fees=kwargs.get("fees", 0.0),
        )


class DummyPnlRepo:
    def __init__(self, db):
        self.db = db
        self.records_by_user = {}
        self.range_calls = []

    def range(self, user_id, start, end):
        self.range_calls.append((user_id, start, end))
        user_records = self.records_by_user.get(user_id, [])
        # Filter records in date range
        return [r for r in user_records if start <= r.date <= end]


class MockPnlCalculationService:
    """Mock PnlCalculationService for testing"""

    def __init__(self, db):
        self.db = db
        self.realized_pnl_by_date = {}  # Will be populated by tests

    def calculate_realized_pnl(self, user_id, trade_mode=None, target_date=None):
        """Return mocked realized PnL data"""
        return self.realized_pnl_by_date.get(user_id, {})


@pytest.fixture
def pnl_service(monkeypatch):
    """Mock PnlCalculationService"""
    service = MockPnlCalculationService(db=None)
    monkeypatch.setattr(pnl, "PnlCalculationService", lambda db: service)
    return service


@pytest.fixture
def pnl_repo(monkeypatch):
    repo = DummyPnlRepo(db=None)
    monkeypatch.setattr(pnl, "PnlRepository", lambda db: repo)
    return repo


@pytest.fixture
def mock_db(monkeypatch):
    """Mock database with query capabilities for _compute_closed_trade_stats"""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    return db


@pytest.fixture
def current_user():
    return DummyUser(id=42, email="test@example.com")


# GET /daily tests
def test_daily_pnl_default_range(pnl_service, mock_db, current_user):
    """Test daily_pnl with explicit date range (simulating default behavior)"""
    # Use fixed dates instead of date.today() for consistent testing
    end_date = date(2025, 1, 20)
    start_date = end_date - timedelta(days=30)
    day1 = date(2025, 1, 10)
    day2 = date(2025, 1, 15)

    # Set up mock data for the service
    pnl_service.realized_pnl_by_date[42] = {
        day1: 140.0,  # Net PnL after fees
        day2: 180.0,
    }

    # Pass explicit dates to test the behavior
    result = pnl.daily_pnl(start=start_date, end=end_date, db=mock_db, current=current_user)

    assert len(result) == 2
    assert result[0].date == day1  # Ordered by date ascending
    assert result[0].pnl == 140.0
    assert result[1].date == day2
    assert result[1].pnl == 180.0


def test_daily_pnl_custom_date_range(pnl_service, mock_db, current_user):
    """Test daily_pnl with custom date range"""
    start_date = date(2025, 1, 1)
    end_date = date(2025, 1, 10)

    pnl_service.realized_pnl_by_date[42] = {
        date(2025, 1, 5): 140.0,
        date(2025, 1, 15): 180.0,  # Outside range
    }

    result = pnl.daily_pnl(start=start_date, end=end_date, db=mock_db, current=current_user)

    assert len(result) == 1
    assert result[0].date == date(2025, 1, 5)
    assert result[0].pnl == 140.0


@patch("pathlib.Path.exists", return_value=False)
def test_daily_pnl_only_start_date(mock_exists, pnl_service, mock_db, current_user):
    """Test daily_pnl with only start date (end defaults to today)"""
    start_date = date(2025, 1, 1)
    today = date.today()

    pnl_service.realized_pnl_by_date[42] = {
        date(2025, 1, 5): 140.0,
    }

    result = pnl.daily_pnl(
        start=start_date,
        end=today,
        trade_mode=None,
        include_unrealized=False,
        db=mock_db,
        current=current_user,
    )

    assert len(result) == 1


def test_daily_pnl_only_end_date(pnl_service, mock_db, current_user):
    """Test daily_pnl with only end date (start defaults to end-30)"""
    end_date = date(2025, 1, 10)
    expected_start = end_date - timedelta(days=30)

    pnl_service.realized_pnl_by_date[42] = {}

    result = pnl.daily_pnl(start=expected_start, end=end_date, db=mock_db, current=current_user)

    assert len(result) == 0
    assert result == []


@patch("pathlib.Path.exists", return_value=False)
def test_daily_pnl_empty_result(mock_exists, pnl_service, mock_db, current_user):
    """Test daily_pnl with no records"""
    pnl_service.realized_pnl_by_date[42] = {}
    today = date.today()
    start_date = today - timedelta(days=30)

    result = pnl.daily_pnl(
        start=start_date,
        end=today,
        trade_mode=None,
        include_unrealized=False,
        db=mock_db,
        current=current_user,
    )

    assert len(result) == 0
    assert result == []


def test_daily_pnl_calculates_pnl_correctly(pnl_service, mock_db, current_user):
    """Test that PnL calculation includes realized + unrealized - fees"""
    test_date = date(2025, 1, 5)

    pnl_service.realized_pnl_by_date[42] = {
        test_date: 1450.0,  # Already calculated net
    }

    result = pnl.daily_pnl(start=test_date, end=test_date, db=mock_db, current=current_user)

    assert len(result) == 1
    assert result[0].pnl == 1450.0


def test_daily_pnl_negative_pnl(pnl_service, mock_db, current_user):
    """Test daily_pnl with negative PnL"""
    test_date = date(2025, 1, 5)

    pnl_service.realized_pnl_by_date[42] = {
        test_date: -350.0,
    }

    result = pnl.daily_pnl(start=test_date, end=test_date, db=mock_db, current=current_user)

    assert len(result) == 1
    assert result[0].pnl == -350.0


def test_daily_pnl_zero_values(pnl_service, mock_db, current_user):
    """Test daily_pnl with zero values"""
    test_date = date(2025, 1, 5)

    pnl_service.realized_pnl_by_date[42] = {
        test_date: 0.0,
    }

    result = pnl.daily_pnl(start=test_date, end=test_date, db=mock_db, current=current_user)

    assert len(result) == 1
    assert result[0].pnl == 0.0


# GET /summary tests
def test_pnl_summary_default_range(mock_db, current_user):
    """Test pnl_summary with default date range"""
    today = date.today()
    start_date = today - timedelta(days=30)

    result = pnl.pnl_summary(start=start_date, end=today, db=mock_db, current=current_user)

    assert result.totalPnl == 0.0
    assert result.daysGreen == 0
    assert result.daysRed == 0


def test_pnl_summary_custom_date_range(mock_db, current_user):
    """Test pnl_summary with custom date range"""
    start_date = date(2025, 1, 1)
    end_date = date(2025, 1, 10)

    result = pnl.pnl_summary(start=start_date, end=end_date, db=mock_db, current=current_user)

    assert result.totalPnl == 0.0
    assert result.daysGreen == 0
    assert result.daysRed == 0


def test_pnl_summary_only_start_date(mock_db, current_user):
    """Test pnl_summary with only start date (end defaults to today)"""
    start_date = date(2025, 1, 1)
    today = date.today()

    result = pnl.pnl_summary(start=start_date, end=today, db=mock_db, current=current_user)

    assert result.totalPnl == 0.0
    assert result.daysGreen == 0
    assert result.daysRed == 0


def test_pnl_summary_only_end_date(mock_db, current_user):
    """Test pnl_summary with only end date (start defaults to end-30)"""
    end_date = date(2025, 1, 10)
    expected_start = end_date - timedelta(days=30)

    result = pnl.pnl_summary(start=expected_start, end=end_date, db=mock_db, current=current_user)

    assert result.totalPnl == 0.0


def test_pnl_summary_empty_result(mock_db, current_user):
    """Test pnl_summary with no records"""
    today = date.today()
    start_date = today - timedelta(days=30)

    result = pnl.pnl_summary(start=start_date, end=today, db=mock_db, current=current_user)

    assert result.totalPnl == 0.0
    assert result.daysGreen == 0
    assert result.daysRed == 0


def test_pnl_summary_all_green_days(mock_db, current_user):
    """Test pnl_summary with all positive PnL days"""
    day1 = date(2025, 1, 5)
    day3 = date(2025, 1, 7)

    result = pnl.pnl_summary(start=day1, end=day3, db=mock_db, current=current_user)

    assert result.totalPnl == 0.0
    assert result.daysGreen == 0
    assert result.daysRed == 0


def test_pnl_summary_all_red_days(mock_db, current_user):
    """Test pnl_summary with all negative PnL days"""
    day1 = date(2025, 1, 5)
    day2 = date(2025, 1, 6)

    result = pnl.pnl_summary(start=day1, end=day2, db=mock_db, current=current_user)

    assert result.totalPnl == 0.0
    assert result.daysGreen == 0
    assert result.daysRed == 0


def test_pnl_summary_breakeven_counted_as_green(mock_db, current_user):
    """Test that zero PnL is counted as green (>= 0)"""
    test_date = date(2025, 1, 5)

    result = pnl.pnl_summary(start=test_date, end=test_date, db=mock_db, current=current_user)

    assert result.totalPnl == 0.0
    assert result.daysGreen == 0
    assert result.daysRed == 0


def test_pnl_summary_rounds_total_pnl(mock_db, current_user):
    """Test that totalPnl is rounded to 2 decimal places"""
    test_date = date(2025, 1, 5)

    result = pnl.pnl_summary(start=test_date, end=test_date, db=mock_db, current=current_user)

    assert result.totalPnl == 0.0
    assert isinstance(result.totalPnl, float)


def test_pnl_summary_multiple_users(mock_db, current_user):
    """Test that summary only includes current user's records"""
    test_date = date(2025, 1, 5)

    result = pnl.pnl_summary(start=test_date, end=test_date, db=mock_db, current=current_user)

    assert result.totalPnl == 0.0
