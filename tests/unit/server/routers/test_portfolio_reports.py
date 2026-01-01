"""Tests for portfolio and reports routers"""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from server.app.routers import portfolio as portfolio_module
from server.app.routers import reports as reports_module
from src.infrastructure.db.models import (
    PortfolioSnapshot,
    TradeMode,
    UserRole,
    Users,
    UserSettings,
)


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
            is_active=kwargs.get("is_active", True),
        )


@pytest.fixture
def mock_deps_portfolio(monkeypatch, db_session):
    """Mock dependencies for portfolio endpoints"""
    # Create a real user in the database
    user = Users(
        id=1,
        email="user@example.com",
        name="Test User",
        password_hash="$2b$12$dummy",
        role=UserRole.USER,
        is_active=True,
    )
    # Check if user already exists (from ensure_system_user)
    existing_user = db_session.query(Users).filter_by(id=1).first()
    if existing_user:
        # Update existing user
        existing_user.email = user.email
        existing_user.name = user.name
        existing_user.role = user.role
        existing_user.is_active = user.is_active
        user = existing_user
    else:
        db_session.add(user)
        db_session.commit()

    # Create default settings
    settings = UserSettings(
        user_id=1,
        trade_mode=TradeMode.PAPER,
    )
    db_session.add(settings)
    db_session.commit()

    current_user = DummyUser(id=1)

    def mock_get_current_user():
        return current_user

    def mock_get_db():
        return db_session

    monkeypatch.setattr("server.app.routers.portfolio.get_current_user", mock_get_current_user)
    monkeypatch.setattr("server.app.routers.portfolio.get_db", mock_get_db)
    monkeypatch.setattr("server.app.routers.reports.get_current_user", mock_get_current_user)
    monkeypatch.setattr("server.app.routers.reports.get_db", mock_get_db)

    return {"db": db_session, "user": current_user}


def test_portfolio_history_empty(mock_deps_portfolio):
    """Test portfolio history with no snapshots"""
    deps = mock_deps_portfolio
    result = portfolio_module.portfolio_history(
        start=None, end=None, limit=1000, db=deps["db"], current=deps["user"]
    )
    assert result == []


def test_portfolio_history_with_snapshots(mock_deps_portfolio):
    """Test portfolio history with snapshots"""
    deps = mock_deps_portfolio
    db = deps["db"]
    user_id = deps["user"].id

    today = date.today()

    # Create portfolio snapshots
    for i in range(3):
        snapshot = PortfolioSnapshot(
            user_id=user_id,
            date=today - timedelta(days=i),
            total_value=10000.0 + (i * 100),
            invested_value=5000.0 + (i * 50),
            available_cash=5000.0 + (i * 50),
            unrealized_pnl=100.0 * i,
            realized_pnl=200.0 * i,
            open_positions_count=2 + i,
            closed_positions_count=1 + i,
            total_return=0.5 + (0.1 * i),
            daily_return=0.01 * (i + 1),
            snapshot_type="daily",
        )
        db.add(snapshot)
    db.commit()

    result = portfolio_module.portfolio_history(
        start=None, end=None, limit=1000, db=db, current=deps["user"]
    )

    assert len(result) == 3
    # Should be ordered by date descending
    assert result[0]["date"] == today.isoformat()
    assert result[0]["total_value"] == 10000.0
    assert result[2]["date"] == (today - timedelta(days=2)).isoformat()


def test_portfolio_history_with_date_filters(mock_deps_portfolio):
    """Test portfolio history with date range filters"""
    deps = mock_deps_portfolio
    db = deps["db"]
    user_id = deps["user"].id

    today = date.today()

    # Create snapshots on different dates
    for i in range(5):
        snapshot = PortfolioSnapshot(
            user_id=user_id,
            date=today - timedelta(days=i),
            total_value=10000.0,
            invested_value=5000.0,
            available_cash=5000.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            open_positions_count=0,
            closed_positions_count=0,
            total_return=0.0,
            daily_return=0.0,
            snapshot_type="daily",
        )
        db.add(snapshot)
    db.commit()

    # Filter to last 2 days
    result = portfolio_module.portfolio_history(
        start=today - timedelta(days=1),
        end=today,
        limit=1000,
        db=db,
        current=deps["user"],
    )

    assert len(result) == 2


def test_portfolio_history_with_limit(mock_deps_portfolio):
    """Test portfolio history respects limit parameter"""
    deps = mock_deps_portfolio
    db = deps["db"]
    user_id = deps["user"].id

    today = date.today()

    # Create 10 snapshots
    for i in range(10):
        snapshot = PortfolioSnapshot(
            user_id=user_id,
            date=today - timedelta(days=i),
            total_value=10000.0,
            invested_value=5000.0,
            available_cash=5000.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            open_positions_count=0,
            closed_positions_count=0,
            total_return=0.0,
            daily_return=0.0,
            snapshot_type="daily",
        )
        db.add(snapshot)
    db.commit()

    # Get only first 3
    result = portfolio_module.portfolio_history(
        start=None, end=None, limit=3, db=db, current=deps["user"]
    )

    assert len(result) == 3


