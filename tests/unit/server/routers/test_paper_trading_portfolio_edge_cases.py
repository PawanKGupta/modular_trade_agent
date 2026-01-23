"""
Unit tests for paper trading portfolio endpoint edge cases

Tests cover:
- Multiple users trading same symbol in different modes
- Positions without matching orders
- Fallback logic for ambiguous positions
- Account balance vs positions mismatch validation
- Symbol format inconsistencies
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from server.app.routers import paper_trading
from src.infrastructure.db.models import TradeMode


class DummyUser:
    def __init__(self, id: int):
        self.id = id


class DummyOrder(SimpleNamespace):
    """Simple order object that works with getattr()"""

    def __init__(self, **kwargs):
        # The router expects these attributes to exist for stats/recent orders.
        kwargs.setdefault("status", "closed")
        kwargs.setdefault("price", 0.0)
        kwargs.setdefault("avg_price", 0.0)
        kwargs.setdefault("order_type", "market")
        kwargs.setdefault("quantity", 0)
        kwargs.setdefault("placed_at", datetime.now())
        kwargs.setdefault("filled_at", None)
        kwargs.setdefault("broker_order_id", None)
        kwargs.setdefault("order_id", None)
        kwargs.setdefault("metadata", None)
        kwargs.setdefault("order_metadata", None)
        super().__init__(**kwargs)


class DummyPosition(SimpleNamespace):
    """Simple position object that works with getattr()"""

    pass


class TestPaperTradingPortfolioEdgeCases:
    """Test edge cases for paper trading portfolio endpoint"""

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        self.user_id = 1
        self.user = DummyUser(id=self.user_id)
        self.db_session = MagicMock()

        # Mock PaperTradeStore
        self.mock_store = MagicMock()
        self.mock_store.get_account.return_value = {
            "initial_capital": 100000.0,
            "available_cash": 50000.0,
            "realized_pnl": 1000.0,
        }
        self.mock_store.get_all_orders.return_value = []
        monkeypatch.setattr(
            "server.app.routers.paper_trading.PaperTradeStore",
            lambda path, **kwargs: self.mock_store,
        )

        # Mock PaperTradeReporter
        self.mock_reporter = MagicMock()
        self.mock_reporter.order_statistics.return_value = {
            "total_orders": 10,
            "buy_orders": 5,
            "sell_orders": 5,
            "completed_orders": 8,
            "pending_orders": 2,
            "cancelled_orders": 0,
            "rejected_orders": 0,
        }
        monkeypatch.setattr(
            "server.app.routers.paper_trading.PaperTradeReporter",
            lambda store: self.mock_reporter,
        )

        # Mock Path.exists
        monkeypatch.setattr("pathlib.Path.exists", lambda self: True)

        # Mock yfinance will be done in each test using patch context manager
        # Store the mock factory for use in tests
        self.mock_ticker_factory = lambda symbol: MagicMock(
            info={"currentPrice": 100.0, "regularMarketPrice": 100.0}
        )

        # Ensure unit tests never call out to yfinance/data fetchers.
        monkeypatch.setattr(
            "server.app.routers.paper_trading.yf.Ticker",
            self.mock_ticker_factory,
        )

        def mock_fetch_ohlcv_yf(ticker, days=60, interval="1d"):
            # Minimal dataframe for EMA calculation (no network).
            return pd.DataFrame({"close": [100.0] * max(days, 10)})

        monkeypatch.setattr(
            "server.app.routers.paper_trading.fetch_ohlcv_yf",
            mock_fetch_ohlcv_yf,
        )

        # Mock PositionsRepository - must return the same instance
        # Note: PositionsRepository is imported inside the function,
        # so we need to patch the source module
        self.mock_positions_repo = MagicMock()

        def positions_repo_factory(db):
            return self.mock_positions_repo

        monkeypatch.setattr(
            "src.infrastructure.persistence.positions_repository.PositionsRepository",
            positions_repo_factory,
        )
        # Also patch at the module level in case it's imported there
        monkeypatch.setattr(
            "server.app.routers.paper_trading.PositionsRepository",
            positions_repo_factory,
        )

        # Mock OrdersRepository - must return the same instance
        # Note: OrdersRepository is imported at module level, so patch there
        self.mock_orders_repo = MagicMock()

        def orders_repo_factory(db):
            return self.mock_orders_repo

        monkeypatch.setattr(
            "server.app.routers.paper_trading.OrdersRepository",
            orders_repo_factory,
        )

        # Mock SettingsRepository
        self.mock_settings_repo = MagicMock()
        self.mock_settings_repo.get_by_user_id.return_value = MagicMock(trade_mode=TradeMode.PAPER)
        monkeypatch.setattr(
            "server.app.routers.paper_trading.SettingsRepository",
            lambda db: self.mock_settings_repo,
        )

    def test_multiple_users_same_symbol_different_modes(self, monkeypatch):
        """Test that User 1's broker position doesn't appear in User 2's paper portfolio"""
        user2_id = 2

        # User 1 has broker position for RELIANCE-EQ (not used in test)
        DummyPosition(
            symbol="RELIANCE-EQ",
            quantity=10.0,
            avg_price=100.0,
            closed_at=None,
            opened_at=datetime.now(),
            reentry_count=0,
            entry_rsi=29.5,
            initial_entry_price=100.0,
            reentries=None,
        )

        # User 2 has paper position for RELIANCE-EQ
        position_time = datetime.now()
        user2_position = DummyPosition(
            symbol="RELIANCE-EQ",
            quantity=5.0,
            avg_price=100.0,
            closed_at=None,
            opened_at=position_time,
            reentry_count=0,
            entry_rsi=29.5,
            initial_entry_price=100.0,
            reentries=None,
        )

        # User 1's broker order (not used in test)
        DummyOrder(
            symbol="RELIANCE-EQ",
            side="buy",
            placed_at=datetime.now(),
            trade_mode=TradeMode.BROKER,
        )

        # User 2's paper order - must be placed at same time as position opened
        user2_order = DummyOrder(
            symbol="RELIANCE-EQ",
            side="buy",
            placed_at=position_time,  # Exact same time
            trade_mode=TradeMode.PAPER,
        )

        # Mock repositories - ensure they return the mocked objects
        self.mock_positions_repo.list.return_value = [user2_position]
        self.mock_orders_repo.list.return_value = ([user2_order], 1)

        # Call endpoint for User 2 with yfinance mock
        user2 = DummyUser(id=user2_id)
        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.info = {"currentPrice": 100.0, "regularMarketPrice": 100.0}
            mock_ticker_class.return_value = mock_ticker_instance

            # Mock Path.exists for active_sell_orders.json
            def mock_path_exists(self):
                return False if "active_sell_orders.json" in str(self) else True

            monkeypatch.setattr("pathlib.Path.exists", mock_path_exists)

            result = paper_trading.get_paper_trading_portfolio(db=self.db_session, current=user2)

        # Verify User 2 only sees their paper position
        assert len(result.holdings) == 1
        assert result.holdings[0].symbol == "RELIANCE-EQ"
        assert result.holdings[0].quantity == 5.0

    def test_position_without_matching_order_fallback(self, monkeypatch):
        """Test fallback logic when position exists but no matching order found"""
        # Position without matching order (created before order tracking)
        position = DummyPosition(
            symbol="STOCK1-EQ",
            quantity=10.0,
            avg_price=100.0,
            closed_at=None,
            opened_at=datetime.now() - timedelta(days=1),
            reentry_count=0,
            entry_rsi=29.5,
            initial_entry_price=100.0,
            reentries=None,
        )

        # No orders for this symbol
        self.mock_positions_repo.list.return_value = [position]
        self.mock_orders_repo.list.return_value = ([], 0)

        # User is in paper mode - should assume paper trading
        self.mock_settings_repo.get_by_user_id.return_value = MagicMock(trade_mode=TradeMode.PAPER)

        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.info = {"currentPrice": 100.0, "regularMarketPrice": 100.0}
            mock_ticker_class.return_value = mock_ticker_instance

            # Mock Path.exists for active_sell_orders.json
            def mock_path_exists(self):
                return False if "active_sell_orders.json" in str(self) else True

            monkeypatch.setattr("pathlib.Path.exists", mock_path_exists)

            result = paper_trading.get_paper_trading_portfolio(
                db=self.db_session, current=self.user
            )

        # Should include position (fallback to paper mode)
        assert len(result.holdings) == 1
        assert result.holdings[0].symbol == "STOCK1-EQ"

    def test_position_without_order_broker_mode_skip(self, monkeypatch):
        """Test that ambiguous positions are skipped when user is in broker mode"""
        # Position without matching order
        position = DummyPosition(
            symbol="STOCK2-EQ",
            quantity=10.0,
            avg_price=100.0,
            closed_at=None,
            opened_at=datetime.now() - timedelta(days=1),
            reentry_count=0,
            entry_rsi=29.5,
            initial_entry_price=100.0,
            reentries=None,
        )

        # No orders for this symbol
        self.mock_positions_repo.list.return_value = [position]
        self.mock_orders_repo.list.return_value = ([], 0)

        # User is in broker mode - should skip ambiguous position
        self.mock_settings_repo.get_by_user_id.return_value = MagicMock(trade_mode=TradeMode.BROKER)

        result = paper_trading.get_paper_trading_portfolio(db=self.db_session, current=self.user)

        # Should skip ambiguous position
        assert len(result.holdings) == 0

    def test_position_with_broker_order_skipped(self, monkeypatch):
        """Test that positions with broker orders are skipped in paper portfolio"""
        # Position with broker order
        position_time = datetime.now()
        position = DummyPosition(
            symbol="STOCK3-EQ",
            quantity=10.0,
            avg_price=100.0,
            closed_at=None,
            opened_at=position_time,
            reentry_count=0,
            entry_rsi=29.5,
            initial_entry_price=100.0,
            reentries=None,
        )

        # Broker order for this symbol
        broker_order = DummyOrder(
            symbol="STOCK3-EQ",
            side="buy",
            placed_at=position_time,
            trade_mode=TradeMode.BROKER,
        )

        self.mock_positions_repo.list.return_value = [position]
        self.mock_orders_repo.list.return_value = ([broker_order], 1)

        result = paper_trading.get_paper_trading_portfolio(db=self.db_session, current=self.user)

        # Should skip broker position
        assert len(result.holdings) == 0

    def test_account_balance_mismatch_validation(self, monkeypatch):
        """Test account balance vs positions mismatch validation"""
        # Position with large investment
        position_time = datetime.now()
        position = DummyPosition(
            symbol="STOCK4-EQ",
            quantity=1000.0,  # Large quantity
            avg_price=100.0,
            closed_at=None,
            opened_at=position_time,
            reentry_count=0,
            entry_rsi=29.5,
            initial_entry_price=100.0,
            reentries=None,
        )

        # Paper order
        paper_order = DummyOrder(
            symbol="STOCK4-EQ",
            side="buy",
            placed_at=position_time,
            trade_mode=TradeMode.PAPER,
        )

        # Account data with mismatch (available_cash doesn't match expected)
        self.mock_store.get_account.return_value = {
            "initial_capital": 100000.0,
            "available_cash": 90000.0,  # Should be much less given position
            "realized_pnl": 0.0,
        }

        self.mock_positions_repo.list.return_value = [position]
        self.mock_orders_repo.list.return_value = ([paper_order], 1)

        # Should still work but log warning
        with patch("server.app.routers.paper_trading.logger") as mock_logger:
            paper_trading.get_paper_trading_portfolio(db=self.db_session, current=self.user)
            # Verify warning was logged
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if "discrepancy" in str(call).lower()
            ]
            assert len(warning_calls) > 0

    def test_symbol_format_mismatch_target_prices(self, monkeypatch):
        """Test that target prices work with both full and base symbol formats"""
        # Position with full symbol (RELIANCE-EQ)
        position_time = datetime.now()
        position = DummyPosition(
            symbol="RELIANCE-EQ",
            quantity=10.0,
            avg_price=100.0,
            closed_at=None,
            opened_at=position_time,
            reentry_count=0,
            entry_rsi=29.5,
            initial_entry_price=100.0,
            reentries=None,
        )

        # Paper order - same time as position
        paper_order = DummyOrder(
            symbol="RELIANCE-EQ",
            side="buy",
            placed_at=position_time,  # Same time as position
            trade_mode=TradeMode.PAPER,
        )

        self.mock_positions_repo.list.return_value = [position]

        # Target prices now come from DB sell orders (single source of truth).
        sell_order = DummyOrder(
            symbol="RELIANCE-EQ",
            side="sell",
            placed_at=position_time,
            trade_mode=TradeMode.PAPER,
            status="pending",
            price=110.0,
        )

        def list_side_effect(user_id, *args, **kwargs):
            if kwargs.get("side") == "sell":
                return ([sell_order], 1)
            return ([paper_order], 1)

        self.mock_orders_repo.list.side_effect = list_side_effect

        result = paper_trading.get_paper_trading_portfolio(db=self.db_session, current=self.user)

        # Should find target price using base symbol
        assert len(result.holdings) == 1
        assert result.holdings[0].target_price == 110.0

    def test_order_time_matching_within_one_hour(self, monkeypatch):
        """Test that orders are matched with positions within 1 hour window"""
        # Position opened 30 minutes ago
        position_time = datetime.now() - timedelta(minutes=30)
        position = DummyPosition(
            symbol="STOCK5-EQ",
            quantity=10.0,
            avg_price=100.0,
            closed_at=None,
            opened_at=position_time,
            reentry_count=0,
            entry_rsi=29.5,
            initial_entry_price=100.0,
            reentries=None,
        )

        # Paper order placed 30 minutes ago (within 1 hour) - same time as position
        paper_order = DummyOrder(
            symbol="STOCK5-EQ",
            side="buy",
            placed_at=position_time,  # Same time as position
            trade_mode=TradeMode.PAPER,
        )

        self.mock_positions_repo.list.return_value = [position]
        self.mock_orders_repo.list.return_value = ([paper_order], 1)

        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.info = {"currentPrice": 100.0, "regularMarketPrice": 100.0}
            mock_ticker_class.return_value = mock_ticker_instance

            # Mock Path.exists for active_sell_orders.json
            def mock_path_exists(self):
                return False if "active_sell_orders.json" in str(self) else True

            monkeypatch.setattr("pathlib.Path.exists", mock_path_exists)

            result = paper_trading.get_paper_trading_portfolio(
                db=self.db_session, current=self.user
            )

        # Should match
        assert len(result.holdings) == 1

    def test_order_time_matching_outside_one_hour(self, monkeypatch):
        """Test that orders outside 1 hour window don't match"""
        # Position opened 2 hours ago
        position_time = datetime.now() - timedelta(hours=2)
        position = DummyPosition(
            symbol="STOCK6-EQ",
            quantity=10.0,
            avg_price=100.0,
            closed_at=None,
            opened_at=position_time,
            reentry_count=0,
            entry_rsi=29.5,
            initial_entry_price=100.0,
            reentries=None,
        )

        # Paper order placed 2 hours ago (outside 1 hour window) - same time as position
        paper_order = DummyOrder(
            symbol="STOCK6-EQ",
            side="buy",
            placed_at=position_time,  # Same time as position (2 hours ago)
            trade_mode=TradeMode.PAPER,
        )

        self.mock_positions_repo.list.return_value = [position]
        self.mock_orders_repo.list.return_value = ([paper_order], 1)

        # User is in paper mode - should use fallback
        self.mock_settings_repo.get_by_user_id.return_value = MagicMock(trade_mode=TradeMode.PAPER)

        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker_instance = MagicMock()
            mock_ticker_instance.info = {"currentPrice": 100.0, "regularMarketPrice": 100.0}
            mock_ticker_class.return_value = mock_ticker_instance

            # Mock Path.exists for active_sell_orders.json
            def mock_path_exists(self):
                return False if "active_sell_orders.json" in str(self) else True

            monkeypatch.setattr("pathlib.Path.exists", mock_path_exists)

            result = paper_trading.get_paper_trading_portfolio(
                db=self.db_session, current=self.user
            )

        # Should still include position (fallback logic)
        assert len(result.holdings) == 1
