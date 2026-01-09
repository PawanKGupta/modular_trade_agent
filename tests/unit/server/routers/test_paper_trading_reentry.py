"""Tests for reentry data in paper trading portfolio endpoint"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from server.app.routers import paper_trading
from src.infrastructure.db.models import Positions, UserRole


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "User"),
            role=kwargs.get("role", UserRole.USER),
        )


class DummyPaperTradeStore:
    def __init__(self, storage_path, auto_save=False):
        self.storage_path = storage_path
        self.auto_save = auto_save
        self._account = None
        self._holdings = {}
        self._orders = []
        self._transactions = []

    def get_account(self):
        return self._account

    def get_all_holdings(self):
        return self._holdings

    def get_all_orders(self):
        return self._orders

    def get_all_transactions(self):
        return self._transactions


class DummyPaperTradeReporter:
    def __init__(self, store):
        self.store = store

    def order_statistics(self):
        orders = self.store.get_all_orders()
        total = len(orders)
        completed = sum(1 for o in orders if o.get("status") == "COMPLETED")
        buy_count = sum(1 for o in orders if o.get("transaction_type") == "BUY")
        sell_count = sum(1 for o in orders if o.get("transaction_type") == "SELL")
        pending = sum(1 for o in orders if o.get("status") == "PENDING")
        cancelled = sum(1 for o in orders if o.get("status") == "CANCELLED")
        rejected = sum(1 for o in orders if o.get("status") == "REJECTED")

        return {
            "total_orders": total,
            "completed_orders": completed,
            "buy_orders": buy_count,
            "sell_orders": sell_count,
            "pending_orders": pending,
            "cancelled_orders": cancelled,
            "rejected_orders": rejected,
        }


class DummyPositionsRepository:
    def __init__(self, db):
        self.db = db
        self.positions = {}
        self.positions_list = []  # For list() method

    def get_by_symbol(self, user_id, symbol):
        return self.positions.get((user_id, symbol.upper()))

    def list(self, user_id):
        """Return all positions for user_id"""
        return self.positions_list


def test_get_paper_trading_portfolio_with_reentry_data(monkeypatch):
    """Test that reentry data is fetched from positions table and included in holdings"""
    user = DummyUser(id=42)

    def mock_exists(self):
        return True

    monkeypatch.setattr(Path, "exists", mock_exists)

    store = DummyPaperTradeStore("test_path")
    store._account = {
        "initial_capital": 100000.0,
        "available_cash": 50000.0,
        "realized_pnl": 0.0,
    }
    store._holdings = {
        "RELIANCE": {  # No .NS suffix to test normalization
            "quantity": 10,
            "average_price": 2500.0,
            "current_price": 2600.0,
        }
    }
    store._orders = []

    def mock_store_init(storage_path, auto_save=False):
        return store

    monkeypatch.setattr(paper_trading, "PaperTradeStore", mock_store_init)

    def mock_reporter_init(store):
        return DummyPaperTradeReporter(store)

    monkeypatch.setattr(paper_trading, "PaperTradeReporter", mock_reporter_init)

    # Mock positions repository with reentry data
    mock_position = MagicMock(spec=Positions)
    mock_position.reentry_count = 2
    mock_position.entry_rsi = 28.5
    mock_position.initial_entry_price = 2500.0
    mock_position.reentries = {
        "reentries": [
            {
                "qty": 5,
                "price": 2400.0,
                "time": "2025-01-15T10:00:00",
                "level": 20,
                "rsi": 18.5,
                "cycle": 1,
            },
            {
                "qty": 3,
                "price": 2300.0,
                "time": "2025-01-20T10:00:00",
                "level": 10,
                "rsi": 9.2,
                "cycle": 2,
            },
        ]
    }

    positions_repo = DummyPositionsRepository(None)
    positions_repo.positions[(42, "RELIANCE")] = mock_position
    positions_repo.positions_list = [mock_position]  # For list() method

    def mock_positions_repo_init(db):
        return positions_repo

    monkeypatch.setattr(
        "src.infrastructure.persistence.positions_repository.PositionsRepository",
        mock_positions_repo_init,
    )

    # Mock yfinance
    with patch("yfinance.Ticker") as mock_ticker_class:
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"currentPrice": 2600.0}
        mock_ticker_class.return_value = mock_ticker_instance

        def mock_path_exists(self):
            return False if "active_sell_orders.json" in str(self) else True

        monkeypatch.setattr(Path, "exists", mock_path_exists)

        db_session = MagicMock()
        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

        assert len(result.holdings) == 1
        holding = result.holdings[0]
        assert holding.symbol == "RELIANCE"
        assert holding.reentry_count == 2
        assert holding.entry_rsi == 28.5
        assert holding.initial_entry_price == 2500.0
        assert holding.reentries is not None
        assert len(holding.reentries) == 2
        assert holding.reentries[0]["qty"] == 5
        assert holding.reentries[0]["price"] == 2400.0
        assert holding.reentries[0]["level"] == 20
        assert holding.reentries[1]["qty"] == 3
        assert holding.reentries[1]["price"] == 2300.0
        assert holding.reentries[1]["level"] == 10


def test_get_paper_trading_portfolio_with_reentry_data_old_format(monkeypatch):
    """Test that old format reentries (direct array) is handled correctly"""
    user = DummyUser(id=42)

    def mock_exists(self):
        return True

    monkeypatch.setattr(Path, "exists", mock_exists)

    store = DummyPaperTradeStore("test_path")
    store._account = {
        "initial_capital": 100000.0,
        "available_cash": 50000.0,
        "realized_pnl": 0.0,
    }
    store._holdings = {
        "RELIANCE.NS": {
            "quantity": 10,
            "average_price": 2500.0,
            "current_price": 2600.0,
        }
    }
    store._orders = []

    def mock_store_init(storage_path, auto_save=False):
        return store

    monkeypatch.setattr(paper_trading, "PaperTradeStore", mock_store_init)

    def mock_reporter_init(store):
        return DummyPaperTradeReporter(store)

    monkeypatch.setattr(paper_trading, "PaperTradeReporter", mock_reporter_init)

    # Mock positions repository with old format reentries (direct array)
    mock_position = MagicMock(spec=Positions)
    mock_position.reentry_count = 1
    mock_position.entry_rsi = 29.0
    mock_position.initial_entry_price = 2500.0
    mock_position.reentries = [  # Old format: direct array
        {
            "qty": 5,
            "price": 2400.0,
            "time": "2025-01-15T10:00:00",
        }
    ]

    positions_repo = DummyPositionsRepository(None)
    positions_repo.positions[(42, "RELIANCE")] = mock_position
    positions_repo.positions_list = [mock_position]  # For list() method

    def mock_positions_repo_init(db):
        return positions_repo

    monkeypatch.setattr(
        "src.infrastructure.persistence.positions_repository.PositionsRepository",
        mock_positions_repo_init,
    )

    # Mock yfinance
    with patch("yfinance.Ticker") as mock_ticker_class:
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"currentPrice": 2600.0}
        mock_ticker_class.return_value = mock_ticker_instance

        def mock_path_exists(self):
            return False if "active_sell_orders.json" in str(self) else True

        monkeypatch.setattr(Path, "exists", mock_path_exists)

        db_session = MagicMock()
        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

        assert len(result.holdings) == 1
        holding = result.holdings[0]
        assert holding.reentry_count == 1
        assert holding.reentries is not None
        assert len(holding.reentries) == 1
        assert holding.reentries[0]["qty"] == 5


def test_get_paper_trading_portfolio_without_reentry_data(monkeypatch):
    """Test that holdings without reentry data return defaults"""
    user = DummyUser(id=42)

    def mock_exists(self):
        return True

    monkeypatch.setattr(Path, "exists", mock_exists)

    store = DummyPaperTradeStore("test_path")
    store._account = {
        "initial_capital": 100000.0,
        "available_cash": 50000.0,
        "realized_pnl": 0.0,
    }
    store._holdings = {
        "TCS": {
            "quantity": 20,
            "average_price": 3500.0,
            "current_price": 3600.0,
        }
    }
    store._orders = []

    def mock_store_init(storage_path, auto_save=False):
        return store

    monkeypatch.setattr(paper_trading, "PaperTradeStore", mock_store_init)

    def mock_reporter_init(store):
        return DummyPaperTradeReporter(store)

    monkeypatch.setattr(paper_trading, "PaperTradeReporter", mock_reporter_init)

    # Mock positions repository - no position found
    positions_repo = DummyPositionsRepository(None)

    def mock_positions_repo_init(db):
        return positions_repo

    monkeypatch.setattr(
        "src.infrastructure.persistence.positions_repository.PositionsRepository",
        mock_positions_repo_init,
    )

    # Mock yfinance
    with patch("yfinance.Ticker") as mock_ticker_class:
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"currentPrice": 3600.0}
        mock_ticker_class.return_value = mock_ticker_instance

        def mock_path_exists(self):
            return False if "active_sell_orders.json" in str(self) else True

        monkeypatch.setattr(Path, "exists", mock_path_exists)

        db_session = MagicMock()
        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

        assert len(result.holdings) == 1
        holding = result.holdings[0]
        assert holding.symbol == "TCS"
        # Should have default values
        assert holding.reentry_count == 0
        assert holding.entry_rsi is None
        assert holding.initial_entry_price is None
        assert holding.reentries is None


def test_get_paper_trading_portfolio_reentry_data_symbol_normalization(monkeypatch):
    """Test that symbol normalization works correctly for reentry data lookup"""
    user = DummyUser(id=42)

    def mock_exists(self):
        return True

    monkeypatch.setattr(Path, "exists", mock_exists)

    store = DummyPaperTradeStore("test_path")
    store._account = {
        "initial_capital": 100000.0,
        "available_cash": 50000.0,
        "realized_pnl": 0.0,
    }
    # Test various symbol formats
    store._holdings = {
        "RELIANCE-EQ": {  # Broker format with -EQ suffix
            "quantity": 10,
            "average_price": 2500.0,
            "current_price": 2600.0,
        },
        "TCS.NS": {  # With .NS suffix
            "quantity": 20,
            "average_price": 3500.0,
            "current_price": 3600.0,
        },
    }
    store._orders = []

    def mock_store_init(storage_path, auto_save=False):
        return store

    monkeypatch.setattr(paper_trading, "PaperTradeStore", mock_store_init)

    def mock_reporter_init(store):
        return DummyPaperTradeReporter(store)

    monkeypatch.setattr(paper_trading, "PaperTradeReporter", mock_reporter_init)

    # Mock positions repository - positions stored as "RELIANCE" and "TCS" (normalized)
    mock_position1 = MagicMock(spec=Positions)
    mock_position1.reentry_count = 1
    mock_position1.entry_rsi = 28.0
    mock_position1.initial_entry_price = 2500.0
    mock_position1.reentries = {
        "reentries": [{"qty": 5, "price": 2400.0, "time": "2025-01-15T10:00:00"}]
    }

    mock_position2 = MagicMock(spec=Positions)
    mock_position2.reentry_count = 0
    mock_position2.entry_rsi = None
    mock_position2.initial_entry_price = None
    mock_position2.reentries = None

    positions_repo = DummyPositionsRepository(None)
    positions_repo.positions[(42, "RELIANCE")] = mock_position1
    positions_repo.positions[(42, "TCS")] = mock_position2

    def mock_positions_repo_init(db):
        return positions_repo

    monkeypatch.setattr(
        "src.infrastructure.persistence.positions_repository.PositionsRepository",
        mock_positions_repo_init,
    )

    # Mock yfinance
    with patch("yfinance.Ticker") as mock_ticker_class:
        call_count = [0]

        def create_mock_ticker(ticker_symbol):
            call_count[0] += 1
            mock_ticker = MagicMock()
            if "RELIANCE" in ticker_symbol or call_count[0] == 1:
                mock_ticker.info = {"currentPrice": 2600.0}
            else:
                mock_ticker.info = {"currentPrice": 3600.0}
            return mock_ticker

        mock_ticker_class.side_effect = create_mock_ticker

        def mock_path_exists(self):
            return False if "active_sell_orders.json" in str(self) else True

        monkeypatch.setattr(Path, "exists", mock_path_exists)

        db_session = MagicMock()
        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

        assert len(result.holdings) == 2

        # RELIANCE-EQ should match RELIANCE in database
        reliance_holding = next(h for h in result.holdings if h.symbol == "RELIANCE-EQ")
        assert reliance_holding.reentry_count == 1
        assert reliance_holding.entry_rsi == 28.0

        # TCS.NS should match TCS in database
        tcs_holding = next(h for h in result.holdings if h.symbol == "TCS.NS")
        assert tcs_holding.reentry_count == 0
        assert tcs_holding.entry_rsi is None


def test_get_paper_trading_portfolio_reentry_data_invalid_format(monkeypatch):
    """Test that invalid reentries format (neither dict nor list) is handled gracefully"""
    user = DummyUser(id=42)

    def mock_exists(self):
        return True

    monkeypatch.setattr(Path, "exists", mock_exists)

    store = DummyPaperTradeStore("test_path")
    store._account = {
        "initial_capital": 100000.0,
        "available_cash": 50000.0,
        "realized_pnl": 0.0,
    }
    store._holdings = {
        "RELIANCE": {
            "quantity": 10,
            "average_price": 2500.0,
            "current_price": 2600.0,
        }
    }
    store._orders = []

    def mock_store_init(storage_path, auto_save=False):
        return store

    monkeypatch.setattr(paper_trading, "PaperTradeStore", mock_store_init)

    def mock_reporter_init(store):
        return DummyPaperTradeReporter(store)

    monkeypatch.setattr(paper_trading, "PaperTradeReporter", mock_reporter_init)

    # Mock positions repository with invalid reentries format (string instead of dict/list)
    mock_position = MagicMock(spec=Positions)
    mock_position.reentry_count = 1
    mock_position.entry_rsi = 28.5
    mock_position.initial_entry_price = 2500.0
    mock_position.reentries = "invalid_format"  # Invalid format - neither dict nor list

    positions_repo = DummyPositionsRepository(None)
    positions_repo.positions[(42, "RELIANCE")] = mock_position
    positions_repo.positions_list = [mock_position]  # For list() method

    def mock_positions_repo_init(db):
        return positions_repo

    monkeypatch.setattr(
        "src.infrastructure.persistence.positions_repository.PositionsRepository",
        mock_positions_repo_init,
    )

    # Mock yfinance
    with patch("yfinance.Ticker") as mock_ticker_class:
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"currentPrice": 2600.0}
        mock_ticker_class.return_value = mock_ticker_instance

        def mock_path_exists(self):
            return False if "active_sell_orders.json" in str(self) else True

        monkeypatch.setattr(Path, "exists", mock_path_exists)

        db_session = MagicMock()
        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

        assert len(result.holdings) == 1
        holding = result.holdings[0]
        # Should have reentry_count and entry_rsi, but reentries should be empty list
        assert holding.reentry_count == 1
        assert holding.entry_rsi == 28.5
        assert holding.reentries == []


def test_get_paper_trading_portfolio_reentry_data_exception_handling(monkeypatch):
    """Test that exceptions during reentry data fetch don't break the endpoint"""
    user = DummyUser(id=42)

    def mock_exists(self):
        return True

    monkeypatch.setattr(Path, "exists", mock_exists)

    store = DummyPaperTradeStore("test_path")
    store._account = {
        "initial_capital": 100000.0,
        "available_cash": 50000.0,
        "realized_pnl": 0.0,
    }
    store._holdings = {
        "RELIANCE": {
            "quantity": 10,
            "average_price": 2500.0,
            "current_price": 2600.0,
        }
    }
    store._orders = []

    def mock_store_init(storage_path, auto_save=False):
        return store

    monkeypatch.setattr(paper_trading, "PaperTradeStore", mock_store_init)

    def mock_reporter_init(store):
        return DummyPaperTradeReporter(store)

    monkeypatch.setattr(paper_trading, "PaperTradeReporter", mock_reporter_init)

    # Mock positions repository to raise exception
    def mock_positions_repo_init(db):
        raise Exception("Database connection error")

    monkeypatch.setattr(
        "src.infrastructure.persistence.positions_repository.PositionsRepository",
        mock_positions_repo_init,
    )

    # Mock yfinance
    with patch("yfinance.Ticker") as mock_ticker_class:
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"currentPrice": 2600.0}
        mock_ticker_class.return_value = mock_ticker_instance

        def mock_path_exists(self):
            return False if "active_sell_orders.json" in str(self) else True

        monkeypatch.setattr(Path, "exists", mock_path_exists)

        db_session = MagicMock()
        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user)

        # Should still return holdings with default reentry values
        assert len(result.holdings) == 1
        holding = result.holdings[0]
        assert holding.reentry_count == 0
        assert holding.entry_rsi is None
        assert holding.reentries is None
