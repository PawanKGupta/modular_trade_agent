"""Tests for the metrics router endpoints"""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from server.app.routers import metrics as metrics_module
from src.infrastructure.db.models import Positions, TradeMode, UserRole, Users, UserSettings


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
def mock_deps(monkeypatch, db_session):
    """Mock dependencies for metrics endpoints"""
    # Create a real user in the database
    user = Users(
        id=1,
        email="user@example.com",
        name="Test User",
        password_hash="$2b$12$dummy",
        role=UserRole.USER,
        is_active=True,
    )
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

    monkeypatch.setattr("server.app.routers.metrics.get_current_user", mock_get_current_user)
    monkeypatch.setattr("server.app.routers.metrics.get_db", mock_get_db)

    return {"db": db_session, "user": current_user}


def test_get_dashboard_metrics_empty_positions(mock_deps):
    """Test metrics with no positions"""
    deps = mock_deps
    result = metrics_module.get_dashboard_metrics(
        period_days=30, trade_mode=None, db=deps["db"], current=deps["user"]
    )

    assert result.total_trades == 0
    assert result.profitable_trades == 0
    assert result.losing_trades == 0
    assert result.win_rate == 0.0
    assert result.average_profit_per_trade == 0.0
    assert result.best_trade_profit is None
    assert result.worst_trade_loss is None
    assert result.total_realized_pnl == 0.0
    assert result.best_trade_symbol is None
    assert result.worst_trade_symbol is None
    assert result.days_traded == 0
    assert result.avg_holding_period_days == 0.0


def test_get_dashboard_metrics_with_profitable_position(mock_deps):
    """Test metrics with a profitable position"""
    deps = mock_deps
    db = deps["db"]
    user_id = deps["user"].id

    now = datetime.now()
    position = Positions(
        user_id=user_id,
        symbol="AAPL",
        quantity=10,
        avg_price=100.0,
        opened_at=now - timedelta(days=5),
        closed_at=now,
        exit_price=110.0,
        realized_pnl=100.0,
        sell_order_id=None,
    )
    db.add(position)
    db.commit()

    result = metrics_module.get_dashboard_metrics(
        period_days=30, trade_mode=None, db=db, current=deps["user"]
    )

    assert result.total_trades == 1
    assert result.profitable_trades == 1
    assert result.losing_trades == 0
    assert result.win_rate == 100.0
    assert result.best_trade_profit == 100.0
    assert result.worst_trade_loss is None
    assert result.total_realized_pnl == 100.0
    assert result.best_trade_symbol == "AAPL"
    assert result.worst_trade_symbol is None
    assert result.days_traded == 1


def test_get_dashboard_metrics_with_losing_position(mock_deps):
    """Test metrics with a losing position"""
    deps = mock_deps
    db = deps["db"]
    user_id = deps["user"].id

    now = datetime.now()
    position = Positions(
        user_id=user_id,
        symbol="GOOGL",
        quantity=5,
        avg_price=150.0,
        opened_at=now - timedelta(days=2),
        closed_at=now,
        exit_price=140.0,
        realized_pnl=-50.0,
        sell_order_id=None,
    )
    db.add(position)
    db.commit()

    result = metrics_module.get_dashboard_metrics(
        period_days=30, trade_mode=None, db=db, current=deps["user"]
    )

    assert result.total_trades == 1
    assert result.profitable_trades == 0
    assert result.losing_trades == 1
    assert result.win_rate == 0.0
    assert result.best_trade_profit is None
    assert result.worst_trade_loss == -50.0
    assert result.total_realized_pnl == -50.0
    assert result.worst_trade_symbol == "GOOGL"


