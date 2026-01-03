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
from unittest.mock import MagicMock, patch

import pytest

from server.app.routers import paper_trading
from src.infrastructure.db.models import TradeMode


class DummyUser:
    def __init__(self, id: int):
        self.id = id


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

        # Mock yfinance
        self.mock_ticker = MagicMock()
        self.mock_ticker.info = {"currentPrice": 100.0}
        monkeypatch.setattr("yfinance.Ticker", lambda symbol: self.mock_ticker)

        # Mock PositionsRepository
        self.mock_positions_repo = MagicMock()
        monkeypatch.setattr(
            "server.app.routers.paper_trading.PositionsRepository",
            lambda db: self.mock_positions_repo,
        )

        # Mock OrdersRepository
        self.mock_orders_repo = MagicMock()
        monkeypatch.setattr(
            "server.app.routers.paper_trading.OrdersRepository",
            lambda db: self.mock_orders_repo,
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

        # User 1 has broker position for RELIANCE-EQ
        user1_position = MagicMock()
        user1_position.symbol = "RELIANCE-EQ"
        user1_position.quantity = 10
        user1_position.avg_price = 100.0
        user1_position.closed_at = None
        user1_position.opened_at = datetime.now()
        user1_position.reentry_count = 0
        user1_position.entry_rsi = 29.5
        user1_position.initial_entry_price = 100.0
        user1_position.reentries = None

        # User 2 has paper position for RELIANCE-EQ
        user2_position = MagicMock()
        user2_position.symbol = "RELIANCE-EQ"
        user2_position.quantity = 5
        user2_position.avg_price = 100.0
        user2_position.closed_at = None
        user2_position.opened_at = datetime.now()
        user2_position.reentry_count = 0
        user2_position.entry_rsi = 29.5
        user2_position.initial_entry_price = 100.0
        user2_position.reentries = None

        # User 1's broker order
        user1_order = MagicMock()
        user1_order.symbol = "RELIANCE-EQ"
        user1_order.side = "buy"
        user1_order.placed_at = datetime.now()
        user1_order.trade_mode = TradeMode.BROKER

        # User 2's paper order
        user2_order = MagicMock()
        user2_order.symbol = "RELIANCE-EQ"
        user2_order.side = "buy"
        user2_order.placed_at = datetime.now()
        user2_order.trade_mode = TradeMode.PAPER

        # Mock repositories
        self.mock_positions_repo.list.return_value = [user2_position]
        self.mock_orders_repo.list.return_value = [user2_order]

        # Call endpoint for User 2
        user2 = DummyUser(id=user2_id)
        result = paper_trading.get_paper_trading_portfolio(db=self.db_session, current=user2)

        # Verify User 2 only sees their paper position
        assert len(result.holdings) == 1
        assert result.holdings[0].symbol == "RELIANCE-EQ"
        assert result.holdings[0].quantity == 5

    def test_position_without_matching_order_fallback(self, monkeypatch):
        """Test fallback logic when position exists but no matching order found"""
        # Position without matching order (created before order tracking)
        position = MagicMock()
        position.symbol = "STOCK1-EQ"
        position.quantity = 10
        position.avg_price = 100.0
        position.closed_at = None
        position.opened_at = datetime.now() - timedelta(days=1)
        position.reentry_count = 0
        position.entry_rsi = 29.5
        position.initial_entry_price = 100.0
        position.reentries = None

        # No orders for this symbol
        self.mock_positions_repo.list.return_value = [position]
        self.mock_orders_repo.list.return_value = []

        # User is in paper mode - should assume paper trading
        self.mock_settings_repo.get_by_user_id.return_value = MagicMock(trade_mode=TradeMode.PAPER)

        result = paper_trading.get_paper_trading_portfolio(db=self.db_session, current=self.user)

        # Should include position (fallback to paper mode)
        assert len(result.holdings) == 1
        assert result.holdings[0].symbol == "STOCK1-EQ"

    def test_position_without_order_broker_mode_skip(self, monkeypatch):
        """Test that ambiguous positions are skipped when user is in broker mode"""
        # Position without matching order
        position = MagicMock()
        position.symbol = "STOCK2-EQ"
        position.quantity = 10
        position.avg_price = 100.0
        position.closed_at = None
        position.opened_at = datetime.now() - timedelta(days=1)
        position.reentry_count = 0
        position.entry_rsi = 29.5
        position.initial_entry_price = 100.0
        position.reentries = None

        # No orders for this symbol
        self.mock_positions_repo.list.return_value = [position]
        self.mock_orders_repo.list.return_value = []

        # User is in broker mode - should skip ambiguous position
        self.mock_settings_repo.get_by_user_id.return_value = MagicMock(trade_mode=TradeMode.BROKER)

        result = paper_trading.get_paper_trading_portfolio(db=self.db_session, current=self.user)

        # Should skip ambiguous position
        assert len(result.holdings) == 0

    def test_position_with_broker_order_skipped(self, monkeypatch):
        """Test that positions with broker orders are skipped in paper portfolio"""
        # Position with broker order
        position = MagicMock()
        position.symbol = "STOCK3-EQ"
        position.quantity = 10
        position.avg_price = 100.0
        position.closed_at = None
        position.opened_at = datetime.now()
        position.reentry_count = 0
        position.entry_rsi = 29.5
        position.initial_entry_price = 100.0
        position.reentries = None

        # Broker order for this symbol
        broker_order = MagicMock()
        broker_order.symbol = "STOCK3-EQ"
        broker_order.side = "buy"
        broker_order.placed_at = datetime.now()
        broker_order.trade_mode = TradeMode.BROKER

        self.mock_positions_repo.list.return_value = [position]
        self.mock_orders_repo.list.return_value = [broker_order]

        result = paper_trading.get_paper_trading_portfolio(db=self.db_session, current=self.user)

        # Should skip broker position
        assert len(result.holdings) == 0

    def test_account_balance_mismatch_validation(self, monkeypatch):
        """Test account balance vs positions mismatch validation"""
        # Position with large investment
        position = MagicMock()
        position.symbol = "STOCK4-EQ"
        position.quantity = 1000  # Large quantity
        position.avg_price = 100.0
        position.closed_at = None
        position.opened_at = datetime.now()
        position.reentry_count = 0
        position.entry_rsi = 29.5
        position.initial_entry_price = 100.0
        position.reentries = None

        # Paper order
        paper_order = MagicMock()
        paper_order.symbol = "STOCK4-EQ"
        paper_order.side = "buy"
        paper_order.placed_at = datetime.now()
        paper_order.trade_mode = TradeMode.PAPER

        # Account data with mismatch (available_cash doesn't match expected)
        self.mock_store.get_account.return_value = {
            "initial_capital": 100000.0,
            "available_cash": 90000.0,  # Should be much less given position
            "realized_pnl": 0.0,
        }

        self.mock_positions_repo.list.return_value = [position]
        self.mock_orders_repo.list.return_value = [paper_order]

        # Should still work but log warning
        with patch("server.app.routers.paper_trading.logger") as mock_logger:
            paper_trading.get_paper_trading_portfolio(
                db=self.db_session, current=self.user
            )
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
        position = MagicMock()
        position.symbol = "RELIANCE-EQ"
        position.quantity = 10
        position.avg_price = 100.0
        position.closed_at = None
        position.opened_at = datetime.now()
        position.reentry_count = 0
        position.entry_rsi = 29.5
        position.initial_entry_price = 100.0
        position.reentries = None

        # Paper order
        paper_order = MagicMock()
        paper_order.symbol = "RELIANCE-EQ"
        paper_order.side = "buy"
        paper_order.placed_at = datetime.now()
        paper_order.trade_mode = TradeMode.PAPER

        self.mock_positions_repo.list.return_value = [position]
        self.mock_orders_repo.list.return_value = [paper_order]

        # Mock target prices with base symbol (RELIANCE)
        import json

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "builtins.open",
                create=True,
            ) as mock_open,
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
                {"RELIANCE": {"target_price": 110.0}}
            )
            result = paper_trading.get_paper_trading_portfolio(
                db=self.db_session, current=self.user
            )

            # Should find target price using base symbol
            assert len(result.holdings) == 1
            assert result.holdings[0].target_price == 110.0

    def test_order_time_matching_within_one_hour(self, monkeypatch):
        """Test that orders are matched with positions within 1 hour window"""
        # Position opened 30 minutes ago
        position = MagicMock()
        position.symbol = "STOCK5-EQ"
        position.quantity = 10
        position.avg_price = 100.0
        position.closed_at = None
        position.opened_at = datetime.now() - timedelta(minutes=30)
        position.reentry_count = 0
        position.entry_rsi = 29.5
        position.initial_entry_price = 100.0
        position.reentries = None

        # Paper order placed 30 minutes ago (within 1 hour)
        paper_order = MagicMock()
        paper_order.symbol = "STOCK5-EQ"
        paper_order.side = "buy"
        paper_order.placed_at = datetime.now() - timedelta(minutes=30)
        paper_order.trade_mode = TradeMode.PAPER

        self.mock_positions_repo.list.return_value = [position]
        self.mock_orders_repo.list.return_value = [paper_order]

        result = paper_trading.get_paper_trading_portfolio(db=self.db_session, current=self.user)

        # Should match
        assert len(result.holdings) == 1

    def test_order_time_matching_outside_one_hour(self, monkeypatch):
        """Test that orders outside 1 hour window don't match"""
        # Position opened 2 hours ago
        position = MagicMock()
        position.symbol = "STOCK6-EQ"
        position.quantity = 10
        position.avg_price = 100.0
        position.closed_at = None
        position.opened_at = datetime.now() - timedelta(hours=2)
        position.reentry_count = 0
        position.entry_rsi = 29.5
        position.initial_entry_price = 100.0
        position.reentries = None

        # Paper order placed 2 hours ago (outside 1 hour window)
        paper_order = MagicMock()
        paper_order.symbol = "STOCK6-EQ"
        paper_order.side = "buy"
        paper_order.placed_at = datetime.now() - timedelta(hours=2)
        paper_order.trade_mode = TradeMode.PAPER

        self.mock_positions_repo.list.return_value = [position]
        self.mock_orders_repo.list.return_value = [paper_order]

        # User is in paper mode - should use fallback
        self.mock_settings_repo.get_by_user_id.return_value = MagicMock(trade_mode=TradeMode.PAPER)

        result = paper_trading.get_paper_trading_portfolio(db=self.db_session, current=self.user)

        # Should still include position (fallback logic)
        assert len(result.holdings) == 1
