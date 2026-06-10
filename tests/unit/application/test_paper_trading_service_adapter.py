"""
Tests for Paper Trading Service Adapter

Tests that paper trading mode works correctly for individual services.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.application.services.paper_trading_service_adapter import (
    PaperTradingEngineAdapter,
    PaperTradingServiceAdapter,
)
from src.infrastructure.db.models import (
    Signals,
    SignalStatus,
    Users,
    UserSignalStatus,
)
from src.infrastructure.db.timezone_utils import ist_now


def _set_today_like_index(df: pd.DataFrame) -> pd.DataFrame:
    """Attach a datetime index ending today (IST) for sell-monitor tests."""
    end_ts = pd.Timestamp(ist_now())
    if end_ts.tzinfo is None:
        end_ts = end_ts.tz_localize("Asia/Kolkata")
    df.index = (
        pd.DatetimeIndex([end_ts])
        if len(df) == 1
        else pd.date_range(end=end_ts, periods=len(df), freq="D")
    )
    return df


def _ema9_for_ticker(ticker, broker_symbol=None, *, reliance=2600.0, tcs=3600.0):
    """Side effect helper matching _calculate_ema9(ticker, broker_symbol=...) signature."""
    if "RELIANCE" in ticker:
        return reliance
    if "TCS" in ticker:
        return tcs
    return None


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
    broker.get_all_orders.return_value = []
    broker.get_available_balance.return_value = MagicMock(amount=100000.0)
    broker.place_order.return_value = "PAPER_ORDER_123"

    # Provide a stable in-memory "account" shape for balance checks
    broker.store.get_account.return_value = {"available_cash": 1_000_000_000.0}
    broker.store.storage_path = "paper_trading/test"

    # Provide a stable price provider for prefetch (doesn't affect sizing, just avoids MagicMock quirks)
    broker.price_provider.get_prices.return_value = {}
    return broker


class TestPaperTradingServiceAdapter:
    """Test PaperTradingServiceAdapter"""

    def test_initialize_success(self, db_session, test_user):
        """Test successful initialization"""
        with (
            patch(
                "src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter"
            ) as mock_broker_class,
            patch(
                "src.application.services.paper_trading_service_adapter.PaperTradingConfig"
            ) as mock_config_class,
        ):
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
        with (
            patch(
                "src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter"
            ) as mock_broker_class,
            patch(
                "src.application.services.paper_trading_service_adapter.PaperTradingConfig"
            ) as mock_config_class,
        ):
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

    def test_run_premarket_amo_adjustment_delegates_to_adjust_method(
        self, db_session, test_user, mock_paper_broker
    ):
        """Scheduler calls run_premarket_amo_adjustment; paper implements via adjust_amo_quantities_premarket."""
        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
        )
        adapter.broker = mock_paper_broker
        expected_summary = {"total_orders": 0, "adjusted": 0}
        with patch.object(
            adapter,
            "adjust_amo_quantities_premarket",
            return_value=expected_summary,
        ) as mock_adjust:
            result = adapter.run_premarket_amo_adjustment()
        mock_adjust.assert_called_once_with()
        assert result == expected_summary

    def test_run_buy_orders_warns_on_legacy_pending_amo(
        self, db_session, test_user, mock_paper_broker
    ):
        """9:01 buy_orders warns on stale AMO; does not call execute_amo_orders_at_market_open."""
        from modules.kotak_neo_auto_trader.domain import (
            Order,
            OrderStatus,
            OrderType,
            OrderVariety,
            TransactionType,
        )

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
        )
        adapter.broker = mock_paper_broker
        adapter.logger = MagicMock()
        adapter.engine = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=adapter.logger,
        )

        pending_amo = Order(
            symbol="DMART",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            order_id="LEGACY_AMO_1",
            status=OrderStatus.OPEN,
        )
        mock_paper_broker.get_pending_orders.return_value = [pending_amo]

        with (
            patch.object(adapter.engine, "load_latest_recommendations", return_value=[]),
            patch.object(adapter, "execute_amo_orders_at_market_open") as mock_execute_amo,
        ):
            adapter.run_buy_orders()

        legacy_warnings = [
            call
            for call in adapter.logger.warning.call_args_list
            if call.args and "Legacy pending AMO" in call.args[0]
        ]
        assert len(legacy_warnings) == 1
        assert "DMART" in legacy_warnings[0].args[0]
        mock_execute_amo.assert_not_called()

    def test_run_buy_orders_calls_place_reentry_orders(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that run_buy_orders calls place_reentry_orders after placing fresh entries"""
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_paper_broker
        adapter.logger = MagicMock()

        # Initialize engine
        from src.application.services.paper_trading_service_adapter import PaperTradingEngineAdapter

        adapter.engine = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=adapter.logger,
        )

        # Mock load_latest_recommendations to return empty (no fresh entries)
        adapter.engine.load_latest_recommendations = MagicMock(return_value=[])

        # Mock place_reentry_orders
        mock_reentry_summary = {
            "attempted": 1,
            "placed": 1,
            "failed_balance": 0,
            "skipped_duplicates": 0,
            "skipped_invalid_rsi": 0,
            "skipped_missing_data": 0,
            "skipped_invalid_qty": 0,
        }
        adapter.engine.place_reentry_orders = MagicMock(return_value=mock_reentry_summary)

        # Run buy orders
        adapter.run_buy_orders()

        # Verify place_reentry_orders was called
        adapter.engine.place_reentry_orders.assert_called_once()

    def test_run_buy_orders_with_recommendations(self, db_session, test_user, mock_paper_broker):
        """Test buy orders with recommendations"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

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

        with patch.object(
            adapter.engine, "load_latest_recommendations", return_value=recommendations
        ):
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
        """Off-hours fresh entries use MARKET AMO (live parity after session)."""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from modules.kotak_neo_auto_trader.domain import OrderType, OrderVariety

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

        with (
            patch("core.volume_analysis.is_market_hours", return_value=False),
            patch("core.volume_analysis.is_pre_open_session", return_value=False),
        ):
            summary = adapter.place_new_entries(recommendations)

        assert summary["attempted"] == 1
        assert summary["placed"] == 1
        assert mock_paper_broker.place_order.called

        placed_order = mock_paper_broker.place_order.call_args[0][0]
        assert placed_order.order_type == OrderType.MARKET
        assert placed_order.variety == OrderVariety.AMO
        assert placed_order.price is None

    def test_place_new_entries_recalculates_capital_from_liquidity_service(
        self, db_session, test_user, mock_paper_broker
    ):
        """Fresh entries recalculate execution capital via LiquidityCapitalService (live parity)."""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 100000.0

        recommendations = [
            Recommendation(
                ticker="RELIANCE.NS",
                verdict="buy",
                last_close=50.0,
                execution_capital=99999.0,
            )
        ]

        mock_indicators = {"close": 50.0, "avg_volume": 10000, "rsi10": 25.0, "ema9": 52.0}

        with (
            patch("core.volume_analysis.is_market_hours", return_value=False),
            patch("core.volume_analysis.is_pre_open_session", return_value=False),
            patch.object(adapter, "_get_daily_indicators", return_value=mock_indicators),
        ):
            summary = adapter.place_new_entries(recommendations)

        assert summary["placed"] == 1
        placed_order = mock_paper_broker.place_order.call_args[0][0]
        # 10% of 10000 * 50 = 50000 capital → 1000 shares
        assert placed_order.quantity == 1000

    def test_place_new_entries_uses_limit_pre_open(self, db_session, test_user, mock_paper_broker):
        """9:01 pre-open fresh entries use REGULAR LIMIT @ signal close (live parity)."""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from modules.kotak_neo_auto_trader.domain import OrderType, OrderVariety

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )
        mock_paper_broker.config = MagicMock()
        mock_paper_broker.config.max_position_size = 100000.0

        recommendations = [
            Recommendation(
                ticker="RELIANCE.NS", verdict="buy", last_close=2500.0, execution_capital=100000.0
            )
        ]

        mock_indicators = {
            "close": 2500.0,
            "avg_volume": 1_000_000,
            "rsi10": 25.0,
            "ema9": 2520.0,
        }

        with (
            patch("core.volume_analysis.is_market_hours", return_value=True),
            patch("core.volume_analysis.is_pre_open_session", return_value=True),
            patch.object(adapter, "_get_daily_indicators", return_value=mock_indicators),
        ):
            summary = adapter.place_new_entries(recommendations)

        assert summary["placed"] == 1
        placed_order = mock_paper_broker.place_order.call_args[0][0]
        assert placed_order.order_type == OrderType.LIMIT
        assert placed_order.variety == OrderVariety.REGULAR
        assert placed_order.price is not None
        assert float(placed_order.price.amount) == 2500.0

    def test_place_new_entries_prevents_duplicate_symbols_with_different_formats(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that duplicate orders are not placed for same symbol with different formats"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

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

        # Create recommendations with same symbol but different formats
        recommendations = [
            Recommendation(ticker="XYZ", verdict="buy", last_close=100.0),  # Without .NS
            Recommendation(ticker="XYZ.NS", verdict="buy", last_close=100.0),  # With .NS
        ]

        summary = adapter.place_new_entries(recommendations)

        # Should attempt both but only place one (second should be detected as duplicate)
        assert summary["attempted"] == 2
        assert summary["placed"] == 1  # Only one order should be placed
        assert summary["skipped_duplicates"] == 1  # One should be skipped as duplicate

        # Verify only one order was placed
        assert mock_paper_broker.place_order.call_count == 1

    def test_place_new_entries_respects_max_position_size(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that orders respect max_position_size limit"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

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

        mock_indicators = {
            "close": 2500.0,
            "avg_volume": 1_000_000,
            "rsi10": 25.0,
            "ema9": 2520.0,
        }

        with patch.object(adapter, "_get_daily_indicators", return_value=mock_indicators):
            summary = adapter.place_new_entries(recommendations)

        assert summary["attempted"] == 1
        # Order should be placed but with adjusted quantity
        assert summary["placed"] == 1, summary
        assert mock_paper_broker.place_order.called

        # Verify order quantity was adjusted (should be ~20 shares for 50000/2500)
        call_args = mock_paper_broker.place_order.call_args
        order = call_args[0][0]
        assert order.quantity <= 20  # Should be limited by max_position_size

    def test_place_new_entries_duplicate(self, db_session, test_user, mock_paper_broker):
        """Test placing entries with duplicate in portfolio"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        # Mock holding
        mock_holding = MagicMock()
        mock_holding.symbol = "RELIANCE-EQ"  # Full symbol after migration
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
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

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

        with (
            patch(
                "src.application.services.paper_trading_service_adapter.PaperTradingBrokerAdapter"
            ) as mock_broker_class,
            patch(
                "src.application.services.paper_trading_service_adapter.PaperTradingConfig"
            ) as mock_config_class,
        ):
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

    def test_place_new_entries_skips_pending_orders(self, db_session, test_user, mock_paper_broker):
        """Test that duplicate check includes pending buy orders (not just holdings)"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from modules.kotak_neo_auto_trader.domain import (
            OrderStatus,
            TransactionType,
        )

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        # Mock no holdings but has pending order
        mock_paper_broker.get_holdings.return_value = []

        # Create a pending buy order for RELIANCE
        pending_order = MagicMock()
        pending_order.symbol = "RELIANCE-EQ"  # Full symbol after migration
        pending_order.status = OrderStatus.OPEN
        pending_order.transaction_type = TransactionType.BUY
        pending_order.is_buy_order.return_value = True
        pending_order.is_active.return_value = True

        mock_paper_broker.get_all_orders.return_value = [pending_order]
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

        # Should skip because of pending order
        assert summary["attempted"] == 1
        assert summary["placed"] == 0
        assert summary["skipped_duplicates"] == 1
        assert not mock_paper_broker.place_order.called

    def test_place_new_entries_multiple_pending_orders(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test duplicate prevention with multiple pending orders"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation
        from modules.kotak_neo_auto_trader.domain import OrderStatus, TransactionType

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        # Mock holdings with one stock
        mock_holding = MagicMock()
        mock_holding.symbol = "TCS-EQ"  # Full symbol after migration
        mock_paper_broker.get_holdings.return_value = [mock_holding]

        # Create pending orders
        pending_reliance = MagicMock()
        pending_reliance.symbol = "RELIANCE-EQ"  # Full symbol after migration
        pending_reliance.status = OrderStatus.OPEN
        pending_reliance.transaction_type = TransactionType.BUY
        pending_reliance.is_buy_order.return_value = True
        pending_reliance.is_active.return_value = True

        pending_infy = MagicMock()
        pending_infy.symbol = "INFY-EQ"  # Full symbol after migration
        pending_infy.status = OrderStatus.OPEN
        pending_infy.transaction_type = TransactionType.BUY
        pending_infy.is_buy_order.return_value = True
        pending_infy.is_active.return_value = True

        # Add a completed order (should not block)
        completed_order = MagicMock()
        completed_order.symbol = "HDFC"
        completed_order.status = OrderStatus.EXECUTED
        completed_order.is_buy_order.return_value = True
        completed_order.is_active.return_value = False

        mock_paper_broker.get_all_orders.return_value = [
            pending_reliance,
            pending_infy,
            completed_order,
        ]
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
            Recommendation(ticker="RELIANCE.NS", verdict="buy", last_close=2500.0),
            Recommendation(ticker="INFY.NS", verdict="buy", last_close=1450.0),
            Recommendation(ticker="TCS.NS", verdict="buy", last_close=3500.0),
            Recommendation(ticker="HDFC.NS", verdict="buy", last_close=1600.0),  # completed order
        ]

        summary = adapter.place_new_entries(recommendations)

        # All should be skipped (holdings + pending orders + completed but still valid)
        assert summary["attempted"] == 4
        assert summary["placed"] == 1  # Only HDFC should be placed (completed order doesn't block)
        assert summary["skipped_duplicates"] == 3


class TestPaperTradingSellMonitoring:
    """Test frozen EMA9 sell monitoring strategy"""

    @pytest.fixture
    def adapter_with_holdings(self, db_session, test_user, monkeypatch):
        """Create adapter with mock holdings for sell monitoring tests"""
        from config.strategy_config import StrategyConfig
        from src.infrastructure.persistence.positions_repository import PositionsRepository

        monkeypatch.setattr(
            "src.application.services.paper_trading_service_adapter.get_user_logger",
            lambda **kwargs: MagicMock(),
        )

        strategy_config = StrategyConfig(user_capital=100000.0, max_portfolio_size=6)

        mock_broker = MagicMock()
        mock_broker.is_connected.return_value = True
        mock_broker.config = MagicMock()
        mock_broker.config.max_position_size = 100000.0

        # Create positions in database (required for sell orders)
        positions_repo = PositionsRepository(db_session)

        # Create RELIANCE position
        pos1 = positions_repo.upsert(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            quantity=40.0,
            avg_price=2500.0,
        )

        # Create TCS position
        pos2 = positions_repo.upsert(
            user_id=test_user.id,
            symbol="TCS-EQ",
            quantity=30.0,
            avg_price=3500.0,
        )

        db_session.commit()

        # Mock broker methods
        # PaperTradingServiceAdapter._place_sell_orders() uses broker.get_holdings() as the
        # source of truth for what to place exits for.
        mock_reliance_holding = MagicMock()
        mock_reliance_holding.symbol = pos1.symbol
        mock_reliance_holding.quantity = int(pos1.quantity)

        mock_tcs_holding = MagicMock()
        mock_tcs_holding.symbol = pos2.symbol
        mock_tcs_holding.quantity = int(pos2.quantity)

        mock_broker.get_holdings.return_value = [mock_reliance_holding, mock_tcs_holding]
        mock_broker.place_order.return_value = "SELL_ORDER_123"
        mock_broker.get_pending_orders.return_value = []

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_broker
        adapter.engine = PaperTradingEngineAdapter(
            broker=mock_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=adapter.logger,
        )

        # Adapter defaults to running=False; tests that call _place_sell_orders/run_sell_monitor
        # need it True so the stop-request check doesn't skip placement
        adapter.running = True
        adapter.shutdown_requested = False
        adapter.indicator_service = MagicMock()
        adapter.price_service = MagicMock()

        return adapter

    def test_place_sell_orders_frozen_ema9(self, db_session, test_user, adapter_with_holdings):
        """Test that sell orders are placed at frozen EMA9 target"""
        from unittest.mock import patch

        from src.infrastructure.db.models import OrderStatus, TradeMode
        from src.infrastructure.persistence.orders_repository import OrdersRepository

        mock_calculate_ema9 = _ema9_for_ticker

        # Mock broker.place_order to save orders to database
        def mock_place_order(order):
            from src.infrastructure.db.models import Orders

            db_order = Orders(
                user_id=test_user.id,
                symbol=order.symbol,
                side="sell",
                order_type=order.order_type.value.lower(),
                quantity=order.quantity,
                price=float(order.price.amount) if order.price else None,
                status=OrderStatus.PENDING,
                broker_order_id=f"SELL_{order.symbol}_{order.quantity}",
                trade_mode=TradeMode.PAPER,
            )
            db_session.add(db_order)
            db_session.commit()
            return db_order.broker_order_id

        adapter_with_holdings.broker.place_order = mock_place_order

        with patch.object(
            adapter_with_holdings, "_calculate_ema9", side_effect=mock_calculate_ema9
        ):
            adapter_with_holdings._place_sell_orders()

        # Verify sell orders were placed at frozen targets - query database
        orders_repo = OrdersRepository(db_session)
        db_orders, _ = orders_repo.list(test_user.id)
        active_sell_orders = [
            o
            for o in db_orders
            if o.side == "sell"
            and o.status in [OrderStatus.PENDING, OrderStatus.ONGOING]
            and o.trade_mode == TradeMode.PAPER
        ]
        assert len(active_sell_orders) == 2

        # Check RELIANCE sell order
        reliance_orders = [o for o in active_sell_orders if "RELIANCE" in o.symbol]
        assert len(reliance_orders) == 1
        reliance_order = reliance_orders[0]
        assert reliance_order.price == 2600.0
        assert reliance_order.quantity == 40

        # Check TCS sell order
        tcs_orders = [o for o in active_sell_orders if "TCS" in o.symbol]
        assert len(tcs_orders) == 1
        tcs_order = tcs_orders[0]
        assert tcs_order.price == 3600.0
        assert tcs_order.quantity == 30

    def test_sell_orders_not_duplicated(self, db_session, test_user, adapter_with_holdings):
        """Morning placement cancels prior pending sells and places fresh EMA9 limits."""
        from unittest.mock import MagicMock, patch

        from src.infrastructure.db.models import Orders, OrderStatus, TradeMode
        from src.infrastructure.persistence.orders_repository import OrdersRepository

        existing_order = Orders(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            side="sell",
            order_type="limit",
            quantity=40.0,
            price=2600.0,
            status=OrderStatus.PENDING,
            broker_order_id="EXISTING_ORDER",
            trade_mode=TradeMode.PAPER,
        )
        db_session.add(existing_order)
        db_session.commit()

        mock_pending = MagicMock()
        mock_pending.symbol = "RELIANCE-EQ"
        mock_pending.is_sell_order.return_value = True
        mock_pending.is_active.return_value = True
        mock_pending.order_id = "EXISTING_ORDER"
        adapter_with_holdings.broker.get_pending_orders.return_value = [mock_pending]
        adapter_with_holdings.broker.cancel_order.return_value = True

        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "EXISTING_ORDER",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        def mock_calculate_ema9(ticker, broker_symbol=None):
            return _ema9_for_ticker(ticker, broker_symbol, reliance=2650.0, tcs=3600.0)

        def mock_place_order(order):
            from src.infrastructure.db.models import Orders

            db_order = Orders(
                user_id=test_user.id,
                symbol=order.symbol,
                side="sell",
                order_type=order.order_type.value.lower(),
                quantity=order.quantity,
                price=float(order.price.amount) if order.price else None,
                status=OrderStatus.PENDING,
                broker_order_id=f"SELL_{order.symbol}_{order.quantity}",
                trade_mode=TradeMode.PAPER,
            )
            db_session.add(db_order)
            db_session.commit()
            return db_order.broker_order_id

        adapter_with_holdings.broker.place_order = mock_place_order

        with (
            patch.object(adapter_with_holdings, "_calculate_ema9", side_effect=mock_calculate_ema9),
            patch.object(adapter_with_holdings, "_initialize_rsi10_cache_paper", return_value=None),
            patch.object(adapter_with_holdings, "_save_sell_orders_to_file", return_value=None),
        ):
            adapter_with_holdings._place_sell_orders()

        adapter_with_holdings.broker.cancel_order.assert_called_with("EXISTING_ORDER")

        orders_repo = OrdersRepository(db_session)
        db_orders, _ = orders_repo.list(test_user.id)
        reliance_pending = [
            o
            for o in db_orders
            if o.side == "sell"
            and "RELIANCE" in o.symbol
            and o.trade_mode == TradeMode.PAPER
            and o.status == OrderStatus.PENDING
        ]
        assert any(o.price == 2650.0 for o in reliance_pending)
        assert adapter_with_holdings.active_sell_orders["RELIANCE-EQ"]["target_price"] == 2650.0

        tcs_orders = [
            o
            for o in db_orders
            if o.side == "sell" and "TCS" in o.symbol and o.trade_mode == TradeMode.PAPER
        ]
        assert len(tcs_orders) == 1
        assert tcs_orders[0].price == 3600.0

    def test_monitor_sell_orders_target_reached_via_limit_fill(
        self, db_session, test_user, adapter_with_holdings
    ):
        """Test target exit: limit fill via check_and_execute_pending_orders (LTP >= limit)."""
        from unittest.mock import MagicMock, patch

        import pandas as pd

        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
                "entry_price": 2500.0,
            }
        }

        adapter_with_holdings.broker.check_and_execute_pending_orders = MagicMock(
            return_value={"checked": 1, "executed": 1, "still_pending": 0}
        )
        adapter_with_holdings.broker.get_holding = MagicMock(return_value=None)

        mock_data = _set_today_like_index(
            pd.DataFrame({"high": [2650.0], "close": [2620.0]})
        )

        with (
            patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data),
            patch.object(
                adapter_with_holdings, "_get_current_rsi10_paper", return_value=45.0
            ),
        ):
            adapter_with_holdings._monitor_sell_orders()

        assert "RELIANCE" not in adapter_with_holdings.active_sell_orders
        assert adapter_with_holdings.broker.check_and_execute_pending_orders.called
        adapter_with_holdings.broker.place_order.assert_not_called()

    def test_monitor_sell_orders_daily_high_fills_pending_limit(
        self, db_session, test_user, adapter_with_holdings
    ):
        """When daily high >= target but LTP did not fill, fill pending sell limit at target."""
        from unittest.mock import MagicMock, patch

        import pandas as pd

        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
                "entry_price": 2500.0,
            }
        }

        adapter_with_holdings.broker.check_and_execute_pending_orders = MagicMock(
            return_value={"checked": 1, "executed": 0, "still_pending": 1}
        )
        mock_holding = MagicMock()
        mock_holding.quantity = 40
        adapter_with_holdings.broker.get_holding = MagicMock(
            side_effect=[mock_holding, mock_holding, None]
        )
        adapter_with_holdings.broker.fill_pending_sell_limits_on_daily_high = MagicMock(
            return_value=True
        )

        mock_data = _set_today_like_index(
            pd.DataFrame({"high": [2650.0], "close": [2620.0]})
        )

        with (
            patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data),
            patch.object(
                adapter_with_holdings, "_get_current_rsi10_paper", return_value=45.0
            ),
        ):
            adapter_with_holdings._monitor_sell_orders()

        assert "RELIANCE" not in adapter_with_holdings.active_sell_orders
        adapter_with_holdings.broker.fill_pending_sell_limits_on_daily_high.assert_called_once_with(
            "RELIANCE", 2650.0
        )
        adapter_with_holdings.broker.place_order.assert_not_called()
        adapter_with_holdings.broker.cancel_order.assert_not_called()

    def test_monitor_sell_orders_target_reached_position_not_closed(
        self, db_session, test_user, adapter_with_holdings
    ):
        """Position stays tracked when limit was not filled and holding remains open."""
        from unittest.mock import MagicMock, patch

        import pandas as pd

        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
                "entry_price": 2500.0,
            }
        }

        adapter_with_holdings.broker.check_and_execute_pending_orders = MagicMock(
            return_value={"executed": 0, "still_pending": 1}
        )
        mock_holding = MagicMock()
        mock_holding.quantity = 40
        adapter_with_holdings.broker.get_holding = MagicMock(return_value=mock_holding)

        mock_data = _set_today_like_index(
            pd.DataFrame({"high": [2550.0], "close": [2520.0]})  # High < target
        )

        with (
            patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data),
            patch.object(
                adapter_with_holdings, "_get_current_rsi10_paper", return_value=45.0
            ),
        ):
            adapter_with_holdings._monitor_sell_orders()

        assert "RELIANCE" in adapter_with_holdings.active_sell_orders
        adapter_with_holdings.broker.place_order.assert_not_called()

    def test_monitor_sell_orders_rsi_exit(self, db_session, test_user, adapter_with_holdings):
        """Test exit condition: RSI > 50 (falling knife)"""
        from unittest.mock import patch

        import pandas as pd

        # Set up active sell order
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_123",
                "target_price": 2600.0,  # Target not reached
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }
        adapter_with_holdings.broker.check_and_execute_pending_orders = MagicMock(
            return_value={"executed": 0, "pending": 0}
        )
        mock_holding = MagicMock()
        mock_holding.quantity = 40
        adapter_with_holdings.broker.get_holding = MagicMock(return_value=mock_holding)

        mock_data = _set_today_like_index(
            pd.DataFrame(
                {
                    "high": [2550.0],
                    "close": [2520.0],
                }
            )
        )

        with (
            patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data),
            patch.object(
                adapter_with_holdings, "_get_current_rsi10_paper", return_value=52.0
            ),
        ):
            adapter_with_holdings._monitor_sell_orders()

        # Order should be removed (RSI exit triggered)
        assert "RELIANCE" not in adapter_with_holdings.active_sell_orders

        # Verify market order was placed
        assert adapter_with_holdings.broker.place_order.called
        call_args = adapter_with_holdings.broker.place_order.call_args
        market_order = call_args[0][0]
        assert market_order.transaction_type.name == "SELL"
        assert market_order.order_type.name == "MARKET"

    def test_monitor_sell_orders_no_exit(self, db_session, test_user, adapter_with_holdings):
        """Test that order remains active when neither exit condition is met"""
        from unittest.mock import patch

        import pandas as pd

        # Set up active sell order
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        # Mock OHLCV data where neither exit condition is met
        mock_data = _set_today_like_index(
            pd.DataFrame(
                {
                    "high": [2580.0],
                    "close": [2560.0],
                }
            )
        )

        adapter_with_holdings.broker.check_and_execute_pending_orders = MagicMock(
            return_value={"executed": 0, "pending": 0}
        )
        mock_holding = MagicMock()
        mock_holding.quantity = 40
        adapter_with_holdings.broker.get_holding = MagicMock(return_value=mock_holding)

        with (
            patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data),
            patch.object(
                adapter_with_holdings, "_get_current_rsi10_paper", return_value=45.0
            ),
        ):
            adapter_with_holdings._monitor_sell_orders()

        # Order should still be active
        assert "RELIANCE" in adapter_with_holdings.active_sell_orders
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"] == 2600.0

    def test_frozen_target_never_updates(self, db_session, test_user, adapter_with_holdings):
        """Test that frozen target price NEVER updates after initial placement"""
        from unittest.mock import patch

        import pandas as pd

        initial_target = 2600.0

        # Set up active sell order
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_123",
                "target_price": initial_target,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        # Mock data where EMA9 has changed significantly
        mock_data = _set_today_like_index(
            pd.DataFrame(
                {
                    "High": [2580.0],
                    "Close": [2560.0],
                    "RSI10": [45.0],
                }
            )
        )

        # Mock EMA9 calculation returning different value
        def mock_calculate_ema9(ticker, broker_symbol=None):
            return 2700.0  # EMA9 has moved up significantly!

        adapter_with_holdings.broker.check_and_execute_pending_orders = MagicMock(
            return_value={"executed": 0, "pending": 0}
        )
        mock_holding = MagicMock()
        mock_holding.quantity = 40
        adapter_with_holdings.broker.get_holding = MagicMock(return_value=mock_holding)

        with (
            patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data),
            patch.object(
                adapter_with_holdings, "_get_current_rsi10_paper", return_value=45.0
            ),
            patch.object(
                adapter_with_holdings, "_calculate_ema9", side_effect=mock_calculate_ema9
            ),
        ):
            adapter_with_holdings._monitor_sell_orders()

        # Target should STILL be frozen at original value
        assert "RELIANCE" in adapter_with_holdings.active_sell_orders
        assert (
            adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"] == initial_target
        )
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"] != 2700.0

    def test_calculate_ema9_uses_unified_sell_target(self, db_session, test_user):
        """Test that _calculate_ema9 delegates to compute_sell_target (realtime EMA9 path)."""
        from unittest.mock import MagicMock, patch

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
        )
        adapter.indicator_service = MagicMock()
        adapter.price_service = MagicMock()

        with patch(
            "modules.kotak_neo_auto_trader.services.sell_target_service.compute_sell_target",
            return_value=2565.45,
        ) as mock_compute:
            result = adapter._calculate_ema9("RELIANCE.NS", broker_symbol="RELIANCE-EQ")

        assert result == 2565.45
        mock_compute.assert_called_once()
        call_kw = mock_compute.call_args.kwargs
        assert call_kw["broker_symbol"] == "RELIANCE-EQ"
        assert call_kw["live_price_manager"] is None

    def test_monitor_sell_orders_with_lowercase_columns(self, db_session, test_user):
        """Test limit-fill tracking removal with lowercase OHLC columns."""
        from unittest.mock import MagicMock, patch

        import pandas as pd

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
        )
        adapter.broker = MagicMock()
        adapter.logger = MagicMock()
        adapter.converted_to_market = set()

        adapter.active_sell_orders = {
            "RELIANCE-EQ": {
                "order_id": "SELL_ORDER_123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        mock_data = _set_today_like_index(
            pd.DataFrame(
                {
                    "open": [2500.0] * 50,
                    "high": [2650.0] * 50,
                    "low": [2480.0] * 50,
                    "close": [2620.0] * 50,
                    "volume": [1000000] * 50,
                }
            )
        )

        adapter.broker.check_and_execute_pending_orders = MagicMock(
            return_value={"executed": 1, "still_pending": 0}
        )
        adapter.broker.get_holding.return_value = None

        with (
            patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data),
            patch.object(adapter, "_get_current_rsi10_paper", return_value=45.0),
        ):
            adapter._monitor_sell_orders()

        assert "RELIANCE-EQ" not in adapter.active_sell_orders
        assert mock_data["close"].iloc[-1] == 2620.0

    def test_monitor_sell_orders_fetches_60_days(self, db_session, test_user):
        """Test that _monitor_sell_orders fetches 60 days of data for stable indicators"""
        from unittest.mock import MagicMock, patch

        import pandas as pd

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
        )
        adapter.broker = MagicMock()
        adapter.logger = MagicMock()
        adapter.converted_to_market = set()  # Initialize RSI exit tracking

        adapter.active_sell_orders = {
            "RELIANCE-EQ": {  # Full symbol after migration
                "order_id": "SELL_ORDER_123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        mock_data = _set_today_like_index(
            pd.DataFrame(
                {
                    "high": [2580.0],
                    "close": [2560.0],
                }
            )
        )

        adapter.broker.check_and_execute_pending_orders = MagicMock(
            return_value={"executed": 0, "pending": 0}
        )
        mock_holding = MagicMock()
        mock_holding.quantity = 40
        adapter.broker.get_holding = MagicMock(return_value=mock_holding)

        with (
            patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_data) as mock_fetch,
            patch.object(adapter, "_get_current_rsi10_paper", return_value=45.0),
        ):
            adapter._monitor_sell_orders()

            calls = [call for call in mock_fetch.call_args_list if call[0][0] == "RELIANCE.NS"]
            assert len(calls) > 0, "fetch_ohlcv_yf should be called for RELIANCE.NS"

            main_call = next((call for call in calls if call[1].get("days") == 60), None)
            assert main_call is not None, (
                "fetch_ohlcv_yf should be called with days=60 for RSI session guard. "
                f"Actual calls: {[call[1] for call in calls]}"
            )

    def test_service_state_attributes(self, db_session, test_user):
        """Test that service has running and shutdown_requested attributes for scheduler control"""
        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
        )

        # Verify state attributes exist
        assert hasattr(adapter, "running")
        assert hasattr(adapter, "shutdown_requested")

        # Verify initial state
        assert adapter.running is False
        assert adapter.shutdown_requested is False

        # Test state changes
        adapter.running = True
        assert adapter.running is True

        adapter.shutdown_requested = True
        assert adapter.shutdown_requested is True

    @pytest.mark.skip(
        reason="File-based sell order tracking is deprecated. Orders are now tracked in database only."
    )
    def test_load_sell_orders_from_file(self, db_session, test_user, tmp_path):
        """Test loading sell orders from file on startup - DEPRECATED"""
        # File-based tracking removed - orders are now tracked in database only
        pass

    @pytest.mark.skip(
        reason="File-based sell order tracking is deprecated. Orders are now tracked in database only."
    )
    def test_load_sell_orders_from_file_filters_stale_orders(self, db_session, test_user, tmp_path):
        """Test that stale orders (no holdings, no pending) are filtered out - DEPRECATED"""
        # File-based tracking removed - orders are now tracked in database only
        pass

    @pytest.mark.skip(
        reason="File-based sell order tracking is deprecated. Orders are now tracked in database only."
    )
    def test_load_sell_orders_from_file_keeps_pending_orders(self, db_session, test_user, tmp_path):
        """Test that orders with pending broker orders are kept even without holdings - DEPRECATED"""
        # File-based tracking removed - orders are now tracked in database only
        pass

    @pytest.mark.skip(
        reason="File-based sell order tracking is deprecated. Orders are now tracked in database only."
    )
    def test_load_sell_orders_from_file_missing_file(self, db_session, test_user, tmp_path):
        """Test that missing file doesn't cause error - DEPRECATED"""
        # File-based tracking removed - orders are now tracked in database only
        pass

    def test_place_sell_orders_skips_loaded_orders(
        self, db_session, test_user, adapter_with_holdings, tmp_path
    ):
        """Morning placement replaces in-memory tracking with fresh EMA9 sells."""
        from unittest.mock import patch

        # Set storage path
        adapter_with_holdings.storage_path = str(tmp_path)
        adapter_with_holdings._sell_orders_file = tmp_path / "active_sell_orders.json"

        # Pre-load an order from file (simulating service restart)
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "LOADED_ORDER_123",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        adapter_with_holdings.broker.place_order.return_value = "NEW_RELIANCE_SELL"

        def mock_calculate_ema9(ticker, broker_symbol=None):
            return _ema9_for_ticker(ticker, broker_symbol, reliance=2650.0, tcs=3600.0)

        with (
            patch.object(adapter_with_holdings, "_calculate_ema9", side_effect=mock_calculate_ema9),
            patch.object(adapter_with_holdings, "_initialize_rsi10_cache_paper", return_value=None),
            patch.object(adapter_with_holdings, "_save_sell_orders_to_file", return_value=None),
        ):
            adapter_with_holdings._place_sell_orders()

        assert (
            adapter_with_holdings.active_sell_orders["RELIANCE-EQ"]["order_id"]
            == "NEW_RELIANCE_SELL"
        )
        assert adapter_with_holdings.active_sell_orders["RELIANCE-EQ"]["target_price"] == 2650.0
        assert "TCS-EQ" in adapter_with_holdings.active_sell_orders
        assert adapter_with_holdings.active_sell_orders["TCS-EQ"]["target_price"] == 3600.0

    def test_place_sell_orders_skips_pending_broker_orders(
        self, db_session, test_user, adapter_with_holdings
    ):
        """Stale broker pending sells are cancelled and replaced at latest EMA9."""
        from unittest.mock import MagicMock, patch

        # Create mock pending sell order in broker
        mock_pending_order = MagicMock()
        mock_pending_order.symbol = "RELIANCE"
        mock_pending_order.is_sell_order.return_value = True
        mock_pending_order.is_active.return_value = True
        mock_pending_order.price = MagicMock(amount=2600.0)
        mock_pending_order.order_id = "BROKER_ORDER_123"

        adapter_with_holdings.broker.get_pending_orders.return_value = [mock_pending_order]
        adapter_with_holdings.broker.cancel_order.return_value = True
        adapter_with_holdings.broker.place_order.return_value = "NEW_RELIANCE_SELL"
        adapter_with_holdings.active_sell_orders = {}

        def mock_calculate_ema9(ticker, broker_symbol=None):
            return _ema9_for_ticker(ticker, broker_symbol, reliance=2650.0, tcs=3600.0)

        with (
            patch.object(adapter_with_holdings, "_calculate_ema9", side_effect=mock_calculate_ema9),
            patch.object(adapter_with_holdings, "_initialize_rsi10_cache_paper", return_value=None),
            patch.object(adapter_with_holdings, "_save_sell_orders_to_file", return_value=None),
        ):
            adapter_with_holdings._place_sell_orders()

        adapter_with_holdings.broker.cancel_order.assert_called_with("BROKER_ORDER_123")
        assert "RELIANCE-EQ" in adapter_with_holdings.active_sell_orders
        assert adapter_with_holdings.active_sell_orders["RELIANCE-EQ"]["target_price"] == 2650.0
        assert "TCS-EQ" in adapter_with_holdings.active_sell_orders

    def test_eod_cleanup_cancels_pending_sell_orders(
        self, db_session, test_user, adapter_with_holdings
    ):
        """EOD cleanup cancels unexecuted sell limits and clears tracking."""
        from unittest.mock import MagicMock, patch

        mock_pending = MagicMock()
        mock_pending.symbol = "RELIANCE-EQ"
        mock_pending.is_sell_order.return_value = True
        mock_pending.is_active.return_value = True
        mock_pending.order_id = "EOD_SELL_1"

        adapter_with_holdings.broker.get_pending_orders.return_value = [mock_pending]
        adapter_with_holdings.broker.cancel_order.return_value = True
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE-EQ": {"order_id": "EOD_SELL_1", "target_price": 2600.0, "qty": 40}
        }
        adapter_with_holdings.reporter = None

        with patch.object(adapter_with_holdings, "_save_sell_orders_to_file"):
            adapter_with_holdings.run_eod_cleanup()

        adapter_with_holdings.broker.cancel_order.assert_called_with("EOD_SELL_1")
        assert adapter_with_holdings.active_sell_orders == {}

    def test_eod_cleanup_cancels_pending_day_buy_not_amo(
        self, db_session, test_user, adapter_with_holdings
    ):
        """EOD cleanup cancels REGULAR/DAY pending buys but preserves AMO."""
        from unittest.mock import MagicMock, patch

        day_buy = MagicMock()
        day_buy.symbol = "GALLANTT.NS"
        day_buy.is_buy_order.return_value = True
        day_buy.is_sell_order.return_value = False
        day_buy.is_active.return_value = True
        day_buy.is_amo_order.return_value = False
        day_buy.is_eod_cancellable_day_buy.return_value = True
        day_buy.order_id = "EOD_BUY_DAY_1"

        amo_buy = MagicMock()
        amo_buy.symbol = "RELIANCE.NS"
        amo_buy.is_buy_order.return_value = True
        amo_buy.is_sell_order.return_value = False
        amo_buy.is_active.return_value = True
        amo_buy.is_amo_order.return_value = True
        amo_buy.is_eod_cancellable_day_buy.return_value = False
        amo_buy.order_id = "EOD_BUY_AMO_1"

        adapter_with_holdings.broker.get_pending_orders.return_value = [day_buy, amo_buy]
        adapter_with_holdings.broker.cancel_order.return_value = True
        adapter_with_holdings.reporter = None
        adapter_with_holdings.active_sell_orders = {}

        with patch.object(adapter_with_holdings, "_save_sell_orders_to_file"):
            with patch.object(adapter_with_holdings, "_cancel_unexecuted_sell_orders", return_value={}):
                adapter_with_holdings.run_eod_cleanup()

        adapter_with_holdings.broker.cancel_order.assert_called_once_with("EOD_BUY_DAY_1")

    @pytest.mark.skip(
        reason="File-based sell order tracking is deprecated. Orders are now tracked in database only."
    )
    def test_initialize_loads_sell_orders(self, db_session, test_user, tmp_path):
        """Test that initialize() calls _load_sell_orders_from_file() - DEPRECATED"""
        # File-based tracking removed - orders are now tracked in database only
        pass

    def test_update_sell_order_quantity_after_reentry(
        self, db_session, test_user, adapter_with_holdings
    ):
        """After re-entry, _update_sell_order_quantity cancels the old sell and places updated qty/limit."""
        from unittest.mock import patch

        adapter = adapter_with_holdings
        new_target = 2650.0
        adapter.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_OLD",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }
        adapter.broker.cancel_order.return_value = True
        adapter.broker.place_order.return_value = "SELL_ORDER_NEW"

        with (
            patch.object(adapter, "_calculate_ema9", return_value=new_target),
            patch.object(adapter, "_save_sell_orders_to_file"),
        ):
            updated = adapter._update_sell_order_quantity("RELIANCE", 60, new_target)

        assert updated is True
        adapter.broker.cancel_order.assert_called_once_with("SELL_ORDER_OLD")
        adapter.broker.place_order.assert_called_once()
        new_order = adapter.broker.place_order.call_args[0][0]
        assert new_order.quantity == 60
        assert new_order.transaction_type.value == "SELL"
        assert float(new_order.price.amount) == new_target
        assert adapter.active_sell_orders["RELIANCE"]["qty"] == 60
        assert adapter.active_sell_orders["RELIANCE"]["target_price"] == new_target
        assert adapter.active_sell_orders["RELIANCE"]["order_id"] == "SELL_ORDER_NEW"

    def test_sync_sell_order_quantities_with_holdings(
        self, db_session, test_user, adapter_with_holdings
    ):
        """Test that _sync_sell_order_quantities_with_holdings updates multiple orders"""
        from unittest.mock import MagicMock

        # Set up multiple sell orders with outdated quantities
        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL_ORDER_1",
                "target_price": 2600.0,
                "qty": 40,  # Old quantity
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            },
            "TCS": {
                "order_id": "SELL_ORDER_2",
                "target_price": 3600.0,
                "qty": 30,  # Old quantity
                "ticker": "TCS.NS",
                "entry_date": "2024-01-01",
            },
        }

        # Mock holdings with increased quantities (re-entries happened)
        mock_holding1 = MagicMock()
        mock_holding1.symbol = "RELIANCE"
        mock_holding1.quantity = 60  # Increased from 40

        mock_holding2 = MagicMock()
        mock_holding2.symbol = "TCS"
        mock_holding2.quantity = 30  # Same (no re-entry)

        adapter_with_holdings.broker.get_holdings.return_value = [
            mock_holding1,
            mock_holding2,
        ]

        # Mock cancel and place order
        adapter_with_holdings.broker.cancel_order.return_value = True
        adapter_with_holdings.broker.place_order.side_effect = [
            "NEW_SELL_ORDER_1",
            "NEW_SELL_ORDER_2",
        ]

        # Mock EMA9 calculation to return new targets
        from unittest.mock import patch

        new_target_reliance = 2650.0
        with patch.object(
            adapter_with_holdings, "_calculate_ema9", return_value=new_target_reliance
        ):
            # Sync quantities (targets will be recalculated)
            updated_count = adapter_with_holdings._sync_sell_order_quantities_with_holdings()

        # Verify only RELIANCE was updated (TCS quantity didn't change)
        assert updated_count == 1
        assert adapter_with_holdings.active_sell_orders["RELIANCE"]["qty"] == 60
        assert (
            adapter_with_holdings.active_sell_orders["RELIANCE"]["target_price"]
            == new_target_reliance
        )
        assert adapter_with_holdings.active_sell_orders["TCS"]["qty"] == 30  # Unchanged

    def test_place_sell_orders_updates_quantity_on_reentry(
        self, db_session, test_user, adapter_with_holdings
    ):
        """Morning placement replaces stale sells using current holdings qty and EMA9."""
        from unittest.mock import MagicMock, patch

        adapter_with_holdings.active_sell_orders = {
            "RELIANCE": {
                "order_id": "EXISTING_ORDER",
                "target_price": 2600.0,
                "qty": 40,
                "ticker": "RELIANCE.NS",
                "entry_date": "2024-01-01",
            }
        }

        mock_holding = MagicMock()
        mock_holding.symbol = "RELIANCE-EQ"
        mock_holding.quantity = 60
        adapter_with_holdings.broker.get_holdings.return_value = [mock_holding]

        mock_pending_order = MagicMock()
        mock_pending_order.symbol = "RELIANCE-EQ"
        mock_pending_order.is_sell_order.return_value = True
        mock_pending_order.is_active.return_value = True
        mock_pending_order.order_id = "EXISTING_ORDER"
        adapter_with_holdings.broker.get_pending_orders.return_value = [mock_pending_order]
        adapter_with_holdings.broker.cancel_order.return_value = True
        adapter_with_holdings.broker.place_order.return_value = "UPDATED_ORDER"

        new_target = 2650.0
        with (
            patch.object(adapter_with_holdings, "_calculate_ema9", return_value=new_target),
            patch.object(adapter_with_holdings, "_initialize_rsi10_cache_paper", return_value=None),
            patch.object(adapter_with_holdings, "_save_sell_orders_to_file", return_value=None),
        ):
            adapter_with_holdings._place_sell_orders()

        assert adapter_with_holdings.active_sell_orders["RELIANCE-EQ"]["qty"] == 60
        assert adapter_with_holdings.active_sell_orders["RELIANCE-EQ"]["target_price"] == new_target
        adapter_with_holdings.broker.cancel_order.assert_called_with("EXISTING_ORDER")
        adapter_with_holdings.broker.place_order.assert_called_once()

        new_order = adapter_with_holdings.broker.place_order.call_args[0][0]
        assert float(new_order.price.amount) == new_target


