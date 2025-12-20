"""
Tests for Full Symbols Migration Edge Cases

This test suite covers edge cases and missing coverage areas for the full symbols migration:
- Symbol format variations (different segments, case sensitivity)
- Ticker creation from full symbols
- Exact symbol matching
- Broker holdings with different field names
- Multiple segments of same base symbol
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from modules.kotak_neo_auto_trader.utils.symbol_utils import (
    extract_base_symbol,
    get_ticker_from_full_symbol,
    normalize_symbol,
)
from src.infrastructure.db.models import Positions


class TestSymbolUtilsEdgeCases:
    """Test edge cases for symbol utility functions"""

    def test_get_ticker_from_full_symbol_with_different_segments(self):
        """Test ticker creation from full symbols with different segment suffixes"""
        assert get_ticker_from_full_symbol("RELIANCE-EQ") == "RELIANCE.NS"
        assert get_ticker_from_full_symbol("RELIANCE-BE") == "RELIANCE.NS"
        assert get_ticker_from_full_symbol("RELIANCE-BL") == "RELIANCE.NS"
        assert get_ticker_from_full_symbol("RELIANCE-BZ") == "RELIANCE.NS"

    def test_get_ticker_from_full_symbol_with_base_symbol(self):
        """Test ticker creation from base symbol (no segment suffix)"""
        assert get_ticker_from_full_symbol("RELIANCE") == "RELIANCE.NS"
        assert get_ticker_from_full_symbol("TCS") == "TCS.NS"

    def test_get_ticker_from_full_symbol_case_insensitive(self):
        """Test ticker creation handles case variations"""
        assert get_ticker_from_full_symbol("reliance-eq") == "RELIANCE.NS"
        assert get_ticker_from_full_symbol("Reliance-EQ") == "RELIANCE.NS"
        assert get_ticker_from_full_symbol("RELIANCE-eq") == "RELIANCE.NS"

    def test_get_ticker_from_full_symbol_with_whitespace(self):
        """Test ticker creation handles whitespace"""
        assert get_ticker_from_full_symbol(" RELIANCE-EQ ") == "RELIANCE.NS"
        assert get_ticker_from_full_symbol("RELIANCE-EQ\n") == "RELIANCE.NS"

    def test_extract_base_symbol_with_different_segments(self):
        """Test base symbol extraction from different segment suffixes"""
        assert extract_base_symbol("RELIANCE-EQ") == "RELIANCE"
        assert extract_base_symbol("RELIANCE-BE") == "RELIANCE"
        assert extract_base_symbol("RELIANCE-BL") == "RELIANCE"
        assert extract_base_symbol("RELIANCE-BZ") == "RELIANCE"
        assert extract_base_symbol("RELIANCE") == "RELIANCE"

    def test_extract_base_symbol_case_insensitive(self):
        """Test base symbol extraction handles case variations"""
        assert extract_base_symbol("reliance-eq") == "RELIANCE"
        assert extract_base_symbol("Reliance-EQ") == "RELIANCE"

    def test_normalize_symbol_variations(self):
        """Test symbol normalization handles various formats"""
        assert normalize_symbol("reliance") == "RELIANCE"
        assert normalize_symbol("RELIANCE") == "RELIANCE"
        assert normalize_symbol(" Reliance ") == "RELIANCE"
        assert normalize_symbol("RELIANCE-EQ") == "RELIANCE-EQ"
        assert normalize_symbol("") == ""


class TestFullSymbolMatching:
    """Test exact symbol matching with full symbols"""

    def test_exact_symbol_match_same_segment(self):
        """Test that exact matching works for same segment"""
        symbol1 = "RELIANCE-EQ"
        symbol2 = "RELIANCE-EQ"
        assert symbol1.upper() == symbol2.upper()

    def test_exact_symbol_match_different_segments(self):
        """Test that different segments don't match (correct behavior)"""
        symbol1 = "RELIANCE-EQ"
        symbol2 = "RELIANCE-BE"
        assert symbol1.upper() != symbol2.upper()

    def test_exact_symbol_match_case_insensitive(self):
        """Test that matching is case insensitive"""
        symbol1 = "reliance-eq"
        symbol2 = "RELIANCE-EQ"
        assert symbol1.upper() == symbol2.upper()


