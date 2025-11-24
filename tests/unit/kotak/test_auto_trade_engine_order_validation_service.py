"""
Unit tests for AutoTradeEngine OrderValidationService integration

Tests verify the migration of Buy Orders and Pre-market Retry services
to use OrderValidationService while maintaining backward compatibility.

Phase 3.1: Order Validation & Verification
"""

from unittest.mock import Mock, MagicMock, patch

import pytest

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine


class TestAutoTradeEngineOrderValidationServiceInitialization:
    """Test AutoTradeEngine initialization with OrderValidationService"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_init_with_order_validation_service(self, mock_auth):
        """Test that AutoTradeEngine initializes OrderValidationService"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        engine = AutoTradeEngine(env_file="test.env", user_id=1)

        assert engine.order_validation_service is not None
        assert engine.order_validation_service.portfolio_service == engine.portfolio_service
        assert engine.order_validation_service.portfolio is None  # Set after login
        assert engine.order_validation_service.orders is None  # Set after login

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoOrders")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoPortfolio")
    def test_login_updates_order_validation_service(self, mock_portfolio, mock_orders, mock_auth):
        """Test that login() updates OrderValidationService with portfolio and orders"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        mock_portfolio_instance = Mock()
        mock_orders_instance = Mock()
        mock_portfolio.return_value = mock_portfolio_instance
        mock_orders.return_value = mock_orders_instance

        engine = AutoTradeEngine(env_file="test.env", user_id=1)
        engine.login()

        assert engine.order_validation_service.portfolio == mock_portfolio_instance
        assert engine.order_validation_service.orders == mock_orders_instance


class TestBuyOrdersServiceOrderValidationServiceIntegration:
    """Test that place_new_entries() uses OrderValidationService correctly"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_place_new_entries_uses_order_validation_service_volume_ratio(
        self, mock_auth
    ):
        """Test that place_new_entries() uses OrderValidationService.check_volume_ratio()"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock OrderValidationService
        mock_validation_service = Mock()
        mock_validation_service.check_portfolio_capacity = Mock(
            return_value=(True, 3, 10)  # has_capacity, current_count, max_size
        )
        mock_validation_service.check_duplicate_order = Mock(
            return_value=(False, None)  # is_duplicate, reason
        )
        mock_validation_service.check_volume_ratio = Mock(
            return_value=(False, 0.5, "Rs 500+ (10%)")  # is_valid, ratio, tier_info
        )
        mock_validation_service.check_balance = Mock(
            return_value=(True, 100000.0, 40)  # has_sufficient, available_cash, affordable_qty
        )

        # Mock PortfolioService
        mock_portfolio_service = Mock()
        mock_portfolio_service.get_portfolio_count = Mock(return_value=3)
        mock_portfolio_service.get_current_positions = Mock(return_value=[])
        mock_validation_service.portfolio_service = mock_portfolio_service

        # Create engine
        engine = AutoTradeEngine(env_file="test.env", user_id=1)
        engine.order_validation_service = mock_validation_service
        engine.portfolio_service = mock_portfolio_service
        engine.portfolio = Mock()
        engine.portfolio.get_holdings = Mock(return_value={"data": []})
        engine.orders = Mock()
        engine.orders.get_pending_orders = Mock(return_value=[])

        # Mock recommendation
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        rec = Recommendation(
            ticker="RELIANCE.NS",
            verdict="buy",
            last_close=2500.0,
            execution_capital=50000.0,
        )

        # Mock indicators
        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.AutoTradeEngine.get_daily_indicators"
        ) as mock_indicators:
            mock_indicators.return_value = {
                "close": 2500.0,
                "rsi10": 25.0,
                "ema9": 2480.0,
                "ema200": 2400.0,
                "avg_volume": 1000.0,  # Low volume to trigger ratio check
            }

            summary = engine.place_new_entries([rec])

            # Verify OrderValidationService.check_volume_ratio() was called
            mock_validation_service.check_volume_ratio.assert_called()
            assert summary["skipped_invalid_qty"] > 0 or summary["attempted"] > 0

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_place_new_entries_uses_order_validation_service_balance(self, mock_auth):
        """Test that place_new_entries() uses OrderValidationService.check_balance()"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock OrderValidationService
        mock_validation_service = Mock()
        mock_validation_service.check_portfolio_capacity = Mock(
            return_value=(True, 3, 10)
        )
        mock_validation_service.check_duplicate_order = Mock(
            return_value=(False, None)
        )
        mock_validation_service.check_volume_ratio = Mock(
            return_value=(True, 0.01, "Rs 500+ (10%)")
        )
        mock_validation_service.check_balance = Mock(
            return_value=(False, 1000.0, 0)  # Insufficient balance
        )

        # Mock PortfolioService
        mock_portfolio_service = Mock()
        mock_portfolio_service.get_portfolio_count = Mock(return_value=3)
        mock_portfolio_service.get_current_positions = Mock(return_value=[])
        mock_validation_service.portfolio_service = mock_portfolio_service

        # Create engine
        engine = AutoTradeEngine(env_file="test.env", user_id=1)
        engine.order_validation_service = mock_validation_service
        engine.portfolio_service = mock_portfolio_service
        engine.portfolio = Mock()
        engine.portfolio.get_holdings = Mock(return_value={"data": []})
        engine.orders = Mock()
        engine.orders.get_pending_orders = Mock(return_value=[])

        # Mock recommendation
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        rec = Recommendation(
            ticker="RELIANCE.NS",
            verdict="buy",
            last_close=2500.0,
            execution_capital=50000.0,
        )

        # Mock indicators
        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.AutoTradeEngine.get_daily_indicators"
        ) as mock_indicators:
            mock_indicators.return_value = {
                "close": 2500.0,
                "rsi10": 25.0,
                "ema9": 2480.0,
                "ema200": 2400.0,
                "avg_volume": 1000000.0,
            }

            summary = engine.place_new_entries([rec])

            # Verify OrderValidationService.check_balance() was called
            mock_validation_service.check_balance.assert_called()
            # Balance check happens after volume ratio, so we expect it to be called if volume passes

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_place_new_entries_uses_order_validation_service_portfolio_capacity(
        self, mock_auth
    ):
        """Test that place_new_entries() uses OrderValidationService.check_portfolio_capacity()"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock OrderValidationService
        mock_validation_service = Mock()
        mock_validation_service.check_portfolio_capacity = Mock(
            return_value=(False, 10, 10)  # At capacity
        )

        # Mock PortfolioService
        mock_portfolio_service = Mock()
        mock_portfolio_service.get_portfolio_count = Mock(return_value=10)
        mock_portfolio_service.get_current_positions = Mock(return_value=[])
        mock_validation_service.portfolio_service = mock_portfolio_service

        # Create engine
        engine = AutoTradeEngine(env_file="test.env", user_id=1)
        engine.order_validation_service = mock_validation_service
        engine.portfolio_service = mock_portfolio_service
        engine.portfolio = Mock()
        engine.portfolio.get_holdings = Mock(return_value={"data": []})
        engine.orders = Mock()
        engine.orders.get_pending_orders = Mock(return_value=[])

        # Mock recommendation
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        rec = Recommendation(
            ticker="RELIANCE.NS",
            verdict="buy",
            last_close=2500.0,
            execution_capital=50000.0,
        )

        summary = engine.place_new_entries([rec])

        # Verify OrderValidationService.check_portfolio_capacity() was called
        mock_validation_service.check_portfolio_capacity.assert_called()
        assert summary["skipped_portfolio_limit"] > 0

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_place_new_entries_uses_order_validation_service_duplicate_check(
        self, mock_auth
    ):
        """Test that place_new_entries() uses OrderValidationService.check_duplicate_order()"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock OrderValidationService
        mock_validation_service = Mock()
        mock_validation_service.check_portfolio_capacity = Mock(
            return_value=(True, 3, 10)
        )
        mock_validation_service.check_duplicate_order = Mock(
            return_value=(True, "Already in holdings: RELIANCE")
        )
        mock_validation_service.check_volume_ratio = Mock(
            return_value=(True, 0.01, "Rs 500+ (10%)")
        )
        mock_validation_service.check_balance = Mock(
            return_value=(True, 100000.0, 40)
        )

        # Mock PortfolioService
        mock_portfolio_service = Mock()
        mock_portfolio_service.get_portfolio_count = Mock(return_value=3)
        mock_portfolio_service.get_current_positions = Mock(return_value=[])
        mock_validation_service.portfolio_service = mock_portfolio_service

        # Create engine
        engine = AutoTradeEngine(env_file="test.env", user_id=1)
        engine.order_validation_service = mock_validation_service
        engine.portfolio_service = mock_portfolio_service
        engine.portfolio = Mock()
        engine.portfolio.get_holdings = Mock(return_value={"data": []})
        engine.orders = Mock()
        engine.orders.get_pending_orders = Mock(return_value=[])

        # Mock recommendation
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        rec = Recommendation(
            ticker="RELIANCE.NS",
            verdict="buy",
            last_close=2500.0,
            execution_capital=50000.0,
        )

        summary = engine.place_new_entries([rec])

        # Verify OrderValidationService.check_duplicate_order() was called
        mock_validation_service.check_duplicate_order.assert_called()
        assert summary["skipped_duplicates"] > 0


