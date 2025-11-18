"""
Tests for Paper Trading Service Adapter

Tests that paper trading mode works correctly for individual services.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.application.services.paper_trading_service_adapter import (
    PaperTradingEngineAdapter,
    PaperTradingServiceAdapter,
)
from src.infrastructure.db.models import Users


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = Users(
        email="paper_test@example.com",
        password_hash="test_hash",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_paper_broker():
    """Mock paper trading broker"""
    broker = MagicMock()
    broker.is_connected.return_value = True
    broker.get_holdings.return_value = []
    broker.get_available_balance.return_value = MagicMock(amount=100000.0)
    broker.place_order.return_value = "PAPER_ORDER_123"
    return broker


class TestPaperTradingServiceAdapter:
    """Test PaperTradingServiceAdapter"""

    def test_initialize_success(self, db_session, test_user):
        """Test successful initialization"""
        with patch(
            "src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter"
        ) as mock_broker_class, patch(
            "src.application.services.paper_trading_service_adapter.PaperTradingConfig"
        ) as mock_config_class:
            mock_broker = MagicMock()
            mock_broker.connect.return_value = True
            mock_broker.get_holdings.return_value = []
            mock_broker.get_available_balance.return_value = MagicMock(amount=100000.0)
            mock_broker_class.return_value = mock_broker

            adapter = PaperTradingServiceAdapter(
                user_id=test_user.id,
                db_session=db_session,
                initial_capital=100000.0,
            )

            result = adapter.initialize()

            assert result is True
            assert adapter.broker is not None
            assert adapter.config is not None

    def test_initialize_failure(self, db_session, test_user):
        """Test initialization failure when broker connection fails"""
        with patch(
            "src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter"
        ) as mock_broker_class, patch(
            "src.application.services.paper_trading_service_adapter.PaperTradingConfig"
        ) as mock_config_class:
            mock_broker = MagicMock()
            mock_broker.connect.return_value = False
            mock_broker_class.return_value = mock_broker

            adapter = PaperTradingServiceAdapter(
                user_id=test_user.id,
                db_session=db_session,
            )

            result = adapter.initialize()

            assert result is False

    def test_run_buy_orders_no_recommendations(self, db_session, test_user, mock_paper_broker):
        """Test buy orders with no recommendations"""
        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
        )
        adapter.broker = mock_paper_broker
        adapter.engine = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=adapter.logger,
        )

        with patch.object(adapter.engine, "load_latest_recommendations", return_value=[]):
            adapter.run_buy_orders()

        assert adapter.tasks_completed["buy_orders"] is True

    def test_run_buy_orders_with_recommendations(self, db_session, test_user, mock_paper_broker):
        """Test buy orders with recommendations"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_paper_broker
        # Mock broker config with max_position_size
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 100000.0

        adapter.engine = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=adapter.logger,
        )

        recommendations = [
            Recommendation(ticker="RELIANCE.NS", verdict="buy", last_close=2500.0),
            Recommendation(ticker="TCS.NS", verdict="strong_buy", last_close=3500.0),
        ]

        with patch.object(adapter.engine, "load_latest_recommendations", return_value=recommendations):
            adapter.run_buy_orders()

        assert adapter.tasks_completed["buy_orders"] is True
        # Verify orders were placed
        assert mock_paper_broker.place_order.call_count == 2


