"""
Unit tests for Pre-market Retry service PortfolioService integration

Tests verify the migration to use PortfolioService
while maintaining backward compatibility.
"""

from unittest.mock import Mock, patch

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine


class TestRetryServicePortfolioServiceIntegration:
    """Test that retry_pending_orders_from_db uses PortfolioService correctly"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_uses_portfolio_service_for_capacity_check(self, mock_auth):
        """Test that retry uses PortfolioService.check_portfolio_capacity()"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock PortfolioService
        mock_portfolio_service = Mock()
        mock_portfolio_service.check_portfolio_capacity = Mock(
            return_value=(True, 5, 10)  # has_capacity, current_count, max_size
        )
        mock_portfolio_service.has_position = Mock(return_value=False)

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

        # Mock order (need at least one to trigger capacity check)
        mock_order = Mock()
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.id = 1

        # Mock orders repository
        mock_orders_repo = Mock()
        mock_orders_repo.get_retriable_failed_orders = Mock(return_value=[mock_order])
        mock_orders_repo.list = Mock(return_value=[])

        # Mock OrderValidationService (it delegates to PortfolioService)
        # Make check_portfolio_capacity delegate to portfolio_service
        mock_order_validation_service = Mock()
        mock_order_validation_service.portfolio_service = mock_portfolio_service
        mock_order_validation_service.check_portfolio_capacity = Mock(
            side_effect=lambda include_pending=True: mock_portfolio_service.check_portfolio_capacity(
                include_pending=include_pending
            )
        )
        mock_order_validation_service.check_duplicate_order = Mock(
            return_value=(False, None)  # not duplicate
        )
        mock_order_validation_service.check_balance = Mock(
            return_value=(True, 100000.0, 100)  # has_balance, available_cash, affordable_qty
        )
        mock_order_validation_service.check_volume_ratio = Mock(
            return_value=(True, 0.01, None)  # is_valid, volume_ratio, tier_info
        )

        # Create engine instance
        engine = AutoTradeEngine(env_file="test.env")
        engine.portfolio_service = mock_portfolio_service
        engine.indicator_service = mock_indicator_service
        engine.order_validation_service = mock_order_validation_service
        engine.orders_repo = mock_orders_repo
        engine.user_id = 1

        # Mock strategy config
        engine.strategy_config = Mock()
        engine.strategy_config.max_portfolio_size = 10

        # Mock other dependencies
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
        summary = engine.retry_pending_orders_from_db()

        # Verify OrderValidationService was called (which delegates to PortfolioService)
        mock_order_validation_service.check_portfolio_capacity.assert_called_once_with(
            include_pending=True
        )
        # Verify PortfolioService was called through OrderValidationService
        mock_portfolio_service.check_portfolio_capacity.assert_called_once_with(
            include_pending=True
        )

        # Verify summary structure
        assert summary is not None
        assert "retried" in summary
        assert "placed" in summary
        assert "failed" in summary
        assert "skipped" in summary

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_respects_portfolio_capacity_limit(self, mock_auth):
        """Test that retry skips orders when portfolio capacity is reached"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock PortfolioService - portfolio at capacity
        mock_portfolio_service = Mock()
        mock_portfolio_service.check_portfolio_capacity = Mock(
            return_value=(False, 10, 10)  # no capacity, at limit
        )

        # Mock order
        mock_order1 = Mock()
        mock_order1.symbol = "RELIANCE"
        mock_order1.id = 1

        mock_order2 = Mock()
        mock_order2.symbol = "TCS"
        mock_order2.id = 2

        # Mock orders repository
        mock_orders_repo = Mock()
        mock_orders_repo.get_retriable_failed_orders = Mock(return_value=[mock_order1, mock_order2])
        mock_orders_repo.list = Mock(return_value=[])

        # Mock OrderValidationService (it delegates to PortfolioService)
        # Make check_portfolio_capacity delegate to portfolio_service
        mock_order_validation_service = Mock()
        mock_order_validation_service.portfolio_service = mock_portfolio_service
        mock_order_validation_service.check_portfolio_capacity = Mock(
            side_effect=lambda include_pending=True: mock_portfolio_service.check_portfolio_capacity(
                include_pending=include_pending
            )
        )

        # Create engine instance
        engine = AutoTradeEngine(env_file="test.env")
        engine.portfolio_service = mock_portfolio_service
        engine.order_validation_service = mock_order_validation_service
        engine.orders_repo = mock_orders_repo
        engine.user_id = 1

        # Mock strategy config
        engine.strategy_config = Mock()
        engine.strategy_config.max_portfolio_size = 10

        # Call retry method
        summary = engine.retry_pending_orders_from_db()

        # Verify OrderValidationService was called (which delegates to PortfolioService)
        mock_order_validation_service.check_portfolio_capacity.assert_called_once_with(
            include_pending=True
        )
        # Verify PortfolioService was called through OrderValidationService
        mock_portfolio_service.check_portfolio_capacity.assert_called_once_with(
            include_pending=True
        )

        # Verify orders were skipped due to capacity
        # Note: retried is incremented before capacity check, so first order is retried=1
        # but then capacity check causes break, so skipped = remaining orders
        assert summary["skipped"] == 2  # Both orders skipped (1 retried + 1 remaining)
        assert summary["retried"] == 1  # First order increments retried before capacity check

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_uses_portfolio_service_for_holdings_check(self, mock_auth):
        """Test that retry uses PortfolioService via has_holding() for duplicate check"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock PortfolioService
        mock_portfolio_service = Mock()
        mock_portfolio_service.check_portfolio_capacity = Mock(
            return_value=(True, 5, 10)  # has capacity
        )
        mock_portfolio_service.has_position = Mock(return_value=True)  # Already in holdings

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

        # Mock OrderValidationService (it uses PortfolioService for duplicate checks)
        # Make check_portfolio_capacity and check_duplicate_order delegate to portfolio_service
        mock_order_validation_service = Mock()
        mock_order_validation_service.portfolio_service = mock_portfolio_service
        mock_order_validation_service.check_portfolio_capacity = Mock(
            side_effect=lambda include_pending=True: mock_portfolio_service.check_portfolio_capacity(
                include_pending=include_pending
            )
        )
        # Make check_duplicate_order call portfolio_service.has_position
        mock_order_validation_service.check_duplicate_order = Mock(
            side_effect=lambda symbol, **kwargs: (
                mock_portfolio_service.has_position(symbol),
                (
                    "Already in holdings: " + symbol
                    if mock_portfolio_service.has_position(symbol)
                    else None
                ),
            )
        )

        # Create engine instance
        engine = AutoTradeEngine(env_file="test.env")
        engine.portfolio_service = mock_portfolio_service
        engine.indicator_service = mock_indicator_service
        engine.order_validation_service = mock_order_validation_service
        engine.orders_repo = mock_orders_repo
        engine.user_id = 1

        # Mock strategy config
        engine.strategy_config = Mock()
        engine.strategy_config.max_portfolio_size = 10

        # Mock orders_repo.mark_cancelled
        engine.orders_repo.mark_cancelled = Mock()

        # Mock other dependencies
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
        summary = engine.retry_pending_orders_from_db()

        # Verify OrderValidationService.check_duplicate_order was called (which uses PortfolioService.has_position)
        mock_order_validation_service.check_duplicate_order.assert_called_once_with(
            "RELIANCE", check_active_buy_order=True, check_holdings=True
        )
        # Verify PortfolioService.has_position was called through OrderValidationService
        # Note: It may be called multiple times (once in duplicate check, possibly elsewhere)
        assert mock_portfolio_service.has_position.called
        assert mock_portfolio_service.has_position.call_count >= 1
        # Verify it was called with the correct symbol
        assert any(
            call[0][0] == "RELIANCE" for call in mock_portfolio_service.has_position.call_args_list
        )

        # Verify order was skipped (already in holdings)
        assert summary["retried"] == 1
        assert summary["placed"] == 0  # Skipped due to duplicate

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_updates_portfolio_service_before_check(self, mock_auth):
        """Test that retry updates PortfolioService with portfolio/orders before checks"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock portfolio and orders
        mock_portfolio = Mock()
        mock_orders = Mock()

        # Mock PortfolioService
        mock_portfolio_service = Mock()
        mock_portfolio_service.portfolio = None
        mock_portfolio_service.orders = None
        mock_portfolio_service.check_portfolio_capacity = Mock(return_value=(True, 5, 10))
        mock_portfolio_service.has_position = Mock(return_value=False)

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

        # Mock order (need at least one to trigger update)
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
        engine.portfolio_service = mock_portfolio_service
        engine.portfolio = mock_portfolio
        engine.orders = mock_orders
        engine.indicator_service = mock_indicator_service
        engine.orders_repo = mock_orders_repo
        engine.user_id = 1

        # Mock other dependencies
        engine.has_active_buy_order = Mock(return_value=False)
        engine._symbol_variants = Mock(return_value=["RELIANCE"])
        # Don't overwrite engine.orders - use the mock_orders we set above
        mock_orders.cancel_pending_buys_for_symbol = Mock(return_value=0)
        engine.check_position_volume_ratio = Mock(return_value=True)
        engine.get_affordable_qty = Mock(return_value=100)
        engine.get_available_cash = Mock(return_value=100000.0)
        engine._calculate_execution_capital = Mock(return_value=50000.0)
        engine._check_for_manual_orders = Mock(return_value={"has_manual_order": False})
        engine._attempt_place_order = Mock(return_value=(False, None))

        # Call retry method
        engine.retry_pending_orders_from_db()

        # Verify PortfolioService was updated
        assert mock_portfolio_service.portfolio == mock_portfolio
        assert mock_portfolio_service.orders == mock_orders


class TestRetryServicePortfolioServiceBackwardCompatibility:
    """Test backward compatibility of retry service with PortfolioService"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_summary_structure_unchanged(self, mock_auth):
        """Test that retry summary structure remains unchanged"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock PortfolioService
        mock_portfolio_service = Mock()
        mock_portfolio_service.check_portfolio_capacity = Mock(return_value=(True, 5, 10))
        mock_portfolio_service.has_position = Mock(return_value=False)

        # Mock orders repository
        mock_orders_repo = Mock()
        mock_orders_repo.get_retriable_failed_orders = Mock(return_value=[])

        # Create engine instance
        engine = AutoTradeEngine(env_file="test.env")
        engine.portfolio_service = mock_portfolio_service
        engine.orders_repo = mock_orders_repo
        engine.user_id = 1

        # Call retry method
        summary = engine.retry_pending_orders_from_db()

        # Verify summary structure (backward compatibility)
        assert isinstance(summary, dict)
        assert "retried" in summary
        assert "placed" in summary
        assert "failed" in summary
        assert "skipped" in summary
        assert all(isinstance(v, int) for v in summary.values())