class TestRetryServiceOrderValidationServiceIntegration:
    """Test that retry_pending_orders_from_db() uses OrderValidationService correctly"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_uses_order_validation_service_portfolio_capacity(self, mock_auth):
        """Test that retry uses OrderValidationService.check_portfolio_capacity()"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock OrderValidationService
        mock_validation_service = Mock()
        mock_validation_service.check_portfolio_capacity = Mock(
            return_value=(False, 10, 10)  # At capacity
        )

        # Mock PortfolioService
        mock_portfolio_service = Mock()
        mock_portfolio_service.get_portfolio_count = Mock(return_value=10)
        mock_validation_service.portfolio_service = mock_portfolio_service

        # Mock order (need at least one to trigger capacity check)
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        mock_order = Mock()
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.id = 1
        mock_order.status = DbOrderStatus.FAILED

        # Mock orders repository
        mock_orders_repo = Mock()
        mock_orders_repo.get_retriable_failed_orders = Mock(return_value=[mock_order])
        mock_orders_repo.list = Mock(return_value=[])

        # Create engine instance
        engine = AutoTradeEngine(env_file="test.env", user_id=1)
        engine.order_validation_service = mock_validation_service
        engine.portfolio_service = mock_portfolio_service
        engine.orders_repo = mock_orders_repo

        summary = engine.retry_pending_orders_from_db()

        # Verify OrderValidationService.check_portfolio_capacity() was called
        mock_validation_service.check_portfolio_capacity.assert_called()
        assert summary["skipped"] > 0 or summary["retried"] == 0

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_uses_order_validation_service_duplicate_check(self, mock_auth):
        """Test that retry uses OrderValidationService.check_duplicate_order()"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock OrderValidationService
        mock_validation_service = Mock()
        mock_validation_service.check_portfolio_capacity = Mock(
            return_value=(True, 5, 10)
        )
        mock_validation_service.check_duplicate_order = Mock(
            return_value=(True, "Already in holdings: RELIANCE")
        )
        mock_validation_service.check_volume_ratio = Mock(
            return_value=(True, 0.01, "Rs 500+ (10%)")
        )

        # Mock PortfolioService
        mock_portfolio_service = Mock()
        mock_portfolio_service.get_portfolio_count = Mock(return_value=5)
        mock_validation_service.portfolio_service = mock_portfolio_service

        # Mock IndicatorService
        mock_indicator_service = Mock()
        mock_indicator_service.get_daily_indicators_dict = Mock(
            return_value={
                "close": 2500.0,
                "rsi10": 25.0,
                "ema9": 2480.0,
                "ema200": 2400.0,
                "avg_volume": 1000000.0,
            }
        )

        # Mock order
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        mock_order = Mock()
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.id = 1
        mock_order.status = DbOrderStatus.FAILED

        # Mock orders repository
        mock_orders_repo = Mock()
        mock_orders_repo.get_retriable_failed_orders = Mock(return_value=[mock_order])
        mock_orders_repo.list = Mock(return_value=[])
        mock_orders_repo.mark_cancelled = Mock()

        # Create engine instance
        engine = AutoTradeEngine(env_file="test.env", user_id=1)
        engine.order_validation_service = mock_validation_service
        engine.portfolio_service = mock_portfolio_service
        engine.indicator_service = mock_indicator_service
        engine.orders_repo = mock_orders_repo

        summary = engine.retry_pending_orders_from_db()

        # Verify OrderValidationService.check_duplicate_order() was called
        mock_validation_service.check_duplicate_order.assert_called()
        assert summary["skipped"] > 0

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_uses_order_validation_service_volume_ratio(self, mock_auth):
        """Test that retry uses OrderValidationService.check_volume_ratio()"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock OrderValidationService
        mock_validation_service = Mock()
        mock_validation_service.check_portfolio_capacity = Mock(
            return_value=(True, 5, 10)
        )
        mock_validation_service.check_duplicate_order = Mock(
            return_value=(False, None)
        )
        mock_validation_service.check_volume_ratio = Mock(
            return_value=(False, 0.5, "Rs 500+ (10%)")  # Invalid volume ratio
        )

        # Mock PortfolioService
        mock_portfolio_service = Mock()
        mock_portfolio_service.get_portfolio_count = Mock(return_value=5)
        mock_validation_service.portfolio_service = mock_portfolio_service

        # Mock IndicatorService
        mock_indicator_service = Mock()
        mock_indicator_service.get_daily_indicators_dict = Mock(
            return_value={
                "close": 2500.0,
                "rsi10": 25.0,
                "ema9": 2480.0,
                "ema200": 2400.0,
                "avg_volume": 1000.0,  # Low volume
            }
        )

        # Mock order
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        mock_order = Mock()
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.id = 1
        mock_order.status = DbOrderStatus.FAILED

        # Mock orders repository
        mock_orders_repo = Mock()
        mock_orders_repo.get_retriable_failed_orders = Mock(return_value=[mock_order])
        mock_orders_repo.list = Mock(return_value=[])
        mock_orders_repo.mark_failed = Mock()

        # Create engine instance
        engine = AutoTradeEngine(env_file="test.env", user_id=1)
        engine.order_validation_service = mock_validation_service
        engine.portfolio_service = mock_portfolio_service
        engine.indicator_service = mock_indicator_service
        engine.orders_repo = mock_orders_repo

        summary = engine.retry_pending_orders_from_db()

        # Verify OrderValidationService.check_volume_ratio() was called
        mock_validation_service.check_volume_ratio.assert_called()
        assert summary["skipped"] > 0