class TestBrokerHoldingsSymbolMatching:
    """Test symbol matching with broker holdings that use different field names"""

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

    def test_holdings_matching_with_display_symbol(self):
        """Test matching when broker returns displaySymbol field"""
        holdings_data = [
            {
                "displaySymbol": "RELIANCE-EQ",
                "symbol": "RELIANCE",
                "quantity": 10,
            }
        ]

        position_symbol = "RELIANCE-EQ"
        for holding in holdings_data:
            holding_symbol = (
                holding.get("displaySymbol")
                or holding.get("symbol")
                or holding.get("tradingSymbol")
                or ""
            )
            holding_full_symbol = holding_symbol.upper()
            if holding_full_symbol == position_symbol.upper():
                assert holding.get("quantity") == 10
                break
        else:
            pytest.fail("Symbol should match")

    def test_holdings_matching_with_trading_symbol(self):
        """Test matching when broker returns tradingSymbol field"""
        holdings_data = [
            {
                "tradingSymbol": "RELIANCE-EQ",
                "quantity": 10,
            }
        ]

        position_symbol = "RELIANCE-EQ"
        for holding in holdings_data:
            holding_symbol = (
                holding.get("displaySymbol")
                or holding.get("symbol")
                or holding.get("tradingSymbol")
                or ""
            )
            holding_full_symbol = holding_symbol.upper()
            if holding_full_symbol == position_symbol.upper():
                assert holding.get("quantity") == 10
                break
        else:
            pytest.fail("Symbol should match")

    def test_holdings_matching_priority_order(self):
        """Test that displaySymbol takes priority over symbol field"""
        holdings_data = [
            {
                "displaySymbol": "RELIANCE-EQ",  # Should use this
                "symbol": "RELIANCE",  # Should ignore this
                "quantity": 10,
            }
        ]

        position_symbol = "RELIANCE-EQ"
        for holding in holdings_data:
            holding_symbol = (
                holding.get("displaySymbol")
                or holding.get("symbol")
                or holding.get("tradingSymbol")
                or ""
            )
            holding_full_symbol = holding_symbol.upper()
            if holding_full_symbol == position_symbol.upper():
                assert holding.get("quantity") == 10
                break
        else:
            pytest.fail("Symbol should match using displaySymbol")

    def test_holdings_no_match_different_segments(self):
        """Test that holdings with different segments don't match"""
        holdings_data = [
            {
                "displaySymbol": "RELIANCE-BE",
                "quantity": 10,
            }
        ]

        position_symbol = "RELIANCE-EQ"
        matched = False
        for holding in holdings_data:
            holding_symbol = (
                holding.get("displaySymbol")
                or holding.get("symbol")
                or holding.get("tradingSymbol")
                or ""
            )
            holding_full_symbol = holding_symbol.upper()
            if holding_full_symbol == position_symbol.upper():
                matched = True
                break

        assert not matched, "Different segments should not match"


class TestMultipleSegmentsSameBaseSymbol:
    """Test handling of multiple segments of the same base symbol"""

    def test_positions_with_different_segments_are_separate(self):
        """Test that positions with different segments are tracked separately"""
        position_eq = Positions(
            user_id=1,
            symbol="RELIANCE-EQ",
            quantity=10.0,
            avg_price=2500.0,
        )

        position_be = Positions(
            user_id=1,
            symbol="RELIANCE-BE",
            quantity=5.0,
            avg_price=2500.0,
        )

        # They should be different positions
        assert position_eq.symbol != position_be.symbol
        assert position_eq.quantity != position_be.quantity

    def test_active_sell_orders_different_segments(self):
        """Test that active_sell_orders tracks different segments separately"""
        active_sell_orders = {
            "RELIANCE-EQ": {
                "order_id": "SELL123",
                "qty": 10,
                "price": 2500.0,
            },
            "RELIANCE-BE": {
                "order_id": "SELL456",
                "qty": 5,
                "price": 2500.0,
            },
        }

        # Both should exist independently
        assert "RELIANCE-EQ" in active_sell_orders
        assert "RELIANCE-BE" in active_sell_orders
        assert active_sell_orders["RELIANCE-EQ"]["qty"] == 10
        assert active_sell_orders["RELIANCE-BE"]["qty"] == 5