def test_get_dashboard_metrics_mixed_positions(mock_deps):
    """Test metrics with multiple profitable and losing positions"""
    deps = mock_deps
    db = deps["db"]
    user_id = deps["user"].id

    now = datetime.now()

    # Profitable trades
    for i in range(3):
        position = Positions(
            user_id=user_id,
            symbol=f"SYM{i}",
            quantity=10,
            avg_price=100.0,
            opened_at=now - timedelta(days=i + 1),
            closed_at=now - timedelta(days=i),
            exit_price=110.0,
            realized_pnl=100.0 * (i + 1),
            sell_order_id=None,
        )
        db.add(position)

    # Losing trades
    for i in range(2):
        position = Positions(
            user_id=user_id,
            symbol=f"LOSS{i}",
            quantity=5,
            avg_price=150.0,
            opened_at=now - timedelta(days=i + 4),
            closed_at=now - timedelta(days=i + 3),
            exit_price=140.0,
            realized_pnl=-50.0 * (i + 1),
            sell_order_id=None,
        )
        db.add(position)

    db.commit()

    result = metrics_module.get_dashboard_metrics(
        period_days=30, trade_mode=None, db=db, current=deps["user"]
    )

    assert result.total_trades == 5
    assert result.profitable_trades == 3
    assert result.losing_trades == 2
    assert result.win_rate == 60.0
    assert result.best_trade_profit == 300.0
    assert result.worst_trade_loss == -100.0
    assert result.total_realized_pnl == 450.0  # 100 + 200 + 300 - 50 - 100
    assert result.days_traded == 5


def test_get_dashboard_metrics_date_range_filter(mock_deps):
    """Test metrics filters positions outside the period"""
    deps = mock_deps
    db = deps["db"]
    user_id = deps["user"].id

    now = datetime.now()

    # Position within range
    position_in_range = Positions(
        user_id=user_id,
        symbol="AAPL",
        quantity=10,
        avg_price=100.0,
        opened_at=now - timedelta(days=5),
        closed_at=now - timedelta(days=2),
        exit_price=110.0,
        realized_pnl=100.0,
        sell_order_id=None,
    )
    db.add(position_in_range)

    # Position outside range
    position_out_of_range = Positions(
        user_id=user_id,
        symbol="GOOGL",
        quantity=5,
        avg_price=150.0,
        opened_at=now - timedelta(days=50),
        closed_at=now - timedelta(days=40),
        exit_price=160.0,
        realized_pnl=50.0,
        sell_order_id=None,
    )
    db.add(position_out_of_range)
    db.commit()

    result = metrics_module.get_dashboard_metrics(
        period_days=30, trade_mode=None, db=db, current=deps["user"]
    )

    # Should only count the in-range position
    assert result.total_trades == 1
    assert result.best_trade_symbol == "AAPL"
    assert result.total_realized_pnl == 100.0


def test_get_dashboard_metrics_invalid_trade_mode(mock_deps):
    """Test metrics with invalid trade_mode raises error"""
    deps = mock_deps

    with pytest.raises(Exception) as exc_info:
        metrics_module.get_dashboard_metrics(
            period_days=30, trade_mode="invalid_mode", db=deps["db"], current=deps["user"]
        )

    assert "Invalid trade_mode" in str(exc_info.value.detail)


def test_get_dashboard_metrics_avg_holding_period(mock_deps):
    """Test average holding period calculation"""
    deps = mock_deps
    db = deps["db"]
    user_id = deps["user"].id

    now = datetime.now()

    # Trade held for 5 days
    position1 = Positions(
        user_id=user_id,
        symbol="SYM1",
        quantity=10,
        avg_price=100.0,
        opened_at=now - timedelta(days=10),
        closed_at=now - timedelta(days=5),
        exit_price=110.0,
        realized_pnl=100.0,
        sell_order_id=None,
    )

    # Trade held for 3 days
    position2 = Positions(
        user_id=user_id,
        symbol="SYM2",
        quantity=10,
        avg_price=100.0,
        opened_at=now - timedelta(days=4),
        closed_at=now - timedelta(days=1),
        exit_price=110.0,
        realized_pnl=100.0,
        sell_order_id=None,
    )

    db.add(position1)
    db.add(position2)
    db.commit()

    result = metrics_module.get_dashboard_metrics(
        period_days=30, trade_mode=None, db=db, current=deps["user"]
    )

    # Average holding period should be (5 + 3) / 2 = 4 days
    assert result.avg_holding_period_days == 4.0


def test_get_daily_metrics_empty_day(mock_deps):
    """Test daily metrics for a day with no trades"""
    deps = mock_deps
    db = deps["db"]

    target_date = date.today()
    result = metrics_module.get_daily_metrics(
        date_str=target_date.isoformat(),
        trade_mode=None,
        db=db,
        current=deps["user"],
    )

    assert result["date"] == target_date.isoformat()
    assert result["trades"] == 0
    assert result["profitable_trades"] == 0
    assert result["losing_trades"] == 0
    assert result["daily_pnl"] == 0.0
    assert result["win_rate"] == 0.0


