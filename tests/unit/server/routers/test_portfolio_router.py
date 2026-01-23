from datetime import date
from types import SimpleNamespace

from server.app.routers import paper_trading as paper_trading_router
from server.app.routers import portfolio as portfolio_router
from src.infrastructure.db.models import TradeMode


class ComparisonColumn:
    def __ge__(self, other):
        return True

    def __le__(self, other):
        return True

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def desc(self):
        return self

    def __hash__(self):
        return 1


class DummyPortfolioSnapshot:
    date = ComparisonColumn()
    user_id = ComparisonColumn()
    snapshot_type = ComparisonColumn()

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class DummyPositions:
    user_id = ComparisonColumn()
    closed_at = ComparisonColumn()


def _patch_settings_repo(monkeypatch, trade_mode: TradeMode):
    class FakeSettingsRepo:
        def ensure_default(self, user_id):
            return SimpleNamespace(trade_mode=trade_mode)

    monkeypatch.setattr(portfolio_router, "SettingsRepository", lambda db: FakeSettingsRepo())


def _make_portfolio_source():
    account = SimpleNamespace(
        initial_capital=500.0,
        available_cash=150.0,
        total_value=700.0,
        unrealized_pnl=30.0,
        realized_pnl=20.0,
    )
    holdings = [SimpleNamespace(symbol="XYZ", quantity=2, average_price=100.0, current_price=115.0)]
    return SimpleNamespace(account=account, holdings=holdings)


def test_portfolio_history_returns_entries(monkeypatch):
    snapshot = SimpleNamespace(
        date=date(2025, 1, 2),
        total_value=100.0,
        invested_value=80.0,
        available_cash=20.0,
        unrealized_pnl=15.0,
        realized_pnl=5.0,
        open_positions_count=1,
        closed_positions_count=0,
        total_return=5.0,
        daily_return=0.5,
        snapshot_type="eod",
    )

    class FakeHistoryQuery:
        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def all(self):
            return [snapshot]

    class FakeHistoryDB:
        def query(self, model):
            assert model is portfolio_router.PortfolioSnapshot
            return FakeHistoryQuery()

    monkeypatch.setattr(portfolio_router, "PortfolioSnapshot", DummyPortfolioSnapshot)

    result = portfolio_router.portfolio_history(
        start=date(2025, 1, 1),
        end=date(2025, 1, 3),
        limit=10,
        db=FakeHistoryDB(),
        current=SimpleNamespace(id=1),
    )

    assert len(result) == 1
    assert result[0]["total_value"] == 100.0
    assert result[0]["snapshot_type"] == "eod"


def test_create_portfolio_snapshot_inserts_record(monkeypatch):
    _patch_settings_repo(monkeypatch, TradeMode.PAPER)
    monkeypatch.setattr(portfolio_router, "PortfolioSnapshot", DummyPortfolioSnapshot)
    monkeypatch.setattr(portfolio_router, "Positions", DummyPositions)
    monkeypatch.setattr(
        paper_trading_router,
        "get_paper_trading_portfolio",
        lambda page=1, page_size=10, db=None, current=None: _make_portfolio_source(),
    )

    class PositionsQuery:
        def filter(self, *args, **kwargs):
            return self

        def count(self):
            return 3

    class SnapshotQuery:
        def filter(self, *args, **kwargs):
            return self

        def one_or_none(self):
            return None

    class FakeSnapshotDB:
        def __init__(self):
            self.added = None
            self.committed = False
            self.refreshed = []

        def query(self, model):
            if model is portfolio_router.Positions:
                return PositionsQuery()
            return SnapshotQuery()

        def add(self, obj):
            self.added = obj

        def commit(self):
            self.committed = True

        def refresh(self, obj):
            self.refreshed.append(obj)

    fake_db = FakeSnapshotDB()

    response = portfolio_router.create_portfolio_snapshot(
        snapshot_date=date(2025, 1, 10),
        db=fake_db,
        current=SimpleNamespace(id=5),
    )

    assert response["status"] == "created"
    assert fake_db.committed is True
    assert isinstance(fake_db.added, portfolio_router.PortfolioSnapshot)
    assert fake_db.added.user_id == 5
    assert fake_db.added.open_positions_count == 1