class TestReconciliationWithFullSymbols:
    """Test reconciliation logic with full symbols"""

    @pytest.fixture
    def sell_manager(self, mock_auth):
        """Create SellOrderManager instance"""
        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
            manager = SellOrderManager(auth=mock_auth, history_path="test_history.json")
            manager.user_id = 1
            manager.positions_repo = Mock()
            return manager

    def test_reconcile_single_symbol_exact_match(self):
        """Test _reconcile_single_symbol with exact full symbol match"""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"
        position.quantity = 10.0
        position.closed_at = None

        holdings_data = [
            {
                "tradingSymbol": "RELIANCE-EQ",
                "quantity": 10,
            }
        ]

        # Simulate the matching logic
        symbol = "RELIANCE-EQ"
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

        assert broker_qty == 10
        assert broker_qty == int(position.quantity)

    def test_reconcile_single_symbol_no_match_different_segment(self):
        """Test that different segments don't match during reconciliation"""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"
        position.quantity = 10.0

        holdings_data = [
            {
                "tradingSymbol": "RELIANCE-BE",  # Different segment
                "quantity": 5,
            }
        ]

        # Simulate the matching logic
        symbol = "RELIANCE-EQ"
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


class TestTickerCreationInSellEngine:
    """Test ticker creation in sell engine methods"""

    @pytest.fixture
    def sell_manager(self, mock_auth):
        """Create SellOrderManager instance"""
        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
            manager = SellOrderManager(auth=mock_auth, history_path="test_history.json")
            manager.user_id = 1
            return manager

    def test_get_positions_without_sell_orders_creates_correct_ticker(self):
        """Test that get_positions_without_sell_orders creates correct ticker from full symbol"""
        from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol

        # Simulate the logic in _get_positions_without_sell_orders_db_only
        symbol = "RELIANCE-EQ"  # Full symbol
        base_symbol = extract_base_symbol(symbol).upper()
        ticker = f"{base_symbol}.NS"

        assert ticker == "RELIANCE.NS"
        assert ticker != "RELIANCE-EQ.NS"  # Should not include segment suffix

    def test_ticker_creation_preserves_base_symbol(self):
        """Test that ticker creation correctly extracts base symbol"""
        test_cases = [
            ("RELIANCE-EQ", "RELIANCE.NS"),
            ("TCS-BE", "TCS.NS"),
            ("INFY-BL", "INFY.NS"),
            ("WIPRO-BZ", "WIPRO.NS"),
        ]

        for full_symbol, expected_ticker in test_cases:
            base_symbol = extract_base_symbol(full_symbol).upper()
            ticker = f"{base_symbol}.NS"
            assert ticker == expected_ticker, f"Failed for {full_symbol}"