# Reports tests
def test_generate_pnl_pdf_daily(mock_deps_portfolio, monkeypatch):
    """Test daily PDF report generation"""
    deps = mock_deps_portfolio

    # Mock PdfGenerator to avoid actual PDF generation
    class MockPdfGenerator:
        def generate_pnl_report(self, **kwargs):
            return b"MOCK_PDF_CONTENT"

    def mock_pdf_init():
        return MockPdfGenerator()

    monkeypatch.setattr("server.app.routers.reports.PdfGenerator", mock_pdf_init)

    response = reports_module.generate_pnl_pdf(
        period="daily",
        start_date=None,
        end_date=None,
        include_unrealized=True,
        trade_mode=TradeMode.PAPER,
        db=deps["db"],
        current=deps["user"],
    )

    assert response.media_type == "application/pdf"
    assert "Content-Disposition" in response.headers


def test_generate_pnl_pdf_weekly(mock_deps_portfolio, monkeypatch):
    """Test weekly PDF report generation"""
    deps = mock_deps_portfolio

    class MockPdfGenerator:
        def generate_pnl_report(self, **kwargs):
            return b"MOCK_PDF_CONTENT"

    def mock_pdf_init():
        return MockPdfGenerator()

    monkeypatch.setattr("server.app.routers.reports.PdfGenerator", mock_pdf_init)

    response = reports_module.generate_pnl_pdf(
        period="weekly",
        start_date=None,
        end_date=None,
        include_unrealized=True,
        trade_mode=TradeMode.PAPER,
        db=deps["db"],
        current=deps["user"],
    )

    assert response.media_type == "application/pdf"


def test_generate_pnl_pdf_monthly(mock_deps_portfolio, monkeypatch):
    """Test monthly PDF report generation"""
    deps = mock_deps_portfolio

    class MockPdfGenerator:
        def generate_pnl_report(self, **kwargs):
            return b"MOCK_PDF_CONTENT"

    def mock_pdf_init():
        return MockPdfGenerator()

    monkeypatch.setattr("server.app.routers.reports.PdfGenerator", mock_pdf_init)

    response = reports_module.generate_pnl_pdf(
        period="monthly",
        start_date=None,
        end_date=None,
        include_unrealized=True,
        trade_mode=TradeMode.PAPER,
        db=deps["db"],
        current=deps["user"],
    )

    assert response.media_type == "application/pdf"


def test_generate_pnl_pdf_custom_with_dates(mock_deps_portfolio, monkeypatch):
    """Test custom period PDF report with explicit dates"""
    deps = mock_deps_portfolio

    class MockPdfGenerator:
        def generate_pnl_report(self, **kwargs):
            return b"MOCK_PDF_CONTENT"

    def mock_pdf_init():
        return MockPdfGenerator()

    monkeypatch.setattr("server.app.routers.reports.PdfGenerator", mock_pdf_init)

    start = date.today() - timedelta(days=10)
    end = date.today()

    reports_module.generate_pnl_pdf(
        period="custom",
        start_date=start,
        end_date=end,
        include_unrealized=False,
        trade_mode=TradeMode.BROKER,
        db=deps["db"],
        current=deps["user"],
    )


def test_generate_pnl_pdf_custom_no_end_date(mock_deps_portfolio, monkeypatch):
    """Test custom period defaults end_date to today"""
    deps = mock_deps_portfolio

    class MockPdfGenerator:
        def generate_pnl_report(self, **kwargs):
            return b"MOCK_PDF_CONTENT"

    def mock_pdf_init():
        return MockPdfGenerator()

    monkeypatch.setattr("server.app.routers.reports.PdfGenerator", mock_pdf_init)

    start = date.today() - timedelta(days=15)

    response = reports_module.generate_pnl_pdf(
        period="custom",
        start_date=start,
        end_date=None,
        include_unrealized=True,
        trade_mode=TradeMode.PAPER,
        db=deps["db"],
        current=deps["user"],
    )

    assert response.media_type == "application/pdf"


def test_generate_pnl_pdf_custom_no_dates(mock_deps_portfolio, monkeypatch):
    """Test custom period with no dates defaults to last 30 days"""
    deps = mock_deps_portfolio

    class MockPdfGenerator:
        def generate_pnl_report(self, **kwargs):
            return b"MOCK_PDF_CONTENT"

    def mock_pdf_init():
        return MockPdfGenerator()

    monkeypatch.setattr("server.app.routers.reports.PdfGenerator", mock_pdf_init)

    response = reports_module.generate_pnl_pdf(
        period="custom",
        start_date=None,
        end_date=None,
        include_unrealized=True,
        trade_mode=TradeMode.PAPER,
        db=deps["db"],
        current=deps["user"],
    )

    assert response.media_type == "application/pdf"
