"""
Tests for holdings API in SellOrderManager.

Tests that holdings are fetched correctly and reused from monitoring cycles.
Cache mechanism has been removed - holdings are fetched when needed and
reused from monitoring cycles instead.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest  # noqa: E402

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager  # noqa: E402


class TestHoldingsAPI:
    """Test holdings API functionality (cache removed, data reused from monitoring)."""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth."""
        return Mock()

    @pytest.fixture
    def mock_portfolio(self):
        """Mock KotakNeoPortfolio."""
        portfolio = Mock()
        portfolio.get_holdings = Mock()
        return portfolio

    @pytest.fixture
    def sell_manager(self, mock_auth, mock_portfolio):
        """Create SellOrderManager instance with mocks."""
        with patch(
            "modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio",
            return_value=mock_portfolio,
        ):
            manager = SellOrderManager(auth=mock_auth, history_path="test_history.json")
            manager.portfolio = mock_portfolio
            return manager

    def test_get_holdings_fetches_from_api(self, sell_manager, mock_portfolio):
        """Test that _get_holdings() fetches from API."""
        mock_holdings = {"data": [{"tradingSymbol": "RELIANCE-EQ", "quantity": 10}]}
        mock_portfolio.get_holdings.return_value = mock_holdings

        result = sell_manager._get_holdings()

        assert result == mock_holdings
        mock_portfolio.get_holdings.assert_called_once()

    def test_get_holdings_returns_none_when_api_fails(self, sell_manager, mock_portfolio):
        """Test that returns None when API fails."""
        mock_portfolio.get_holdings.side_effect = Exception("API Error")

        result = sell_manager._get_holdings()

        assert result is None

    def test_get_holdings_returns_none_when_portfolio_not_available(self, sell_manager):
        """Test that returns None when portfolio is not available."""
        sell_manager.portfolio = None

        result = sell_manager._get_holdings()

        assert result is None

    def test_get_holdings_handles_none_response(self, sell_manager, mock_portfolio):
        """Test that handles None response from API."""
        mock_portfolio.get_holdings.return_value = None

        result = sell_manager._get_holdings()

        assert result is None

    def test_get_holdings_handles_invalid_response(self, sell_manager, mock_portfolio):
        """Test that handles invalid response (not a dict) from API."""
        mock_portfolio.get_holdings.return_value = "invalid response"

        result = sell_manager._get_holdings()

        assert result == "invalid response"

    def test_reconcile_positions_with_broker_holdings_uses_provided_holdings(
        self, sell_manager, mock_portfolio
    ):
        """Test that _reconcile_positions_with_broker_holdings() uses provided holdings response."""
        from src.infrastructure.db.models import Positions

        mock_holdings = {"data": [{"tradingSymbol": "RELIANCE-EQ", "quantity": 5}]}

        # Create a position with more quantity than broker (manual sell detected)
        position = Positions(
            user_id=1,
            symbol="RELIANCE",
            quantity=10.0,
            avg_price=100.0,
        )
        sell_manager.positions_repo = Mock()
        sell_manager.positions_repo.list = Mock(return_value=[position])
        sell_manager.user_id = 1

        # Call with provided holdings response
        with patch(
            "modules.kotak_neo_auto_trader.sell_engine.extract_base_symbol", return_value="RELIANCE"
        ):
            result = sell_manager._reconcile_positions_with_broker_holdings(mock_holdings)

        # Should detect mismatch and update position
        assert result["checked"] == 1
        # Should not call portfolio.get_holdings() since we provided the response
        mock_portfolio.get_holdings.assert_not_called()

    def test_reconcile_positions_with_broker_holdings_fetches_when_not_provided(
        self, sell_manager, mock_portfolio
    ):
        """Test that _reconcile_positions_with_broker_holdings() fetches holdings when not provided."""
        from src.infrastructure.db.models import Positions

        mock_holdings = {"data": [{"tradingSymbol": "RELIANCE-EQ", "quantity": 10}]}
        mock_portfolio.get_holdings.return_value = mock_holdings

        # Create a position
        position = Positions(
            user_id=1,
            symbol="RELIANCE",
            quantity=10.0,
            avg_price=100.0,
        )
        sell_manager.positions_repo = Mock()
        sell_manager.positions_repo.list = Mock(return_value=[position])
        sell_manager.user_id = 1

        # Call without providing holdings response
        with patch(
            "modules.kotak_neo_auto_trader.sell_engine.extract_base_symbol", return_value="RELIANCE"
        ):
            result = sell_manager._reconcile_positions_with_broker_holdings(None)

        # Should fetch from API
        mock_portfolio.get_holdings.assert_called_once()
        assert result["checked"] == 1

    def test_reconcile_single_symbol_uses_provided_holdings(self, sell_manager, mock_portfolio):
        """Test that _reconcile_single_symbol() uses provided holdings response."""
        from src.infrastructure.db.models import Positions

        mock_holdings = {"data": [{"tradingSymbol": "RELIANCE-EQ", "quantity": 5}]}

        # Create a position with more quantity than broker (manual sell detected)
        position = Positions(
            user_id=1,
            symbol="RELIANCE",
            quantity=10.0,
            avg_price=100.0,
        )
        sell_manager.positions_repo = Mock()
        sell_manager.positions_repo.get_by_symbol_for_update = Mock(return_value=position)
        sell_manager.user_id = 1

        # Call with provided holdings response
        with patch(
            "modules.kotak_neo_auto_trader.sell_engine.extract_base_symbol", return_value="RELIANCE"
        ):
            result = sell_manager._reconcile_single_symbol("RELIANCE", mock_holdings)

        # Should detect mismatch and update position
        assert result is True
        # Should not call portfolio.get_holdings() since we provided the response
        mock_portfolio.get_holdings.assert_not_called()

    def test_reconcile_single_symbol_fetches_when_not_provided(self, sell_manager, mock_portfolio):
        """Test that _reconcile_single_symbol() fetches holdings when not provided."""
        from src.infrastructure.db.models import Positions

        mock_holdings = {"data": [{"tradingSymbol": "RELIANCE-EQ", "quantity": 10}]}
        mock_portfolio.get_holdings.return_value = mock_holdings

        # Create a position
        position = Positions(
            user_id=1,
            symbol="RELIANCE",
            quantity=10.0,
            avg_price=100.0,
        )
        sell_manager.positions_repo = Mock()
        sell_manager.positions_repo.get_by_symbol_for_update = Mock(return_value=position)
        sell_manager.user_id = 1

        # Call without providing holdings response
        with patch(
            "modules.kotak_neo_auto_trader.sell_engine.extract_base_symbol", return_value="RELIANCE"
        ):
            result = sell_manager._reconcile_single_symbol("RELIANCE", None)

        # Should fetch from API (only if position exists and is not closed)
        # Position exists and matches, so get_holdings should be called
        mock_portfolio.get_holdings.assert_called_once()
        assert isinstance(result, bool)

    def test_reconcile_single_symbol_handles_closed_position(self, sell_manager, mock_portfolio):
        """Test that _reconcile_single_symbol() handles closed positions."""
        from datetime import datetime

        from src.infrastructure.db.models import Positions

        # Create a closed position
        position = Positions(
            user_id=1,
            symbol="RELIANCE",
            quantity=10.0,
            avg_price=100.0,
            closed_at=datetime.now(),
        )
        sell_manager.positions_repo = Mock()
        sell_manager.positions_repo.get_by_symbol = Mock(return_value=position)
        sell_manager.user_id = 1

        # Should return False for closed position
        result = sell_manager._reconcile_single_symbol("RELIANCE", None)

        assert result is False
        # Should not call portfolio.get_holdings() for closed position
        mock_portfolio.get_holdings.assert_not_called()

    def test_reconcile_single_symbol_handles_missing_position(self, sell_manager, mock_portfolio):
        """Test that _reconcile_single_symbol() handles missing position."""
        sell_manager.positions_repo = Mock()
        sell_manager.positions_repo.get_by_symbol = Mock(return_value=None)
        sell_manager.user_id = 1

        # Should return False for missing position
        result = sell_manager._reconcile_single_symbol("RELIANCE", None)

        assert result is False
        # Should not call portfolio.get_holdings() for missing position
        mock_portfolio.get_holdings.assert_not_called()

    def test_get_open_positions_fetches_holdings(self, sell_manager, mock_portfolio):
        """Test that get_open_positions() fetches holdings for validation."""
        from src.infrastructure.db.models import Positions
        from src.infrastructure.db.timezone_utils import ist_now

        mock_holdings = {"data": [{"tradingSymbol": "RELIANCE-EQ", "quantity": 10}]}
        mock_portfolio.get_holdings.return_value = mock_holdings

        # Create a position with all required fields
        position = Positions(
            user_id=1,
            symbol="RELIANCE",
            quantity=10.0,
            avg_price=100.0,
            opened_at=ist_now(),  # Required field
        )
        sell_manager.positions_repo = Mock()
        sell_manager.positions_repo.list = Mock(return_value=[position])
        sell_manager.user_id = 1
        sell_manager.orders_repo = Mock()
        sell_manager.orders_repo.list = Mock(return_value=[])

        # Call get_open_positions
        with patch(
            "modules.kotak_neo_auto_trader.sell_engine.extract_base_symbol", return_value="RELIANCE"
        ):
            result = sell_manager.get_open_positions()

        # Should fetch holdings for validation
        mock_portfolio.get_holdings.assert_called_once()
        assert isinstance(result, list)
