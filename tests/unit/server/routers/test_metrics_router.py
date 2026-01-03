from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from server.app.routers import metrics as metrics_router


class FakeResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class FakeDB:
    def __init__(self, positions):
        self._positions = positions

    def execute(self, stmt):
        return FakeResult(self._positions)


class FakeSettingsRepo:
    def __init__(self, db):
        self.db = db

    def ensure_default(self, user_id):
        return SimpleNamespace(trade_mode="paper")


@pytest.fixture
def current_user():
    return SimpleNamespace(id=42)


def _patch_settings(monkeypatch):
    monkeypatch.setattr(metrics_router, "SettingsRepository", lambda db: FakeSettingsRepo(db))


def test_get_dashboard_metrics_no_positions(monkeypatch, current_user):
    _patch_settings(monkeypatch)
    db = FakeDB([])

    result = metrics_router.get_dashboard_metrics(
        db=db,
        current=current_user,
        trade_mode=None,
        period_days=30,
    )

    assert result.total_trades == 0
    assert result.win_rate == 0.0
    assert result.best_trade_profit is None
    assert result.avg_holding_period_days == 0.0


def test_get_dashboard_metrics_calculates_values(monkeypatch, current_user):
    _patch_settings(monkeypatch)
    now = datetime(2026, 1, 1, 12, 0)

    positions = [
        SimpleNamespace(
            user_id=current_user.id,
            closed_at=now,
            opened_at=now - timedelta(days=1),
            realized_pnl=120.0,
            symbol="ABC",
            buy_order_id=None,
        ),
        SimpleNamespace(
            user_id=current_user.id,
            closed_at=now + timedelta(days=1),
            opened_at=now,
            realized_pnl=-50.0,
            symbol="XYZ",
            buy_order_id=None,
        ),
        SimpleNamespace(
            user_id=current_user.id,
            closed_at=now + timedelta(days=2),
            opened_at=now - timedelta(days=1),
            realized_pnl=30.0,
            symbol="DEF",
            buy_order_id=None,
        ),
    ]

    db = FakeDB(positions)
    result = metrics_router.get_dashboard_metrics(
        db=db,
        current=current_user,
        period_days=7,
        trade_mode=None,
    )

    assert result.total_trades == 3
    assert result.profitable_trades == 2
    assert result.losing_trades == 1
    assert result.win_rate == round(2 / 3 * 100, 2)
    assert result.average_profit_per_trade == 75.0
    assert result.best_trade_profit == 120.0
    assert result.worst_trade_loss == -50.0
    assert result.total_realized_pnl == 100.0
    assert result.days_traded == 3


def test_get_daily_metrics_invalid_date(monkeypatch, current_user):
    _patch_settings(monkeypatch)

    with pytest.raises(HTTPException) as excinfo:
        metrics_router.get_daily_metrics(
            date_str="2025-99-99",
            db=SimpleNamespace(),
            current=current_user,
        )
    assert excinfo.value.status_code == 400


def test_get_db_connection_pool_status(monkeypatch, current_user):
    pool_payload = {
        "pool_size": 5,
        "checked_in": 3,
        "checked_out": 2,
        "overflow": 1,
        "max_overflow": 5,
        "total_connections": 6,
        "utilization_percent": 50.0,
    }

    monkeypatch.setattr(metrics_router, "get_pool_status", lambda engine: pool_payload)
    monkeypatch.setattr(metrics_router, "check_pool_health", lambda engine: (True, "healthy"))

    result = metrics_router.get_db_connection_pool_status(current=current_user)

    assert result.pool_size == 5
    assert result.is_healthy is True
    assert result.health_message == "healthy"
