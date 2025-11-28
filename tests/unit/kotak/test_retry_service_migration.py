"""
Unit tests for Pre-market Retry service migration

Tests verify the migration to use IndicatorService
while maintaining backward compatibility.
"""

from unittest.mock import Mock, patch

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine


class TestRetryServiceIndicatorServiceIntegration:
    """Test that retry_pending_orders_from_db uses IndicatorService correctly"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_uses_indicator_service(self, mock_auth):
        """Test that retry_pending_orders_from_db() uses IndicatorService"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

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

        # Mock orders repository
        mock_orders_repo = Mock()
        mock_orders_repo.get_retriable_failed_orders = Mock(return_value=[])

        # Create engine instance
        engine = AutoTradeEngine(env_file="test.env")
        engine.indicator_service = mock_indicator_service
        engine.orders_repo = mock_orders_repo
        engine.user_id = 1

        # Call retry method
        summary = engine.retry_pending_orders_from_db()

        # Verify summary structure
        assert summary is not None
        assert "retried" in summary
        assert "placed" in summary
        assert "failed" in summary
        assert "skipped" in summary

        # Verify no orders to retry (empty list)
        assert summary["retried"] == 0

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_calls_indicator_service_with_correct_params(self, mock_auth):
        """Test that retry calls IndicatorService with correct parameters"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

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
        mock_order = Mock()
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.id = 1

        # Mock orders repository
        mock_orders_repo = Mock()
        mock_orders_repo.get_retriable_failed_orders = Mock(return_value=[mock_order])
        mock_orders_repo.list = Mock(return_value=[])
        mock_orders_repo.mark_cancelled = Mock()
        mock_orders_repo.mark_failed = Mock()
        mock_orders_repo.update = Mock()

        # Create engine instance
        engine = AutoTradeEngine(env_file="test.env")
        engine.indicator_service = mock_indicator_service
        engine.orders_repo = mock_orders_repo
        engine.user_id = 1

        # Stub OrderValidationService interactions
        engine.order_validation_service = Mock()
        engine.order_validation_service.check_portfolio_capacity.return_value = (
            True,
            0,
            engine.strategy_config.max_portfolio_size,
        )
        engine.order_validation_service.check_duplicate_order.return_value = (False, "")
        engine.order_validation_service.check_volume_ratio.return_value = (True, 0.1, {})

        # Mock other dependencies
        engine.current_symbols_in_portfolio = Mock(return_value=[])
        engine.portfolio_size = Mock(return_value=0)
        engine.has_holding = Mock(return_value=False)
        engine.has_active_buy_order = Mock(return_value=False)
        engine._symbol_variants = Mock(return_value=["RELIANCE"])
        engine.orders = Mock()
        engine.orders.cancel_pending_buys_for_symbol = Mock(return_value=0)
        engine.check_position_volume_ratio = Mock(return_value=True)
        engine.get_affordable_qty = Mock(return_value=100)
        engine.get_available_cash = Mock(return_value=100000.0)
        engine._calculate_execution_capital = Mock(return_value=50000.0)
        engine._check_for_manual_orders = Mock(return_value={"has_manual_order": False})
        engine._attempt_place_order = Mock(return_value=(False, None))

        # Call retry method
        engine.retry_pending_orders_from_db()

        # Verify IndicatorService was called with correct parameters
        mock_indicator_service.get_daily_indicators_dict.assert_called_once()
        call_args = mock_indicator_service.get_daily_indicators_dict.call_args
        assert call_args[1]["ticker"] == "RELIANCE.NS"
        assert call_args[1]["rsi_period"] is None
        assert call_args[1]["config"] == engine.strategy_config

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_handles_missing_indicators(self, mock_auth):
        """Test that retry handles None or missing indicators correctly"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock IndicatorService to return None
        mock_indicator_service = Mock()
        mock_indicator_service.get_daily_indicators_dict = Mock(return_value=None)

        # Mock order
        mock_order = Mock()
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.id = 1

        # Mock orders repository
        mock_orders_repo = Mock()
        mock_orders_repo.get_retriable_failed_orders = Mock(return_value=[mock_order])
        mock_orders_repo.list = Mock(return_value=[])

        # Create engine instance
        engine = AutoTradeEngine(env_file="test.env")
        engine.indicator_service = mock_indicator_service
        engine.orders_repo = mock_orders_repo
        engine.user_id = 1

        # Stub OrderValidationService interactions
        engine.order_validation_service = Mock()
        engine.order_validation_service.check_portfolio_capacity.return_value = (
            True,
            0,
            engine.strategy_config.max_portfolio_size,
        )
        engine.order_validation_service.check_duplicate_order.return_value = (False, "")
        engine.order_validation_service.check_volume_ratio.return_value = (True, 0.1, {})

        # Mock other dependencies
        engine.current_symbols_in_portfolio = Mock(return_value=[])
        engine.portfolio_size = Mock(return_value=0)
        engine.has_holding = Mock(return_value=False)

        # Call retry method
        summary = engine.retry_pending_orders_from_db()

        # Verify order was skipped due to missing indicators
        assert summary["retried"] == 1
        assert summary["skipped"] == 1
        assert summary["placed"] == 0

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_handles_incomplete_indicators(self, mock_auth):
        """Test that retry handles incomplete indicators (missing keys) correctly"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock IndicatorService to return incomplete indicators
        mock_indicator_service = Mock()
        mock_indicator_service.get_daily_indicators_dict = Mock(
            return_value={"close": 2500.0}  # Missing rsi10, ema9, ema200
        )

        # Mock order
        mock_order = Mock()
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.id = 1

        # Mock orders repository
        mock_orders_repo = Mock()
        mock_orders_repo.get_retriable_failed_orders = Mock(return_value=[mock_order])
        mock_orders_repo.list = Mock(return_value=[])

        # Create engine instance
        engine = AutoTradeEngine(env_file="test.env")
        engine.indicator_service = mock_indicator_service
        engine.orders_repo = mock_orders_repo
        engine.user_id = 1

        # Stub OrderValidationService interactions
        engine.order_validation_service = Mock()
        engine.order_validation_service.check_portfolio_capacity.return_value = (
            True,
            0,
            engine.strategy_config.max_portfolio_size,
        )
        engine.order_validation_service.check_duplicate_order.return_value = (False, "")
        engine.order_validation_service.check_volume_ratio.return_value = (True, 0.1, {})

        # Stub OrderValidationService interactions
        engine.order_validation_service = Mock()
        engine.order_validation_service.check_portfolio_capacity.return_value = (
            True,
            0,
            engine.strategy_config.max_portfolio_size,
        )
        engine.order_validation_service.check_duplicate_order.return_value = (False, "")
        engine.order_validation_service.check_volume_ratio.return_value = (True, 0.1, {})

        # Mock other dependencies
        engine.current_symbols_in_portfolio = Mock(return_value=[])
        engine.portfolio_size = Mock(return_value=0)
        engine.has_holding = Mock(return_value=False)

        # Call retry method
        summary = engine.retry_pending_orders_from_db()

        # Verify order was skipped due to incomplete indicators
        assert summary["retried"] == 1
        assert summary["skipped"] == 1
        assert summary["placed"] == 0

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_uses_strategy_config(self, mock_auth):
        """Test that retry uses engine's strategy_config"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock strategy config
        mock_strategy_config = Mock()
        mock_strategy_config.max_portfolio_size = 10

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
        mock_order = Mock()
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.id = 1

        # Mock orders repository
        mock_orders_repo = Mock()
        mock_orders_repo.get_retriable_failed_orders = Mock(return_value=[mock_order])
        mock_orders_repo.list = Mock(return_value=[])
        mock_orders_repo.mark_cancelled = Mock()
        mock_orders_repo.mark_failed = Mock()
        mock_orders_repo.update = Mock()

        # Create engine instance
        engine = AutoTradeEngine(env_file="test.env")
        engine.indicator_service = mock_indicator_service
        engine.orders_repo = mock_orders_repo
        engine.user_id = 1
        engine.strategy_config = mock_strategy_config

        # Stub OrderValidationService interactions
        engine.order_validation_service = Mock()
        engine.order_validation_service.check_portfolio_capacity.return_value = (
            True,
            0,
            mock_strategy_config.max_portfolio_size,
        )
        engine.order_validation_service.check_duplicate_order.return_value = (False, "")
        engine.order_validation_service.check_volume_ratio.return_value = (True, 0.1, {})

        # Mock other dependencies
        engine.current_symbols_in_portfolio = Mock(return_value=[])
        engine.portfolio_size = Mock(return_value=0)
        engine.has_holding = Mock(return_value=False)
        engine.has_active_buy_order = Mock(return_value=False)
        engine._symbol_variants = Mock(return_value=["RELIANCE"])
        engine.orders = Mock()
        engine.orders.cancel_pending_buys_for_symbol = Mock(return_value=0)
        engine.check_position_volume_ratio = Mock(return_value=True)
        engine.get_affordable_qty = Mock(return_value=100)
        engine.get_available_cash = Mock(return_value=100000.0)
        engine._calculate_execution_capital = Mock(return_value=50000.0)
        engine._check_for_manual_orders = Mock(return_value={"has_manual_order": False})
        engine._attempt_place_order = Mock(return_value=(False, None))

        # Call retry method
        engine.retry_pending_orders_from_db()

        # Verify IndicatorService was called with engine's strategy_config
        call_args = mock_indicator_service.get_daily_indicators_dict.call_args
        assert call_args[1]["config"] == mock_strategy_config