class TestOrderValidationServiceBackwardCompatibility:
    """Test backward compatibility after OrderValidationService migration"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_place_new_entries_summary_structure_unchanged(self, mock_auth):
        """Test that place_new_entries() summary structure remains unchanged"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Create engine
        engine = AutoTradeEngine(env_file="test.env", user_id=1)
        engine.portfolio = Mock()
        engine.portfolio.get_holdings = Mock(return_value={"data": []})
        engine.orders = Mock()
        engine.orders.get_pending_orders = Mock(return_value=[])

        # Mock recommendation
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        rec = Recommendation(
            ticker="RELIANCE.NS",
            verdict="buy",
            last_close=2500.0,
            execution_capital=50000.0,
        )

        summary = engine.place_new_entries([rec])

        # Verify summary structure is unchanged
        assert isinstance(summary, dict)
        assert "attempted" in summary
        assert "placed" in summary
        assert "failed_balance" in summary
        assert "skipped_portfolio_limit" in summary
        assert "skipped_duplicates" in summary
        assert "skipped_missing_data" in summary
        assert "skipped_invalid_qty" in summary
        assert "ticker_attempts" in summary

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_pending_orders_from_db_summary_structure_unchanged(self, mock_auth):
        """Test that retry_pending_orders_from_db() summary structure remains unchanged"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock orders repository
        mock_orders_repo = Mock()
        mock_orders_repo.get_retriable_failed_orders = Mock(return_value=[])

        # Create engine
        engine = AutoTradeEngine(env_file="test.env", user_id=1)
        engine.orders_repo = mock_orders_repo

        summary = engine.retry_pending_orders_from_db()

        # Verify summary structure is unchanged
        assert isinstance(summary, dict)
        assert "retried" in summary
        assert "placed" in summary
        assert "failed" in summary
        assert "skipped" in summary

