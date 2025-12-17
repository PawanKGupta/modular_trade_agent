"""
Tests for Reconciliation with Base/Full Symbol Mapping

Tests the fix where reconciliation matches broker holdings by both full symbol and base symbol.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager  # noqa: E402
from src.infrastructure.db.models import Positions  # noqa: E402


class TestReconciliationBaseFullSymbolMapping:
    """Test reconciliation with base/full symbol mapping"""

    @pytest.fixture
    def mock_auth(self):
        """Create mock auth object"""
        auth = Mock()
        auth.client = Mock()
        return auth

    @pytest.fixture
    def sell_manager(self, mock_auth):
        """Create SellOrderManager instance"""
        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
            manager = SellOrderManager(auth=mock_auth, history_path="test_history.json")
            manager.user_id = 1
            manager.positions_repo = Mock()
            manager.portfolio = Mock()
            return manager

    def test_reconciliation_matches_by_full_symbol(self, sell_manager):
        """Test that reconciliation matches when broker has full symbol"""
        # Mock position with full symbol
        position = Mock(spec=Positions)
        position.symbol = "ASTERDM-EQ"
        position.quantity = 16.0
        position.closed_at = None

        sell_manager.positions_repo.list = Mock(return_value=[position])
        sell_manager.positions_repo.mark_closed = Mock()
        sell_manager.positions_repo.reduce_quantity = Mock()

        # Mock holdings with full symbol
        holdings_response = {
            "data": [
                {
                    "tradingSymbol": "ASTERDM-EQ",
                    "quantity": 16,
                }
            ]
        }
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        stats = sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Should match and not mark as closed
        assert stats["closed"] == 0
        assert stats["updated"] == 0
        sell_manager.positions_repo.mark_closed.assert_not_called()

    def test_reconciliation_matches_by_base_symbol_when_broker_has_base(self, sell_manager):
        """Test that reconciliation matches by base symbol when broker returns base symbol"""
        # Mock position with full symbol
        position = Mock(spec=Positions)
        position.symbol = "ASTERDM-EQ"
        position.quantity = 16.0
        position.closed_at = None

        sell_manager.positions_repo.list = Mock(return_value=[position])
        sell_manager.positions_repo.mark_closed = Mock()
        sell_manager.positions_repo.reduce_quantity = Mock()

        # Mock holdings with base symbol only (as broker API sometimes returns)
        holdings_response = {
            "data": [
                {
                    "symbol": "ASTERDM",  # Base symbol, not full
                    "displaySymbol": "ASTERDM",  # Also base
                    "quantity": 16,
                }
            ]
        }
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        stats = sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Should match via base symbol and not mark as closed
        assert stats["closed"] == 0
        assert stats["updated"] == 0
        sell_manager.positions_repo.mark_closed.assert_not_called()

    def test_reconciliation_matches_by_display_symbol(self, sell_manager):
        """Test that reconciliation matches when broker returns displaySymbol"""
        # Mock position with full symbol
        position = Mock(spec=Positions)
        position.symbol = "EMKAY-BE"
        position.quantity = 376.0
        position.closed_at = None

        sell_manager.positions_repo.list = Mock(return_value=[position])
        sell_manager.positions_repo.mark_closed = Mock()
        sell_manager.positions_repo.reduce_quantity = Mock()

        # Mock holdings with displaySymbol (as broker API returns)
        holdings_response = {
            "data": [
                {
                    "symbol": "EMKAY",  # Base symbol
                    "displaySymbol": "EMKAY-BE",  # Full symbol in displaySymbol
                    "quantity": 376,
                }
            ]
        }
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        stats = sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Should match and not mark as closed
        assert stats["closed"] == 0
        assert stats["updated"] == 0
        sell_manager.positions_repo.mark_closed.assert_not_called()

    def test_reconciliation_detects_manual_full_sell_when_truly_missing(self, sell_manager):
        """Test that reconciliation detects manual full sell when holdings truly missing"""
        # Mock position with quantity
        position = Mock(spec=Positions)
        position.symbol = "SOLD-EQ"
        position.quantity = 10.0
        position.closed_at = None

        sell_manager.positions_repo.list = Mock(return_value=[position])
        sell_manager.positions_repo.mark_closed = Mock()

        # Mock empty holdings (position truly sold)
        holdings_response = {"data": []}
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        stats = sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Should detect manual full sell
        assert stats["closed"] == 1
        # mark_closed is called with additional parameters (closed_at, exit_price)
        sell_manager.positions_repo.mark_closed.assert_called_once()
        call_kwargs = sell_manager.positions_repo.mark_closed.call_args[1]
        assert call_kwargs["user_id"] == 1
        assert call_kwargs["symbol"] == "SOLD-EQ"

    def test_reconciliation_detects_manual_partial_sell(self, sell_manager):
        """Test that reconciliation detects manual partial sell"""
        # Mock position with higher quantity
        position = Mock(spec=Positions)
        position.symbol = "PARTIAL-EQ"
        position.quantity = 100.0
        position.closed_at = None

        sell_manager.positions_repo.list = Mock(return_value=[position])
        sell_manager.positions_repo.mark_closed = Mock()
        sell_manager.positions_repo.reduce_quantity = Mock()

        # Mock holdings with lower quantity (partial sell)
        holdings_response = {
            "data": [
                {
                    "symbol": "PARTIAL",  # Base symbol
                    "quantity": 60,  # Less than position quantity
                }
            ]
        }
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        stats = sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Should detect partial sell
        assert stats["updated"] == 1
        sell_manager.positions_repo.reduce_quantity.assert_called_once()
        # Verify sold quantity (100 - 60 = 40)
        call_args = sell_manager.positions_repo.reduce_quantity.call_args
        assert call_args[1]["sold_quantity"] == 40.0

    def test_reconciliation_ignores_manual_buys(self, sell_manager):
        """Test that reconciliation ignores manual buys (broker_qty > positions_qty)"""
        # Mock position with lower quantity
        position = Mock(spec=Positions)
        position.symbol = "BOUGHT-EQ"
        position.quantity = 100.0
        position.closed_at = None

        sell_manager.positions_repo.list = Mock(return_value=[position])
        sell_manager.positions_repo.mark_closed = Mock()
        sell_manager.positions_repo.reduce_quantity = Mock()

        # Mock holdings with higher quantity (manual buy)
        holdings_response = {
            "data": [
                {
                    "symbol": "BOUGHT",
                    "quantity": 120,  # More than position quantity
                }
            ]
        }
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        stats = sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Should ignore (no updates)
        assert stats["closed"] == 0
        assert stats["updated"] == 0
        sell_manager.positions_repo.mark_closed.assert_not_called()
        sell_manager.positions_repo.reduce_quantity.assert_not_called()

    def test_reconciliation_broker_holdings_map_contains_both_keys(self, sell_manager):
        """Test that broker_holdings_map contains both full and base symbol keys"""
        # Mock position
        position = Mock(spec=Positions)
        position.symbol = "TEST-EQ"
        position.quantity = 10.0
        position.closed_at = None

        sell_manager.positions_repo.list = Mock(return_value=[position])
        sell_manager.positions_repo.mark_closed = Mock()

        # Mock holdings with displaySymbol
        holdings_response = {
            "data": [
                {
                    "symbol": "TEST",  # Base
                    "displaySymbol": "TEST-EQ",  # Full
                    "quantity": 10,
                }
            ]
        }
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        stats = sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Should match (both keys should be in map)
        assert stats["closed"] == 0

    def test_reconciliation_handles_multiple_positions_with_different_segments(self, sell_manager):
        """Test reconciliation with multiple positions having different segments"""
        # Mock multiple positions
        positions = [
            Mock(spec=Positions, symbol="RELIANCE-EQ", quantity=10.0, closed_at=None),
            Mock(spec=Positions, symbol="RELIANCE-BE", quantity=5.0, closed_at=None),
        ]

        sell_manager.positions_repo.list = Mock(return_value=positions)
        sell_manager.positions_repo.mark_closed = Mock()
        sell_manager.positions_repo.reduce_quantity = Mock()

        # Mock holdings with both segments
        holdings_response = {
            "data": [
                {"symbol": "RELIANCE", "displaySymbol": "RELIANCE-EQ", "quantity": 10},
                {"symbol": "RELIANCE", "displaySymbol": "RELIANCE-BE", "quantity": 5},
            ]
        }
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        stats = sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Both should match
        assert stats["closed"] == 0
        assert stats["updated"] == 0
        sell_manager.positions_repo.mark_closed.assert_not_called()
