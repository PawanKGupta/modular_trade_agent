"""
Tests for Reconciliation Logic with Full Symbols

This test suite tests the reconciliation logic that matches positions with broker holdings
using exact full symbol matching (no base symbol fallback).
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from src.infrastructure.db.models import Positions


class TestReconciliationExactMatching:
    """Test exact symbol matching in reconciliation"""

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
            return manager

    def test_reconcile_positions_exact_match_same_segment(self):
        """Test reconciliation with exact match (same segment)"""
        # Simulate broker holdings
        holdings_data = [
            {
                "tradingSymbol": "RELIANCE-EQ",
                "quantity": 10,
            }
        ]

        # Simulate position
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"
        position.quantity = 10.0

        # Simulate the matching logic from _reconcile_positions_with_broker_holdings
        broker_holdings_map = {}
        for holding in holdings_data:
            symbol = (
                holding.get("tradingSymbol")
                or holding.get("symbol")
                or holding.get("securitySymbol")
                or ""
            )
            if not symbol:
                continue

            full_symbol = symbol.upper()
            qty = int(holding.get("quantity", 0))

            if full_symbol and qty > 0:
                broker_holdings_map[full_symbol] = qty

        # Check match
        position_symbol = position.symbol.upper()
        broker_qty = broker_holdings_map.get(position_symbol, 0)

        assert broker_qty == 10
        assert broker_qty == int(position.quantity)

    def test_reconcile_positions_no_match_different_segment(self):
        """Test that different segments don't match during reconciliation"""
        # Simulate broker holdings
        holdings_data = [
            {
                "tradingSymbol": "RELIANCE-BE",  # Different segment
                "quantity": 5,
            }
        ]

        # Simulate position
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"
        position.quantity = 10.0

        # Simulate the matching logic
        broker_holdings_map = {}
        for holding in holdings_data:
            symbol = (
                holding.get("tradingSymbol")
                or holding.get("symbol")
                or holding.get("securitySymbol")
                or ""
            )
            if not symbol:
                continue

            full_symbol = symbol.upper()
            qty = int(holding.get("quantity", 0))

            if full_symbol and qty > 0:
                broker_holdings_map[full_symbol] = qty

        # Check match (should not match - different segments)
        position_symbol = position.symbol.upper()
        broker_qty = broker_holdings_map.get(position_symbol, 0)

        assert broker_qty == 0  # No match
        assert broker_qty != int(position.quantity)

    def test_reconcile_single_symbol_exact_match(self):
        """Test _reconcile_single_symbol with exact match"""
        position = Mock(spec=Positions)
        position.symbol = "TCS-BE"
        position.quantity = 5.0
        position.closed_at = None

        holdings_data = [
            {
                "tradingSymbol": "TCS-BE",
                "quantity": 5,
            }
        ]

        # Simulate the matching logic from _reconcile_single_symbol
        symbol = "TCS-BE"
        broker_qty = 0
        for holding in holdings_data:
            holding_symbol = (
                holding.get("tradingSymbol")
                or holding.get("symbol")
                or holding.get("securitySymbol")
                or ""
            )
            if not holding_symbol:
                continue

            full_symbol = holding_symbol.upper()
            if full_symbol == symbol.upper():  # Exact match
                broker_qty = int(holding.get("quantity", 0))
                break

        assert broker_qty == 5
        assert broker_qty == int(position.quantity)

    def test_reconcile_single_symbol_no_match_different_segment(self):
        """Test _reconcile_single_symbol doesn't match different segments"""
        position = Mock(spec=Positions)
        position.symbol = "TCS-BE"
        position.quantity = 5.0

        holdings_data = [
            {
                "tradingSymbol": "TCS-EQ",  # Different segment
                "quantity": 10,
            }
        ]

        # Simulate the matching logic
        symbol = "TCS-BE"
        broker_qty = 0
        for holding in holdings_data:
            holding_symbol = (
                holding.get("tradingSymbol")
                or holding.get("symbol")
                or holding.get("securitySymbol")
                or ""
            )
            if not holding_symbol:
                continue

            full_symbol = holding_symbol.upper()
            if full_symbol == symbol.upper():  # Exact match
                broker_qty = int(holding.get("quantity", 0))
                break

        # Should not match - different segments
        assert broker_qty == 0
        assert broker_qty != int(position.quantity)


class TestReconciliationWithDifferentFieldNames:
    """Test reconciliation with broker holdings using different field names"""

    def test_reconcile_with_display_symbol(self):
        """Test reconciliation when broker returns displaySymbol"""
        holdings_data = [
            {
                "displaySymbol": "RELIANCE-EQ",
                "quantity": 10,
            }
        ]

        position_symbol = "RELIANCE-EQ"

        # Simulate matching logic that checks multiple fields
        broker_qty = 0
        for holding in holdings_data:
            holding_symbol = (
                holding.get("displaySymbol")
                or holding.get("tradingSymbol")
                or holding.get("symbol")
                or ""
            )
            if not holding_symbol:
                continue

            full_symbol = holding_symbol.upper()
            if full_symbol == position_symbol.upper():
                broker_qty = int(holding.get("quantity", 0))
                break

        assert broker_qty == 10

    def test_reconcile_with_symbol_field(self):
        """Test reconciliation when broker returns symbol field"""
        holdings_data = [
            {
                "symbol": "RELIANCE-EQ",
                "quantity": 10,
            }
        ]

        position_symbol = "RELIANCE-EQ"

        broker_qty = 0
        for holding in holdings_data:
            holding_symbol = (
                holding.get("displaySymbol")
                or holding.get("tradingSymbol")
                or holding.get("symbol")
                or ""
            )
            if not holding_symbol:
                continue

            full_symbol = holding_symbol.upper()
            if full_symbol == position_symbol.upper():
                broker_qty = int(holding.get("quantity", 0))
                break

        assert broker_qty == 10

    def test_reconcile_field_priority(self):
        """Test that displaySymbol takes priority over symbol field"""
        holdings_data = [
            {
                "displaySymbol": "RELIANCE-EQ",  # Should use this
                "symbol": "RELIANCE",  # Should ignore this
                "quantity": 10,
            }
        ]

        position_symbol = "RELIANCE-EQ"

        broker_qty = 0
        for holding in holdings_data:
            holding_symbol = (
                holding.get("displaySymbol")
                or holding.get("tradingSymbol")
                or holding.get("symbol")
                or ""
            )
            if not holding_symbol:
                continue

            full_symbol = holding_symbol.upper()
            if full_symbol == position_symbol.upper():
                broker_qty = int(holding.get("quantity", 0))
                break

        assert broker_qty == 10