class TestPaperTradingEngineAdapter:
    """Test PaperTradingEngineAdapter"""

    def test_load_latest_recommendations_from_db(self, db_session, test_user, mock_paper_broker):
        """Test loading recommendations from database (Signals table)"""
        from src.infrastructure.db.models import Signals
        from src.infrastructure.db.timezone_utils import ist_now

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create test signals in database
        signal1 = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="TCS",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=3500.0,
            ts=ist_now(),
        )
        signal3 = Signals(
            symbol="WATCH",
            verdict="watch",
            final_verdict="watch",
            last_close=100.0,
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2, signal3])
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should only return buy/strong_buy signals
        assert len(recs) == 2
        tickers = {r.ticker for r in recs}
        assert "RELIANCE.NS" in tickers or "RELIANCE" in tickers
        assert "TCS.NS" in tickers or "TCS" in tickers

    def test_place_new_entries(self, db_session, test_user, mock_paper_broker):
        """Test placing new entries"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )

        # Mock broker config with max_position_size
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 100000.0

        recommendations = [
            Recommendation(
                ticker="RELIANCE.NS", verdict="buy", last_close=2500.0, execution_capital=100000.0
            )
        ]

        summary = adapter.place_new_entries(recommendations)

        assert summary["attempted"] == 1
        assert summary["placed"] == 1
        assert mock_paper_broker.place_order.called

    def test_place_new_entries_respects_max_position_size(self, db_session, test_user, mock_paper_broker):
        """Test that orders respect max_position_size limit"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )

        # Mock broker config with lower max_position_size
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 50000.0

        # Recommendation with execution_capital > max_position_size
        recommendations = [
            Recommendation(
                ticker="RELIANCE.NS", verdict="buy", last_close=2500.0, execution_capital=100000.0
            )
        ]

        summary = adapter.place_new_entries(recommendations)

        assert summary["attempted"] == 1
        # Order should be placed but with adjusted quantity
        assert summary["placed"] == 1
        assert mock_paper_broker.place_order.called

        # Verify order quantity was adjusted (should be ~20 shares for 50000/2500)
        call_args = mock_paper_broker.place_order.call_args
        order = call_args[0][0]
        assert order.quantity <= 20  # Should be limited by max_position_size

    def test_place_new_entries_duplicate(self, db_session, test_user, mock_paper_broker):
        """Test placing entries with duplicate in portfolio"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from modules.kotak_neo_auto_trader.domain import Holding
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        # Mock holding
        mock_holding = MagicMock()
        mock_holding.symbol = "RELIANCE"
        mock_paper_broker.get_holdings.return_value = [mock_holding]
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 100000.0

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )

        recommendations = [
            Recommendation(
                ticker="RELIANCE.NS", verdict="buy", last_close=2500.0, execution_capital=100000.0
            )
        ]

        summary = adapter.place_new_entries(recommendations)

        assert summary["attempted"] == 1
        assert summary["placed"] == 0
        assert summary["skipped_duplicates"] == 1
        assert not mock_paper_broker.place_order.called

    def test_place_new_entries_portfolio_limit(self, db_session, test_user, mock_paper_broker):
        """Test placing entries when portfolio limit is reached"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        # Mock 6 holdings (portfolio limit)
        mock_holdings = [MagicMock() for _ in range(6)]
        mock_paper_broker.get_holdings.return_value = mock_holdings
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 100000.0

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )

        recommendations = [
            Recommendation(
                ticker="RELIANCE.NS", verdict="buy", last_close=2500.0, execution_capital=100000.0
            )
        ]

        summary = adapter.place_new_entries(recommendations)

        assert summary["skipped_portfolio_limit"] == 1
        assert not mock_paper_broker.place_order.called

    def test_initialize_sets_max_position_size_from_strategy_config(self, db_session, test_user):
        """Test that initialization sets max_position_size from strategy_config.user_capital"""
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        with patch(
            "src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter"
        ) as mock_broker_class, patch(
            "src.application.services.paper_trading_service_adapter.PaperTradingConfig"
        ) as mock_config_class:
            mock_broker = MagicMock()
            mock_broker.connect.return_value = True
            mock_broker.get_holdings.return_value = []
            mock_broker.get_available_balance.return_value = MagicMock(amount=100000.0)
            mock_broker_class.return_value = mock_broker

            mock_config = MagicMock()
            mock_config_class.return_value = mock_config

            adapter = PaperTradingServiceAdapter(
                user_id=test_user.id,
                db_session=db_session,
                strategy_config=strategy_config,
                initial_capital=100000.0,
            )

            result = adapter.initialize()

            assert result is True
            # Verify PaperTradingConfig was called with max_position_size from strategy_config
            mock_config_class.assert_called_once()
            call_kwargs = mock_config_class.call_args[1]
            assert call_kwargs["max_position_size"] == 100000.0

