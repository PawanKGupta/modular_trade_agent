"""
Tests for holdings API retry logic and database fallback in place_new_entries.
"""

from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine, Recommendation


class TestHoldingsAPIRetryAndFallback:
    """Test holdings API retry logic and database fallback."""

    @pytest.fixture
    def mock_auth(self):
        """Create mock auth object."""
        auth = Mock()
        auth.is_authenticated.return_value = True
        auth.get_client.return_value = Mock()
        return auth

    @pytest.fixture
    def mock_orders(self):
        """Create mock orders object."""
        return Mock()

    @pytest.fixture
    def mock_portfolio(self):
        """Create mock portfolio object."""
        portfolio = Mock()
        portfolio.get_holdings.return_value = None
        return portfolio

    @pytest.fixture
    def engine(self, mock_auth, mock_orders, mock_portfolio):
        """Create AutoTradeEngine instance with mocks."""
        strategy_config = Mock()
        strategy_config.max_portfolio_size = 10  # Must be int, not Mock
        strategy_config.user_capital = 100000.0
        strategy_config.default_variety = "AMO"
        strategy_config.default_exchange = "NSE"
        strategy_config.default_product = "MIS"
        strategy_config.MIN_QTY = 1

        engine = AutoTradeEngine(
            auth=mock_auth, user_id=1, db_session=Mock(), strategy_config=strategy_config
        )
        engine.orders = mock_orders
        engine.portfolio = mock_portfolio
        engine.orders_repo = Mock()
        # Mock orders_repo.list() to return empty list by default
        engine.orders_repo.list.return_value = []
        engine.parse_symbol_for_broker = lambda ticker: ticker.split(".")[0]
        # Mock get_pending_orders to return empty list by default
        mock_orders.get_pending_orders.return_value = []
        # Mock other required methods
        engine.get_available_cash = Mock(return_value=200000.0)
        engine.get_affordable_qty = Mock(return_value=100)
        return engine

    @pytest.fixture
    def recommendations(self):
        """Create sample recommendations."""
        return [
            Recommendation(
                ticker="RELIANCE.NS",
                verdict="strong_buy",
                last_close=2450.0,
                execution_capital=None,
            )
        ]

    def test_holdings_api_success_on_first_attempt(self, engine, mock_portfolio, recommendations):
        """Test that holdings API success on first attempt proceeds normally."""
        # Mock portfolio.get_holdings to return proper dict structure
        mock_portfolio.get_holdings.return_value = {"data": []}

        # Mock portfolio_service methods (used during placement)
        engine.portfolio_service.get_current_positions = Mock(return_value=[])
        engine.portfolio_service.get_portfolio_count = Mock(return_value=0)
        engine.portfolio_service.check_portfolio_capacity = Mock(return_value=(True, 0, 10))
        engine.portfolio_service.has_position = Mock(return_value=False)

        # Mock OrderValidationService
        engine.order_validation_service.check_balance = Mock(return_value=(True, 200000.0, 100))
        engine.order_validation_service.check_portfolio_capacity = Mock(return_value=(True, 0, 10))
        engine.order_validation_service.check_duplicate_order = Mock(return_value=(False, None))
        engine.order_validation_service.check_volume_ratio = Mock(return_value=(True, 0.01, None))
        engine.order_validation_service.get_available_cash = Mock(return_value=200000.0)

        with (
            patch.object(engine, "_get_failed_orders", return_value=[]),
            patch.object(engine, "_attempt_place_order", return_value=(False, None)),
        ):
            result = engine.place_new_entries(recommendations)

            # get_holdings is called for pre-flight check
            assert mock_portfolio.get_holdings.called
            # Order was attempted but failed due to insufficient balance (mocked)
            # The test verifies that holdings API was called successfully
            assert "attempted" in result

    def test_holdings_api_retry_on_failure(self, engine, mock_portfolio, recommendations):
        """Test that holdings API retries up to 3 times on failure."""
        # First 2 attempts fail, 3rd succeeds
        # Provide enough values for all potential calls (pre-flight + retries + placement)
        mock_portfolio.get_holdings.side_effect = [
            None,
            None,
            {"data": []},
            {"data": []},
            {"data": []},
        ]

        # Mock portfolio_service methods (used during placement)
        engine.portfolio_service.get_current_positions = Mock(return_value=[])
        engine.portfolio_service.get_portfolio_count = Mock(return_value=0)
        engine.portfolio_service.check_portfolio_capacity = Mock(return_value=(True, 0, 10))
        engine.portfolio_service.has_position = Mock(return_value=False)

        # Mock OrderValidationService
        engine.order_validation_service.check_balance = Mock(return_value=(True, 200000.0, 100))
        engine.order_validation_service.check_portfolio_capacity = Mock(return_value=(True, 0, 10))
        engine.order_validation_service.check_duplicate_order = Mock(return_value=(False, None))
        engine.order_validation_service.check_volume_ratio = Mock(return_value=(True, 0.01, None))
        engine.order_validation_service.get_available_cash = Mock(return_value=200000.0)

        with (
            patch("time.sleep"),
            patch.object(engine, "_get_failed_orders", return_value=[]),
            patch.object(engine, "_attempt_place_order", return_value=(False, None)),
        ):
            result = engine.place_new_entries(recommendations)

            # Should retry at least 3 times (pre-flight + 2 retries)
            assert mock_portfolio.get_holdings.call_count >= 3

    def test_holdings_api_fallback_to_database_no_existing_orders(
        self, engine, mock_portfolio, recommendations, mock_auth
    ):
        """Test database fallback when holdings API fails and no existing orders."""
        mock_portfolio.get_holdings.return_value = None
        mock_db = Mock()
        mock_db.execute.return_value.fetchone.return_value = [0]  # No existing orders
        engine.db = mock_db
        engine.user_id = 1

        # Mock portfolio_service methods (used during placement)
        engine.portfolio_service.get_current_positions = Mock(return_value=[])
        engine.portfolio_service.get_portfolio_count = Mock(return_value=0)
        engine.portfolio_service.check_portfolio_capacity = Mock(return_value=(True, 0, 10))
        engine.portfolio_service.has_position = Mock(return_value=False)

        # Mock OrderValidationService
        engine.order_validation_service.check_balance = Mock(return_value=(True, 200000.0, 100))
        engine.order_validation_service.check_portfolio_capacity = Mock(return_value=(True, 0, 10))
        engine.order_validation_service.check_duplicate_order = Mock(return_value=(False, None))
        engine.order_validation_service.check_volume_ratio = Mock(return_value=(True, 0.01, None))
        engine.order_validation_service.get_available_cash = Mock(return_value=200000.0)

        with (
            patch("time.sleep"),
            patch.object(engine, "_get_failed_orders", return_value=[]),
            patch.object(engine, "_attempt_place_order", return_value=(False, None)),
        ):
            result = engine.place_new_entries(recommendations)

            # Should proceed with order placement (database fallback worked)
            assert mock_db.execute.called

    def test_holdings_api_fallback_to_database_with_existing_orders(
        self, engine, mock_portfolio, recommendations, mock_auth
    ):
        """Test database fallback aborts when existing orders found."""
        mock_portfolio.get_holdings.return_value = None
        mock_db = Mock()
        mock_db.execute.return_value.fetchone.return_value = [1]  # Existing order found
        engine.db = mock_db
        engine.user_id = 1

        with patch("time.sleep"):
            result = engine.place_new_entries(recommendations)

            # Should abort to prevent duplicates
            assert result["attempted"] == 0
            assert result["placed"] == 0
            assert mock_db.execute.called

    def test_holdings_api_failure_no_database_fallback(
        self, engine, mock_portfolio, recommendations
    ):
        """Test that system aborts when holdings API fails and no database available."""
        mock_portfolio.get_holdings.return_value = None
        engine.db = None  # No database available

        with patch("time.sleep"):
            result = engine.place_new_entries(recommendations)

            # Should abort
            assert result["attempted"] == 0
            assert result["placed"] == 0

    def test_holdings_api_2fa_gate_handling(self, engine, mock_portfolio, recommendations):
        """Test 2FA gate handling in holdings API response."""
        # First response requires 2FA, then success after re-login
        # Provide enough values for all potential calls
        mock_portfolio.get_holdings.side_effect = [
            {"error": "2FA_REQUIRED"},
            {"data": []},  # Success after re-login
            {"data": []},  # Additional calls during placement
            {"data": []},
        ]
        mock_auth = Mock()
        mock_auth.force_relogin.return_value = True
        engine.auth = mock_auth

        with (
            patch.object(engine, "_response_requires_2fa", return_value=True),
            patch.object(engine, "_get_failed_orders", return_value=[]),
            patch.object(engine, "has_holding", return_value=False),
            patch.object(engine, "_attempt_place_order", return_value=(False, None)),
        ):
            result = engine.place_new_entries(recommendations)

            # Should handle 2FA and proceed
            assert mock_portfolio.get_holdings.call_count >= 2

    def test_holdings_api_invalid_response_structure(self, engine, mock_portfolio, recommendations):
        """Test handling of invalid holdings API response structure."""
        mock_portfolio.get_holdings.return_value = {"invalid": "structure"}  # Missing 'data' field

        with patch("time.sleep"):
            result = engine.place_new_entries(recommendations)

            # Should abort due to invalid response
            assert result["attempted"] == 0
            assert result["placed"] == 0