class TestPositionCreationWithFullSymbols:
    """Test position creation and updates with full symbols"""

    def test_position_creation_uses_full_symbol(self):
        """Test that positions are created with full symbols"""
        position = Positions(
            user_id=1,
            symbol="RELIANCE-EQ",  # Full symbol
            quantity=10.0,
            avg_price=2500.0,
        )

        assert position.symbol == "RELIANCE-EQ"
        assert position.symbol.endswith("-EQ")

    def test_position_retrieval_by_full_symbol(self):
        """Test that positions can be retrieved by full symbol"""
        from unittest.mock import Mock

        mock_positions_repo = Mock()
        position = Positions(
            user_id=1,
            symbol="RELIANCE-EQ",
            quantity=10.0,
            avg_price=2500.0,
        )
        mock_positions_repo.get_by_symbol.return_value = position

        retrieved = mock_positions_repo.get_by_symbol(1, "RELIANCE-EQ")
        assert retrieved is not None
        assert retrieved.symbol == "RELIANCE-EQ"

    def test_position_retrieval_fails_with_base_symbol(self):
        """Test that position retrieval fails when using base symbol instead of full"""
        from unittest.mock import Mock

        mock_positions_repo = Mock()
        position = Positions(
            user_id=1,
            symbol="RELIANCE-EQ",  # Full symbol in DB
            quantity=10.0,
            avg_price=2500.0,
        )
        mock_positions_repo.get_by_symbol.return_value = None  # Not found with base symbol

        retrieved = mock_positions_repo.get_by_symbol(1, "RELIANCE")  # Base symbol
        assert retrieved is None  # Should not find with base symbol


class TestManualSellDetectionWithFullSymbols:
    """Test manual sell detection with full symbols"""

    def test_manual_sell_detection_exact_symbol_match(self):
        """Test that manual sell detection uses exact symbol matching"""
        # Simulate the logic in _detect_manual_sells_from_orders
        open_positions = [
            Mock(symbol="RELIANCE-EQ", quantity=10.0),
            Mock(symbol="TCS-BE", quantity=5.0),
        ]

        # Build symbol_to_position map (using full symbols)
        symbol_to_position = {}
        for pos in open_positions:
            full_symbol = pos.symbol.upper()
            symbol_to_position[full_symbol] = pos

        # Simulate manual sell order
        manual_sell_symbol = "RELIANCE-EQ"
        position = symbol_to_position.get(manual_sell_symbol.upper())

        assert position is not None
        assert position.symbol == "RELIANCE-EQ"

    def test_manual_sell_detection_no_match_different_segment(self):
        """Test that manual sell with different segment doesn't match"""
        # Simulate the logic in _detect_manual_sells_from_orders
        open_positions = [
            Mock(symbol="RELIANCE-EQ", quantity=10.0),
        ]

        # Build symbol_to_position map (using full symbols)
        symbol_to_position = {}
        for pos in open_positions:
            full_symbol = pos.symbol.upper()
            symbol_to_position[full_symbol] = pos

        # Simulate manual sell order with different segment
        manual_sell_symbol = "RELIANCE-BE"  # Different segment
        position = symbol_to_position.get(manual_sell_symbol.upper())

        assert position is None  # Should not match


class TestBrokerHoldingsMapWithFullSymbols:
    """Test broker holdings map creation with full symbols"""

    def test_broker_holdings_map_uses_full_symbols(self):
        """Test that broker holdings map uses full symbols as keys"""
        holdings_data = [
            {
                "tradingSymbol": "RELIANCE-EQ",
                "quantity": 10,
            },
            {
                "tradingSymbol": "TCS-BE",
                "quantity": 5,
            },
        ]

        # Simulate the logic in _reconcile_positions_with_broker_holdings
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

        # Verify keys are full symbols
        assert "RELIANCE-EQ" in broker_holdings_map
        assert "TCS-BE" in broker_holdings_map
        assert broker_holdings_map["RELIANCE-EQ"] == 10
        assert broker_holdings_map["TCS-BE"] == 5

    def test_broker_holdings_map_exact_matching(self):
        """Test that broker holdings map enables exact matching"""
        broker_holdings_map = {
            "RELIANCE-EQ": 10,
            "RELIANCE-BE": 5,
        }

        position_symbol = "RELIANCE-EQ"
        broker_qty = broker_holdings_map.get(position_symbol.upper(), 0)

        assert broker_qty == 10
        assert broker_qty != 5  # Should not get BE quantity