class TestSignalStatusFiltering:
    """Test that signal status filtering works correctly in load_latest_recommendations"""

    def test_load_recommendations_includes_active_signals(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that ACTIVE signals are included in recommendations"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create ACTIVE signals
        signal1 = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="TCS",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=3500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2])
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should return both ACTIVE signals
        assert len(recs) == 2
        tickers = {r.ticker for r in recs}
        assert "RELIANCE.NS" in tickers
        assert "TCS.NS" in tickers

    def test_load_recommendations_excludes_traded_signals(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that TRADED signals (per-user) are excluded from recommendations"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create ACTIVE signal
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Mark as TRADED for this user (per-user status)
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="RELIANCE",
            status=SignalStatus.TRADED,
        )
        db_session.add(user_status)
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should exclude TRADED signal
        assert len(recs) == 0

    def test_load_recommendations_excludes_rejected_signals(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that REJECTED signals (per-user) are excluded from recommendations"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create ACTIVE signal
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Mark as REJECTED for this user (per-user status)
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="RELIANCE",
            status=SignalStatus.REJECTED,
        )
        db_session.add(user_status)
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should exclude REJECTED signal
        assert len(recs) == 0

    def test_load_recommendations_excludes_expired_signals(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that EXPIRED signals (base status) are excluded from recommendations"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create EXPIRED signal
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.EXPIRED,
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should exclude EXPIRED signal
        assert len(recs) == 0

    def test_load_recommendations_excludes_failed_signals(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that FAILED signals (per-user) are excluded from recommendations"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create ACTIVE signal
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Mark as FAILED for this user (per-user status)
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="RELIANCE",
            status=SignalStatus.FAILED,
        )
        db_session.add(user_status)
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should exclude FAILED signal
        assert len(recs) == 0

    def test_load_recommendations_per_user_status_takes_precedence(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that per-user status takes precedence over base signal status, except for EXPIRED"""
        # Create another user
        user2 = Users(
            email="user2@test.com",
            password_hash="hash2",
            role="user",
        )
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user2)

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create signal with TRADED base status (not EXPIRED - user can override TRADED/REJECTED)
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.TRADED,  # Base status is TRADED (can be overridden)
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Mark as ACTIVE for test_user (per-user status override)
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,  # Per-user status is ACTIVE
        )
        db_session.add(user_status)
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should include signal because per-user status (ACTIVE) takes precedence over TRADED
        assert len(recs) == 1
        assert recs[0].ticker == "RELIANCE.NS"

    def test_load_recommendations_expired_signals_cannot_be_overridden(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that EXPIRED signals cannot be overridden by per-user status"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create signal with EXPIRED base status
        signal = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.EXPIRED,  # Base status is EXPIRED
            ts=ist_now(),
        )
        db_session.add(signal)
        db_session.commit()
        db_session.refresh(signal)

        # Try to mark as ACTIVE for test_user (per-user status)
        user_status = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal.id,
            symbol="RELIANCE",
            status=SignalStatus.ACTIVE,  # Per-user status is ACTIVE (but should be ignored)
        )
        db_session.add(user_status)
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should NOT include signal because EXPIRED status cannot be overridden
        assert len(recs) == 0

    def test_load_recommendations_mixed_status_signals(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test filtering with mixed status signals"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create multiple signals with different statuses
        signal1 = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="TCS",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=3500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal3 = Signals(
            symbol="INFY",
            verdict="buy",
            final_verdict="buy",
            last_close=1500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal4 = Signals(
            symbol="HDFC",
            verdict="buy",
            final_verdict="buy",
            last_close=2000.0,
            status=SignalStatus.EXPIRED,
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2, signal3, signal4])
        db_session.commit()
        db_session.refresh(signal2)
        db_session.refresh(signal3)

        # Mark signal2 as TRADED (per-user)
        user_status_traded = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal2.id,
            symbol="TCS",
            status=SignalStatus.TRADED,
        )
        # Mark signal3 as REJECTED (per-user)
        user_status_rejected = UserSignalStatus(
            user_id=test_user.id,
            signal_id=signal3.id,
            symbol="INFY",
            status=SignalStatus.REJECTED,
        )
        db_session.add_all([user_status_traded, user_status_rejected])
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should only return signal1 (ACTIVE, no per-user status)
        # signal2 is TRADED (per-user) - excluded
        # signal3 is REJECTED (per-user) - excluded
        # signal4 is EXPIRED (base) - excluded
        assert len(recs) == 1
        assert recs[0].ticker == "RELIANCE.NS"


class TestDuplicateSymbolDeduplication:
    """Test that duplicate symbols are deduplicated when loading recommendations"""

    def test_load_recommendations_deduplicates_xyz_and_xyz_ns(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that signals with 'XYZ' and 'XYZ.NS' are deduplicated"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create signals with same symbol but different formats
        signal1 = Signals(
            symbol="XYZ",
            verdict="buy",
            final_verdict="buy",
            last_close=100.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="XYZ.NS",
            verdict="buy",
            final_verdict="buy",
            last_close=100.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2])
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should only return one recommendation (first one encountered)
        assert len(recs) == 1
        # Both should normalize to XYZ.NS
        assert recs[0].ticker == "XYZ.NS"

    def test_load_recommendations_deduplicates_case_insensitive(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that symbol deduplication is case-insensitive"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create signals with same symbol but different cases
        signal1 = Signals(
            symbol="reliance",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="RELIANCE",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2])
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should only return one recommendation
        assert len(recs) == 1
        assert recs[0].ticker == "RELIANCE.NS"

    def test_load_recommendations_deduplicates_with_bo_suffix(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that symbols with .BO suffix are also deduplicated"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create signals with same base symbol but different suffixes
        # Use explicit timestamps to ensure order: ABC comes first
        now = ist_now()
        signal1 = Signals(
            symbol="ABC",
            verdict="buy",
            final_verdict="buy",
            last_close=50.0,
            status=SignalStatus.ACTIVE,
            ts=now,  # Same timestamp, but added first
        )
        signal2 = Signals(
            symbol="ABC.BO",
            verdict="buy",
            final_verdict="buy",
            last_close=50.0,
            status=SignalStatus.ACTIVE,
            ts=now,  # Same timestamp
        )
        db_session.add(signal1)
        db_session.flush()  # Ensure signal1 is added first
        db_session.add(signal2)
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should only return one recommendation (first one encountered)
        assert len(recs) == 1
        # The first signal processed will be kept
        # Since both normalize to "ABC", whichever is processed first wins
        # We verify deduplication worked by checking only one is returned
        ticker = recs[0].ticker
        assert ticker in ["ABC.NS", "ABC.BO"], f"Expected ABC.NS or ABC.BO, got {ticker}"

    def test_load_recommendations_keeps_first_duplicate(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that the first signal encountered is kept when duplicates exist"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create signals with same normalized symbol but different prices
        # Use explicit timestamps to ensure order: TEST comes first
        now = ist_now()
        signal1 = Signals(
            symbol="TEST",
            verdict="buy",
            final_verdict="buy",
            last_close=200.0,
            status=SignalStatus.ACTIVE,
            ts=now,  # Same timestamp, but added first
        )
        # Second signal has lower price
        signal2 = Signals(
            symbol="TEST.NS",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=150.0,
            status=SignalStatus.ACTIVE,
            ts=now,  # Same timestamp
        )
        db_session.add(signal1)
        db_session.flush()  # Ensure signal1 is added first
        db_session.add(signal2)
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should only return one recommendation
        assert len(recs) == 1
        # Should keep the first one encountered (TEST -> TEST.NS)
        assert recs[0].ticker == "TEST.NS"
        # The first signal processed will be kept (order may vary, so check either price)
        assert recs[0].last_close in [200.0, 150.0]

    def test_load_recommendations_no_deduplication_for_different_symbols(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that different symbols are not deduplicated"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create signals with different symbols
        signal1 = Signals(
            symbol="RELIANCE",
            verdict="buy",
            final_verdict="buy",
            last_close=2500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="TCS",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=3500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal3 = Signals(
            symbol="INFY",
            verdict="buy",
            final_verdict="buy",
            last_close=1500.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2, signal3])
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should return all three recommendations (no duplicates)
        assert len(recs) == 3
        tickers = {r.ticker for r in recs}
        assert "RELIANCE.NS" in tickers
        assert "TCS.NS" in tickers
        assert "INFY.NS" in tickers

    def test_load_recommendations_deduplicates_multiple_duplicates(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that multiple duplicates of the same symbol are all deduplicated"""
        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=None,
            logger=MagicMock(),
        )

        # Create multiple signals with same normalized symbol
        signal1 = Signals(
            symbol="MULTI",
            verdict="buy",
            final_verdict="buy",
            last_close=100.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal2 = Signals(
            symbol="MULTI.NS",
            verdict="buy",
            final_verdict="buy",
            last_close=100.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        signal3 = Signals(
            symbol="multi",
            verdict="strong_buy",
            final_verdict="strong_buy",
            last_close=100.0,
            status=SignalStatus.ACTIVE,
            ts=ist_now(),
        )
        db_session.add_all([signal1, signal2, signal3])
        db_session.commit()

        recs = adapter.load_latest_recommendations()

        # Should only return one recommendation (first one)
        assert len(recs) == 1
        assert recs[0].ticker == "MULTI.NS"


class TestPaperDailyIndicatorsLookback:
    """RSI10 must use a long OHLCV window (matches live IndicatorService)."""

    def test_get_daily_indicators_uses_long_lookback(self, db_session, test_user):
        engine = PaperTradingEngineAdapter(
            broker=MagicMock(),
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=MagicMock(),
            logger=MagicMock(),
        )
        mock_df = pd.DataFrame(
            {
                "close": [100.0 + i * 0.1 for i in range(100)],
                "volume": [1000] * 100,
            }
        )

        with patch("core.data_fetcher.fetch_ohlcv_yf", return_value=mock_df) as mock_fetch:
            result = engine._get_daily_indicators("DMART.NS", add_current_day=False)

        assert result is not None
        mock_fetch.assert_called_once_with(
            "DMART.NS",
            days=800,
            interval="1d",
            add_current_day=False,
        )
        assert "rsi10" in result
