from datetime import date, datetime
from types import SimpleNamespace

import pytest

from server.app.services import portfolio_calculation_service as service_module


class DummyPositionsRepository:
    def __init__(self, positions):
        self._positions = positions

    def list(self, user_id):
        return self._positions


class DummyPnlRepository:
    def __init__(self, pnl_entries):
        self._entries = pnl_entries

    def range(self, user_id, start_date, end_date):
        return self._entries


class DummySnapshotRepository:
    def __init__(self, prev_snapshot=None):
        self.prev_snapshot = prev_snapshot
        self.upsert_args = None

    def get_by_date(self, user_id, lookup_date):
        return self.prev_snapshot

    def upsert_daily(self, *, user_id, snapshot_date, snapshot_data, snapshot_type):
        self.upsert_args = dict(
            user_id=user_id,
            snapshot_date=snapshot_date,
            snapshot_data=snapshot_data,
            snapshot_type=snapshot_type,
        )
        return SimpleNamespace(
            **{
                "user_id": user_id,
                "snapshot_date": snapshot_date,
                **snapshot_data,
            }
        )


def _patch_repositories(monkeypatch, *, positions, pnls, snapshot=None):
    snapshot_repo = DummySnapshotRepository(prev_snapshot=snapshot)
    monkeypatch.setattr(
        service_module,
        "PortfolioSnapshotRepository",
        lambda db: snapshot_repo,
    )
    monkeypatch.setattr(
        service_module,
        "PositionsRepository",
        lambda db: DummyPositionsRepository(positions),
    )
    monkeypatch.setattr(
        service_module,
        "PnlRepository",
        lambda db: DummyPnlRepository(pnls),
    )
    return snapshot_repo


def _position(*, avg_price, quantity, unrealized_pnl, closed_at=None):
    return SimpleNamespace(
        avg_price=avg_price,
        quantity=quantity,
        unrealized_pnl=unrealized_pnl,
        closed_at=closed_at,
    )


def _pnl_entry(realized_pnl):
    return SimpleNamespace(realized_pnl=realized_pnl)


def test_calculate_portfolio_metrics_without_prev_snapshot(monkeypatch):
    positions = [
        _position(
            avg_price=10.0,
            quantity=2,
            unrealized_pnl=5.0,
            closed_at=None,
        ),
        _position(
            avg_price=20.0,
            quantity=1,
            unrealized_pnl=-3.0,
            closed_at=datetime(2024, 12, 31),
        ),
    ]
    snapshot_repo = _patch_repositories(
        monkeypatch,
        positions=positions,
        pnls=[_pnl_entry(150.0)],
    )

    service = service_module.PortfolioCalculationService(db=SimpleNamespace())
    result = service.calculate_portfolio_metrics(
        user_id=1,
        snapshot_date=date(2025, 1, 2),
    )

    assert result["invested_value"] == 20.0
    assert result["open_positions_count"] == 1
    assert result["closed_positions_count"] == 1
    assert result["realized_pnl"] == 150.0
    assert result["total_value"] == pytest.approx(25.0)
    assert result["daily_return"] == 0.0
    assert result["total_return"] == pytest.approx(25.0)
    assert snapshot_repo.upsert_args is None


def test_calculate_portfolio_metrics_with_prev_snapshot(monkeypatch):
    positions = [
        _position(
            avg_price=5.0,
            quantity=3,
            unrealized_pnl=6.0,
            closed_at=None,
        ),
    ]
    prev_snapshot = SimpleNamespace(total_value=10.0)
    _patch_repositories(
        monkeypatch,
        positions=positions,
        pnls=[_pnl_entry(30.0)],
        snapshot=prev_snapshot,
    )

    service = service_module.PortfolioCalculationService(db=SimpleNamespace())
    result = service.calculate_portfolio_metrics(
        user_id=2,
        snapshot_date=date(2025, 1, 2),
    )

    assert result["total_value"] == pytest.approx(21.0)
    assert result["daily_return"] == pytest.approx(110.0)
    assert result["total_return"] == pytest.approx(40.0)


def test_create_snapshot_persists_metrics(monkeypatch):
    snapshot_repo = DummySnapshotRepository()
    monkeypatch.setattr(
        service_module,
        "PortfolioSnapshotRepository",
        lambda db: snapshot_repo,
    )
    monkeypatch.setattr(
        service_module,
        "PositionsRepository",
        lambda db: DummyPositionsRepository([]),
    )
    monkeypatch.setattr(
        service_module,
        "PnlRepository",
        lambda db: DummyPnlRepository([]),
    )

    metrics = {
        "total_value": 50.0,
        "invested_value": 40.0,
        "available_cash": 10.0,
        "unrealized_pnl": 5.0,
        "realized_pnl": 5.0,
        "open_positions_count": 1,
        "closed_positions_count": 0,
        "total_return": 25.0,
        "daily_return": 2.0,
    }

    service = service_module.PortfolioCalculationService(db=SimpleNamespace())
    monkeypatch.setattr(
        service_module.PortfolioCalculationService,
        "calculate_portfolio_metrics",
        lambda self, user_id, snapshot_date, trade_mode=None: metrics,
    )

    snapshot = service.create_snapshot(
        user_id=5,
        snapshot_date=date(2025, 1, 3),
        snapshot_type="eod",
    )

    assert snapshot.user_id == 5
    assert snapshot.total_value == 50.0
    assert snapshot.daily_return == 2.0
    assert snapshot_repo.upsert_args["snapshot_type"] == "eod"
