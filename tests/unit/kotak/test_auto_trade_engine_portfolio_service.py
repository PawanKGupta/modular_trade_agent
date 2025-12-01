"""
Unit tests for AutoTradeEngine PortfolioService integration

Tests verify the migration to PortfolioService
while maintaining backward compatibility.
"""

from unittest.mock import Mock, patch

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine


class TestAutoTradeEnginePortfolioServiceInitialization:
    """Test AutoTradeEngine initialization with PortfolioService"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_init_with_portfolio_service(self, mock_auth):
        """Test that AutoTradeEngine initializes PortfolioService"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        engine = AutoTradeEngine(env_file="test.env")

        assert engine.portfolio_service is not None
        # Portfolio and orders are initialized but set to None initially (set after login)
        # The service itself should exist
        assert hasattr(engine.portfolio_service, "portfolio")
        assert hasattr(engine.portfolio_service, "orders")

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoOrders")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoPortfolio")
    def test_login_updates_portfolio_service(self, mock_portfolio, mock_orders, mock_auth):
        """Test that login() updates PortfolioService with portfolio and orders"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        mock_portfolio_instance = Mock()
        mock_orders_instance = Mock()
        mock_portfolio.return_value = mock_portfolio_instance
        mock_orders.return_value = mock_orders_instance

        engine = AutoTradeEngine(env_file="test.env")
        engine.login()

        assert engine.portfolio_service.portfolio == mock_portfolio_instance
        assert engine.portfolio_service.orders == mock_orders_instance


class TestAutoTradeEnginePortfolioServiceMethods:
    """Test AutoTradeEngine methods that delegate to PortfolioService"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoOrders")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoPortfolio")
    def test_has_holding_delegates_to_portfolio_service(
        self, mock_portfolio, mock_orders, mock_auth
    ):
        """Test that has_holding() delegates to PortfolioService.has_position()"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        mock_portfolio_instance = Mock()
        mock_orders_instance = Mock()
        mock_portfolio.return_value = mock_portfolio_instance
        mock_orders.return_value = mock_orders_instance

        engine = AutoTradeEngine(env_file="test.env")
        engine.login()

        # Mock PortfolioService.has_position()
        engine.portfolio_service.has_position = Mock(return_value=True)

        result = engine.has_holding("RELIANCE")

        assert result is True
        engine.portfolio_service.has_position.assert_called_once_with("RELIANCE")

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoOrders")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoPortfolio")
    def test_current_symbols_in_portfolio_delegates_to_portfolio_service(
        self, mock_portfolio, mock_orders, mock_auth
    ):
        """Test that current_symbols_in_portfolio() delegates to PortfolioService"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        mock_portfolio_instance = Mock()
        mock_orders_instance = Mock()
        mock_portfolio.return_value = mock_portfolio_instance
        mock_orders.return_value = mock_orders_instance

        engine = AutoTradeEngine(env_file="test.env")
        engine.login()

        # Mock PortfolioService.get_current_positions()
        expected_symbols = ["RELIANCE", "TCS", "INFY"]
        engine.portfolio_service.get_current_positions = Mock(return_value=expected_symbols)

        result = engine.current_symbols_in_portfolio()

        assert result == expected_symbols
        engine.portfolio_service.get_current_positions.assert_called_once_with(include_pending=True)

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoOrders")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoPortfolio")
    def test_portfolio_size_delegates_to_portfolio_service(
        self, mock_portfolio, mock_orders, mock_auth
    ):
        """Test that portfolio_size() delegates to PortfolioService.get_portfolio_count()"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        mock_portfolio_instance = Mock()
        mock_orders_instance = Mock()
        mock_portfolio.return_value = mock_portfolio_instance
        mock_orders.return_value = mock_orders_instance

        engine = AutoTradeEngine(env_file="test.env")
        engine.login()

        # Mock PortfolioService.get_portfolio_count()
        expected_count = 5
        engine.portfolio_service.get_portfolio_count = Mock(return_value=expected_count)

        result = engine.portfolio_size()

        assert result == expected_count
        engine.portfolio_service.get_portfolio_count.assert_called_once_with(include_pending=True)


class TestAutoTradeEnginePortfolioServiceBackwardCompatibility:
    """Test backward compatibility of portfolio-related methods"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoOrders")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoPortfolio")
    def test_has_holding_backward_compatibility(self, mock_portfolio, mock_orders, mock_auth):
        """Test that has_holding() maintains backward compatibility"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        mock_portfolio_instance = Mock()
        mock_orders_instance = Mock()
        mock_portfolio.return_value = mock_portfolio_instance
        mock_orders.return_value = mock_orders_instance

        engine = AutoTradeEngine(env_file="test.env")
        engine.login()

        # Mock PortfolioService to return False
        engine.portfolio_service.has_position = Mock(return_value=False)

        result = engine.has_holding("NONEXISTENT")

        assert result is False
        assert isinstance(result, bool)  # Return type unchanged

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoOrders")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoPortfolio")
    def test_current_symbols_in_portfolio_backward_compatibility(
        self, mock_portfolio, mock_orders, mock_auth
    ):
        """Test that current_symbols_in_portfolio() maintains backward compatibility"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        mock_portfolio_instance = Mock()
        mock_orders_instance = Mock()
        mock_portfolio.return_value = mock_portfolio_instance
        mock_orders.return_value = mock_orders_instance

        engine = AutoTradeEngine(env_file="test.env")
        engine.login()

        # Mock PortfolioService to return empty list
        engine.portfolio_service.get_current_positions = Mock(return_value=[])

        result = engine.current_symbols_in_portfolio()

        assert isinstance(result, list)
        assert result == []

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoOrders")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoPortfolio")
    def test_portfolio_size_backward_compatibility(self, mock_portfolio, mock_orders, mock_auth):
        """Test that portfolio_size() maintains backward compatibility"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        mock_portfolio_instance = Mock()
        mock_orders_instance = Mock()
        mock_portfolio.return_value = mock_portfolio_instance
        mock_orders.return_value = mock_orders_instance

        engine = AutoTradeEngine(env_file="test.env")
        engine.login()

        # Mock PortfolioService to return 0
        engine.portfolio_service.get_portfolio_count = Mock(return_value=0)

        result = engine.portfolio_size()

        assert isinstance(result, int)
        assert result == 0
