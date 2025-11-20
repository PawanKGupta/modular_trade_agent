"""
Tests for holdings API retry logic and database fallback in place_new_entries.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime

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
        engine = AutoTradeEngine(
            auth=mock_auth, user_id=1, db_session=Mock(), strategy_config=Mock()
        )
        engine.orders = mock_orders
        engine.portfolio = mock_portfolio
        engine.orders_repo = Mock()
        engine.parse_symbol_for_broker = lambda ticker: ticker.split(".")[0]
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
        mock_portfolio.get_holdings.return_value = {"data": []}

        with (
            patch.object(engine, "_get_failed_orders", return_value=[]),
            patch.object(engine, "has_holding", return_value=False),
            patch.object(engine, "_attempt_place_order", return_value=(False, None)),
        ):

            result = engine.place_new_entries(recommendations)

            assert mock_portfolio.get_holdings.call_count == 1
            assert result["attempted"] == 0  # No orders placed due to mock

    def test_holdings_api_retry_on_failure(self, engine, mock_portfolio, recommendations):
        """Test that holdings API retries up to 3 times on failure."""
        # First 2 attempts fail, 3rd succeeds
        mock_portfolio.get_holdings.side_effect = [None, None, {"data": []}]

        with (
            patch("time.sleep"),
            patch.object(engine, "_get_failed_orders", return_value=[]),
            patch.object(engine, "has_holding", return_value=False),
            patch.object(engine, "_attempt_place_order", return_value=(False, None)),
        ):

            result = engine.place_new_entries(recommendations)

            assert mock_portfolio.get_holdings.call_count == 3

    def test_holdings_api_fallback_to_database_no_existing_orders(
        self, engine, mock_portfolio, recommendations, mock_auth
    ):
        """Test database fallback when holdings API fails and no existing orders."""
        mock_portfolio.get_holdings.return_value = None
        mock_db = Mock()
        mock_db.execute.return_value.fetchone.return_value = [0]  # No existing orders
        engine.db = mock_db
        engine.user_id = 1

        with (
            patch("time.sleep"),
            patch.object(engine, "_get_failed_orders", return_value=[]),
            patch.object(engine, "has_holding", return_value=False),
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
        # First response requires 2FA
        mock_portfolio.get_holdings.side_effect = [
            {"error": "2FA_REQUIRED"},
            {"data": []},  # Success after re-login
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
