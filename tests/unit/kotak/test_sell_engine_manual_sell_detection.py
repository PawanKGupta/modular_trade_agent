"""
Tests for manual sell detection and positions table reconciliation.

Edge Cases #14, #15, #17: Manual sell detection and positions table updates.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest  # noqa: E402

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager  # noqa: E402
from src.infrastructure.db.models import Positions  # noqa: E402


class TestManualSellDetection:
    """Test manual sell detection and positions table reconciliation."""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth."""
        return Mock()

    @pytest.fixture
    def mock_positions_repo(self):
        """Mock PositionsRepository."""
        repo = Mock()
        return repo

    @pytest.fixture
    def mock_portfolio(self):
        """Mock KotakNeoPortfolio."""
        portfolio = Mock()
        return portfolio

    @pytest.fixture
    def sell_manager(self, mock_auth, mock_positions_repo, mock_portfolio):
        """Create SellOrderManager instance with mocks."""
        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio", return_value=mock_portfolio):
            manager = SellOrderManager(
                auth=mock_auth,
                positions_repo=mock_positions_repo,
                user_id=1,
            )
            manager.portfolio = mock_portfolio
            return manager

    def test_reconcile_manual_full_sell(self, sell_manager, mock_positions_repo, mock_portfolio):
        """Test reconciliation detects manual full sell and marks position as closed."""
        # Setup: Position in DB shows 35 shares, broker has 0
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE"
        position.quantity = 35.0
        position.closed_at = None

        mock_positions_repo.list.return_value = [position]
        mock_positions_repo.get_by_symbol.return_value = position

        # Broker holdings: 0 shares (manual full sell)
        mock_portfolio.get_holdings.return_value = {"data": []}

        # Execute reconciliation
        stats = sell_manager._reconcile_positions_with_broker_holdings()

        # Verify: Position marked as closed
        assert stats["checked"] == 1
        assert stats["closed"] == 1
        assert stats["updated"] == 0
        assert stats["ignored"] == 0
        mock_positions_repo.mark_closed.assert_called_once()
        call_args = mock_positions_repo.mark_closed.call_args
        assert call_args.kwargs["user_id"] == 1
        assert call_args.kwargs["symbol"] == "RELIANCE"

    def test_reconcile_manual_partial_sell(self, sell_manager, mock_positions_repo, mock_portfolio):
        """Test reconciliation detects manual partial sell and reduces quantity."""
        # Setup: Position in DB shows 35 shares, broker has 30
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE"
        position.quantity = 35.0
        position.closed_at = None

        mock_positions_repo.list.return_value = [position]

        # Broker holdings: 30 shares (manual partial sell of 5)
        mock_portfolio.get_holdings.return_value = {
            "data": [
                {
                    "tradingSymbol": "RELIANCE-EQ",
                    "quantity": 30,
                }
            ]
        }

        # Execute reconciliation
        stats = sell_manager._reconcile_positions_with_broker_holdings()

        # Verify: Position quantity reduced
        assert stats["checked"] == 1
        assert stats["updated"] == 1
        assert stats["closed"] == 0
        assert stats["ignored"] == 0
        mock_positions_repo.reduce_quantity.assert_called_once()
        call_args = mock_positions_repo.reduce_quantity.call_args
        assert call_args.kwargs["user_id"] == 1
        assert call_args.kwargs["symbol"] == "RELIANCE"
        assert call_args.kwargs["sold_quantity"] == 5.0

    def test_reconcile_manual_buy_ignored(self, sell_manager, mock_positions_repo, mock_portfolio):
        """Test reconciliation ignores manual buys (broker_qty > positions_qty)."""
        # Setup: Position in DB shows 35 shares, broker has 45
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE"
        position.quantity = 35.0
        position.closed_at = None

        mock_positions_repo.list.return_value = [position]

        # Broker holdings: 45 shares (manual buy of 10)
        mock_portfolio.get_holdings.return_value = {
            "data": [
                {
                    "tradingSymbol": "RELIANCE-EQ",
                    "quantity": 45,
                }
            ]
        }

        # Execute reconciliation
        stats = sell_manager._reconcile_positions_with_broker_holdings()

        # Verify: Manual buy ignored, no updates
        assert stats["checked"] == 1
        assert stats["ignored"] == 1
        assert stats["updated"] == 0
        assert stats["closed"] == 0
        mock_positions_repo.reduce_quantity.assert_not_called()
        mock_positions_repo.mark_closed.assert_not_called()

    def test_reconcile_perfect_match(self, sell_manager, mock_positions_repo, mock_portfolio):
        """Test reconciliation when positions match broker holdings."""
        # Setup: Position in DB shows 35 shares, broker has 35
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE"
        position.quantity = 35.0
        position.closed_at = None

        mock_positions_repo.list.return_value = [position]

        # Broker holdings: 35 shares (perfect match)
        mock_portfolio.get_holdings.return_value = {
            "data": [
                {
                    "tradingSymbol": "RELIANCE-EQ",
                    "quantity": 35,
                }
            ]
        }

        # Execute reconciliation
        stats = sell_manager._reconcile_positions_with_broker_holdings()

        # Verify: No updates needed
        assert stats["checked"] == 1
        assert stats["updated"] == 0
        assert stats["closed"] == 0
        assert stats["ignored"] == 0
        mock_positions_repo.reduce_quantity.assert_not_called()
        mock_positions_repo.mark_closed.assert_not_called()

    def test_get_open_positions_validates_quantity(self, sell_manager, mock_positions_repo, mock_portfolio):
        """Test get_open_positions uses min(positions_qty, broker_qty) for sell orders."""
        # Setup: Position in DB shows 35 shares, broker has 30
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE"
        position.quantity = 35.0
        position.avg_price = 2500.0
        position.opened_at = Mock()
        position.opened_at.isoformat.return_value = "2025-01-01T00:00:00"
        position.closed_at = None

        mock_positions_repo.list.return_value = [position]

        # Broker holdings: 30 shares (less than positions table)
        mock_portfolio.get_holdings.return_value = {
            "data": [
                {
                    "tradingSymbol": "RELIANCE-EQ",
                    "quantity": 30,
                }
            ]
        }

        # Execute
        open_positions = sell_manager.get_open_positions()

        # Verify: Uses min(35, 30) = 30 for sell order quantity
        assert len(open_positions) == 1
        assert open_positions[0]["symbol"] == "RELIANCE"
        assert open_positions[0]["qty"] == 30  # Uses broker_qty (30), not positions_qty (35)

    def test_get_open_positions_uses_positions_qty_when_broker_more(self, sell_manager, mock_positions_repo, mock_portfolio):
        """Test get_open_positions uses positions_qty when broker has more (manual buy ignored)."""
        # Setup: Position in DB shows 35 shares, broker has 45
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE"
        position.quantity = 35.0
        position.avg_price = 2500.0
        position.opened_at = Mock()
        position.opened_at.isoformat.return_value = "2025-01-01T00:00:00"
        position.closed_at = None

        mock_positions_repo.list.return_value = [position]

        # Broker holdings: 45 shares (more than positions table - manual buy)
        mock_portfolio.get_holdings.return_value = {
            "data": [
                {
                    "tradingSymbol": "RELIANCE-EQ",
                    "quantity": 45,
                }
            ]
        }

        # Execute
        open_positions = sell_manager.get_open_positions()

        # Verify: Uses min(35, 45) = 35 (positions_qty, not broker_qty)
        assert len(open_positions) == 1
        assert open_positions[0]["symbol"] == "RELIANCE"
        assert open_positions[0]["qty"] == 35  # Uses positions_qty (35), ignores manual buy

    def test_reconcile_handles_missing_portfolio_gracefully(self, sell_manager, mock_positions_repo):
        """Test reconciliation handles missing portfolio gracefully."""
        sell_manager.portfolio = None

        stats = sell_manager._reconcile_positions_with_broker_holdings()

        assert stats == {"checked": 0, "updated": 0, "closed": 0, "ignored": 0}

    def test_reconcile_handles_holdings_api_error(self, sell_manager, mock_positions_repo, mock_portfolio):
        """Test reconciliation handles holdings API errors gracefully."""
        mock_portfolio.get_holdings.side_effect = Exception("API Error")

        stats = sell_manager._reconcile_positions_with_broker_holdings()

        # Should return empty stats without crashing
        assert stats == {"checked": 0, "updated": 0, "closed": 0, "ignored": 0}

    def test_run_at_market_open_calls_reconciliation(self, sell_manager, mock_positions_repo, mock_portfolio):
        """Test run_at_market_open calls reconciliation before placing orders."""
        # Setup: No open positions
        mock_positions_repo.list.return_value = []
        mock_portfolio.get_holdings.return_value = {"data": []}

        # Mock get_existing_sell_orders to avoid API calls
        sell_manager.get_existing_sell_orders = Mock(return_value={})

        # Execute
        orders_placed = sell_manager.run_at_market_open()

        # Verify: Reconciliation was called
        assert mock_portfolio.get_holdings.called
        assert orders_placed == 0