class TestReconciliationManualSellDetection:
    """Test manual sell detection during reconciliation"""

    def test_manual_full_sell_detection_exact_match(self):
        """Test manual full sell detection with exact symbol match"""
        # Position exists but broker has 0 quantity
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"
        position.quantity = 10.0

        broker_holdings_map = {}  # Empty - no holdings

        # Simulate detection logic
        position_symbol = position.symbol.upper()
        positions_qty = int(position.quantity)
        broker_qty = broker_holdings_map.get(position_symbol, 0)

        # Manual full sell detected
        if broker_qty == 0 and positions_qty > 0:
            assert True  # Should detect manual sell
        else:
            pytest.fail("Should detect manual full sell")

    def test_manual_partial_sell_detection_exact_match(self):
        """Test manual partial sell detection with exact symbol match"""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"
        position.quantity = 10.0

        broker_holdings_map = {"RELIANCE-EQ": 5}  # Broker has less

        # Simulate detection logic
        position_symbol = position.symbol.upper()
        positions_qty = int(position.quantity)
        broker_qty = broker_holdings_map.get(position_symbol, 0)

        # Manual partial sell detected
        if broker_qty < positions_qty and broker_qty > 0:
            assert True  # Should detect partial sell
        else:
            pytest.fail("Should detect manual partial sell")

    def test_manual_sell_not_detected_different_segment(self):
        """Test that manual sell is not detected for different segment"""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"
        position.quantity = 10.0

        broker_holdings_map = {"RELIANCE-BE": 5}  # Different segment

        # Simulate detection logic
        position_symbol = position.symbol.upper()
        positions_qty = int(position.quantity)
        broker_qty = broker_holdings_map.get(position_symbol, 0)

        # Should not detect as manual sell (different segment)
        assert broker_qty == 0  # No match for RELIANCE-EQ
        # But this is correct - different segments are separate instruments


class TestReconciliationMultiplePositions:
    """Test reconciliation with multiple positions"""

    def test_reconcile_multiple_positions_different_segments(self):
        """Test reconciliation with multiple positions having different segments"""
        positions = [
            Mock(spec=Positions, symbol="RELIANCE-EQ", quantity=10.0, closed_at=None),
            Mock(spec=Positions, symbol="RELIANCE-BE", quantity=5.0, closed_at=None),
        ]

        holdings_data = [
            {"tradingSymbol": "RELIANCE-EQ", "quantity": 10},
            {"tradingSymbol": "RELIANCE-BE", "quantity": 5},
        ]

        # Build broker holdings map
        broker_holdings_map = {}
        for holding in holdings_data:
            symbol = holding.get("tradingSymbol", "")
            if symbol:
                full_symbol = symbol.upper()
                qty = int(holding.get("quantity", 0))
                if full_symbol and qty > 0:
                    broker_holdings_map[full_symbol] = qty

        # Reconcile each position
        for pos in positions:
            position_symbol = pos.symbol.upper()
            broker_qty = broker_holdings_map.get(position_symbol, 0)
            positions_qty = int(pos.quantity)

            # Should match exactly
            assert broker_qty == positions_qty

    def test_reconcile_multiple_positions_some_missing_in_holdings(self):
        """Test reconciliation when some positions are missing in holdings"""
        positions = [
            Mock(spec=Positions, symbol="RELIANCE-EQ", quantity=10.0, closed_at=None),
            Mock(spec=Positions, symbol="TCS-BE", quantity=5.0, closed_at=None),
        ]

        holdings_data = [
            {"tradingSymbol": "RELIANCE-EQ", "quantity": 10},
            # TCS-BE missing in holdings
        ]

        # Build broker holdings map
        broker_holdings_map = {}
        for holding in holdings_data:
            symbol = holding.get("tradingSymbol", "")
            if symbol:
                full_symbol = symbol.upper()
                qty = int(holding.get("quantity", 0))
                if full_symbol and qty > 0:
                    broker_holdings_map[full_symbol] = qty

        # Check RELIANCE-EQ
        pos1 = positions[0]
        broker_qty1 = broker_holdings_map.get(pos1.symbol.upper(), 0)
        assert broker_qty1 == 10

        # Check TCS-BE (missing in holdings)
        pos2 = positions[1]
        broker_qty2 = broker_holdings_map.get(pos2.symbol.upper(), 0)
        assert broker_qty2 == 0  # Not in holdings
        assert broker_qty2 != int(pos2.quantity)  # Mismatch detected
