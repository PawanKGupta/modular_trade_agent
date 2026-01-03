"""
Integration tests for paper trading portfolio with multiple users

Tests real database scenarios:
- Multiple users trading same symbol
- Positions isolation by user_id
- Trade mode filtering accuracy
"""

import pytest
from sqlalchemy.orm import Session

from server.app.routers import paper_trading
from src.infrastructure.db.models import Orders, OrderStatus, Positions, TradeMode, Users
from src.infrastructure.db.timezone_utils import ist_now


class TestPaperTradingPortfolioMultiUser:
    """Integration tests for multi-user paper trading portfolio"""

    @pytest.fixture
    def user1(self, db_session: Session):
        """Create User 1 in paper mode"""
        user = Users(
            email="user1_paper@test.com",
            name="User 1 Paper",
            password_hash="hash1",
            role="user",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    @pytest.fixture
    def user2(self, db_session: Session):
        """Create User 2 in broker mode"""
        user = Users(
            email="user2_broker@test.com",
            name="User 2 Broker",
            password_hash="hash2",
            role="user",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    @pytest.fixture
    def user1_paper_position(self, db_session: Session, user1):
        """Create paper position for User 1"""
        position = Positions(
            user_id=user1.id,
            symbol="RELIANCE-EQ",
            quantity=10.0,
            avg_price=100.0,
            unrealized_pnl=0.0,
            opened_at=ist_now(),
            closed_at=None,
            reentry_count=0,
            entry_rsi=29.5,
            initial_entry_price=100.0,
        )
        db_session.add(position)
        db_session.commit()
        db_session.refresh(position)
        return position

    @pytest.fixture
    def user2_broker_position(self, db_session: Session, user2):
        """Create broker position for User 2"""
        position = Positions(
            user_id=user2.id,
            symbol="RELIANCE-EQ",
            quantity=20.0,
            avg_price=100.0,
            unrealized_pnl=0.0,
            opened_at=ist_now(),
            closed_at=None,
            reentry_count=0,
            entry_rsi=29.5,
            initial_entry_price=100.0,
        )
        db_session.add(position)
        db_session.commit()
        db_session.refresh(position)
        return position

    @pytest.fixture
    def user1_paper_order(self, db_session: Session, user1, user1_paper_position):
        """Create paper order for User 1"""
        order = Orders(
            user_id=user1.id,
            symbol="RELIANCE-EQ",
            side="buy",
            quantity=10.0,
            price=100.0,
            status=OrderStatus.CLOSED,
            placed_at=user1_paper_position.opened_at,
            trade_mode=TradeMode.PAPER,
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        return order

    @pytest.fixture
    def user2_broker_order(self, db_session: Session, user2, user2_broker_position):
        """Create broker order for User 2"""
        order = Orders(
            user_id=user2.id,
            symbol="RELIANCE-EQ",
            side="buy",
            quantity=20.0,
            price=100.0,
            status=OrderStatus.CLOSED,
            placed_at=user2_broker_position.opened_at,
            trade_mode=TradeMode.BROKER,
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        return order

    def test_user1_sees_only_paper_position(  # noqa: PLR0913
        self,
        db_session: Session,
        user1,
        user1_paper_position,
        user1_paper_order,
        user2_broker_position,
        user2_broker_order,
        monkeypatch,
    ):
        """Test that User 1 only sees their paper position, not User 2's broker position"""
        # Mock PaperTradeStore
        mock_store = pytest.Mock()
        mock_store.get_account.return_value = {
            "initial_capital": 100000.0,
            "available_cash": 90000.0,
            "realized_pnl": 0.0,
        }
        mock_store.get_all_orders.return_value = []
        monkeypatch.setattr(
            "server.app.routers.paper_trading.PaperTradeStore",
            lambda path, **kwargs: mock_store,
        )

        # Mock PaperTradeReporter
        mock_reporter = pytest.Mock()
        mock_reporter.order_statistics.return_value = {
            "total_orders": 1,
            "buy_orders": 1,
            "sell_orders": 0,
            "completed_orders": 1,
            "pending_orders": 0,
            "cancelled_orders": 0,
            "rejected_orders": 0,
        }
        monkeypatch.setattr(
            "server.app.routers.paper_trading.PaperTradeReporter",
            lambda store: mock_reporter,
        )

        # Mock Path.exists
        monkeypatch.setattr("pathlib.Path.exists", lambda self: True)

        # Mock yfinance
        mock_ticker = pytest.Mock()
        mock_ticker.info = {"currentPrice": 100.0}
        monkeypatch.setattr("yfinance.Ticker", lambda symbol: mock_ticker)

        # Mock SettingsRepository
        mock_settings_repo = pytest.Mock()
        mock_settings_repo.get_by_user_id.return_value = pytest.Mock(trade_mode=TradeMode.PAPER)
        monkeypatch.setattr(
            "server.app.routers.paper_trading.SettingsRepository",
            lambda db: mock_settings_repo,
        )

        # Call endpoint for User 1
        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user1)

        # Verify User 1 only sees their paper position
        assert len(result.holdings) == 1
        assert result.holdings[0].symbol == "RELIANCE-EQ"
        assert result.holdings[0].quantity == 10.0

    def test_user2_broker_position_not_in_paper_portfolio(  # noqa: PLR0913
        self,
        db_session: Session,
        user2,
        user1_paper_position,
        user1_paper_order,
        user2_broker_position,
        user2_broker_order,
        monkeypatch,
    ):
        """Test that User 2's broker position doesn't appear in paper portfolio"""
        # Mock PaperTradeStore
        mock_store = pytest.Mock()
        mock_store.get_account.return_value = {
            "initial_capital": 100000.0,
            "available_cash": 80000.0,
            "realized_pnl": 0.0,
        }
        mock_store.get_all_orders.return_value = []
        monkeypatch.setattr(
            "server.app.routers.paper_trading.PaperTradeStore",
            lambda path, **kwargs: mock_store,
        )

        # Mock PaperTradeReporter
        mock_reporter = pytest.Mock()
        mock_reporter.order_statistics.return_value = {
            "total_orders": 0,
            "buy_orders": 0,
            "sell_orders": 0,
            "completed_orders": 0,
            "pending_orders": 0,
            "cancelled_orders": 0,
            "rejected_orders": 0,
        }
        monkeypatch.setattr(
            "server.app.routers.paper_trading.PaperTradeReporter",
            lambda store: mock_reporter,
        )

        # Mock Path.exists
        monkeypatch.setattr("pathlib.Path.exists", lambda self: True)

        # Mock yfinance
        mock_ticker = pytest.Mock()
        mock_ticker.info = {"currentPrice": 100.0}
        monkeypatch.setattr("yfinance.Ticker", lambda symbol: mock_ticker)

        # Mock SettingsRepository (User 2 is in broker mode)
        mock_settings_repo = pytest.Mock()
        mock_settings_repo.get_by_user_id.return_value = pytest.Mock(trade_mode=TradeMode.BROKER)
        monkeypatch.setattr(
            "server.app.routers.paper_trading.SettingsRepository",
            lambda db: mock_settings_repo,
        )

        # Call endpoint for User 2 (should return empty or error)
        # Since User 2 is in broker mode, paper portfolio should be empty
        result = paper_trading.get_paper_trading_portfolio(db=db_session, current=user2)

        # User 2's broker position should not appear
        # (broker positions are filtered out)
        broker_positions = [
            h for h in result.holdings if h.symbol == "RELIANCE-EQ" and h.quantity == 20.0
        ]
        assert len(broker_positions) == 0