def test_get_daily_metrics_with_trades(mock_deps):
    """Test daily metrics with trades for a specific day"""
    deps = mock_deps
    db = deps["db"]
    user_id = deps["user"].id

    target_date = date.today()
    target_datetime = datetime.combine(target_date, datetime.min.time())

    # Add trades for the target date
    position1 = Positions(
        user_id=user_id,
        symbol="AAPL",
        quantity=10,
        avg_price=100.0,
        opened_at=target_datetime - timedelta(hours=1),
        closed_at=target_datetime + timedelta(hours=1),
        exit_price=110.0,
        realized_pnl=100.0,
        sell_order_id=None,
    )

    position2 = Positions(
        user_id=user_id,
        symbol="GOOGL",
        quantity=5,
        avg_price=150.0,
        opened_at=target_datetime + timedelta(hours=2),
        closed_at=target_datetime + timedelta(hours=3),
        exit_price=145.0,
        realized_pnl=-25.0,
        sell_order_id=None,
    )

    db.add(position1)
    db.add(position2)
    db.commit()

    result = metrics_module.get_daily_metrics(
        date_str=target_date.isoformat(),
        trade_mode=None,
        db=db,
        current=deps["user"],
    )

    assert result["date"] == target_date.isoformat()
    assert result["trades"] == 2
    assert result["profitable_trades"] == 1
    assert result["losing_trades"] == 1
    assert result["daily_pnl"] == 75.0
    assert result["win_rate"] == 50.0


def test_get_daily_metrics_invalid_date_format(mock_deps):
    """Test daily metrics with invalid date format"""
    deps = mock_deps

    with pytest.raises(Exception) as exc_info:
        metrics_module.get_daily_metrics(
            date_str="invalid-date", trade_mode=None, db=deps["db"], current=deps["user"]
        )

    assert "Invalid date format" in str(exc_info.value.detail)


def test_get_daily_metrics_default_to_today(mock_deps):
    """Test daily metrics defaults to today when no date provided"""
    deps = mock_deps
    db = deps["db"]
    user_id = deps["user"].id

    today = date.today()
    today_datetime = datetime.combine(today, datetime.min.time())

    position = Positions(
        user_id=user_id,
        symbol="AAPL",
        quantity=10,
        avg_price=100.0,
        opened_at=today_datetime,
        closed_at=today_datetime + timedelta(hours=1),
        exit_price=105.0,
        realized_pnl=50.0,
        sell_order_id=None,
    )

    db.add(position)
    db.commit()

    result = metrics_module.get_daily_metrics(
        date_str=None, trade_mode=None, db=db, current=deps["user"]
    )

    assert result["trades"] == 1
    assert result["daily_pnl"] == 50.0


def test_get_dashboard_metrics_zero_realized_pnl_positions(mock_deps):
    """Test metrics with positions that have zero or null realized_pnl"""
    deps = mock_deps
    db = deps["db"]
    user_id = deps["user"].id

    now = datetime.now()

    # Position with None realized_pnl
    position1 = Positions(
        user_id=user_id,
        symbol="AAPL",
        quantity=10,
        avg_price=100.0,
        opened_at=now - timedelta(days=5),
        closed_at=now,
        exit_price=100.0,
        realized_pnl=None,
        sell_order_id=None,
    )

    # Position with zero realized_pnl
    position2 = Positions(
        user_id=user_id,
        symbol="GOOGL",
        quantity=5,
        avg_price=150.0,
        opened_at=now - timedelta(days=3),
        closed_at=now - timedelta(days=1),
        exit_price=150.0,
        realized_pnl=0.0,
        sell_order_id=None,
    )

    db.add(position1)
    db.add(position2)
    db.commit()

    result = metrics_module.get_dashboard_metrics(
        period_days=30, trade_mode=None, db=db, current=deps["user"]
    )

    assert result.total_trades == 2
    assert result.profitable_trades == 0
    assert result.losing_trades == 0
    assert result.win_rate == 0.0
    assert result.total_realized_pnl == 0.0