class TestRetryServiceBackwardCompatibility:
    """Test that retry maintains backward compatibility"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_summary_structure_unchanged(self, mock_auth):
        """Test that retry summary structure remains unchanged"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock orders repository
        mock_orders_repo = Mock()
        mock_orders_repo.get_retriable_failed_orders = Mock(return_value=[])

        # Create engine instance
        engine = AutoTradeEngine(env_file="test.env")
        engine.orders_repo = mock_orders_repo
        engine.user_id = 1

        # Call retry method
        summary = engine.retry_pending_orders_from_db()

        # Verify summary structure matches original
        assert isinstance(summary, dict)
        assert "retried" in summary
        assert "placed" in summary
        assert "failed" in summary
        assert "skipped" in summary
        assert all(isinstance(v, int) for v in summary.values())

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_handles_no_orders(self, mock_auth):
        """Test that retry handles no orders correctly"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock orders repository
        mock_orders_repo = Mock()
        mock_orders_repo.get_retriable_failed_orders = Mock(return_value=[])

        # Create engine instance
        engine = AutoTradeEngine(env_file="test.env")
        engine.orders_repo = mock_orders_repo
        engine.user_id = 1

        # Call retry method
        summary = engine.retry_pending_orders_from_db()

        # Verify all counts are zero
        assert summary["retried"] == 0
        assert summary["placed"] == 0
        assert summary["failed"] == 0
        assert summary["skipped"] == 0

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_handles_no_repo(self, mock_auth):
        """Test that retry handles missing repository gracefully"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Create engine instance without repository
        engine = AutoTradeEngine(env_file="test.env")
        engine.orders_repo = None
        engine.user_id = 1

        # Call retry method
        summary = engine.retry_pending_orders_from_db()

        # Verify summary is returned with zero counts
        assert summary is not None
        assert summary["retried"] == 0
        assert summary["placed"] == 0
        assert summary["failed"] == 0
        assert summary["skipped"] == 0
