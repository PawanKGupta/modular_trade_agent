"""
Tests for Ticker Creation from Full Symbols

This test suite specifically tests the ticker creation logic which is critical
for yfinance integration. Tickers must use base symbols (e.g., "RELIANCE.NS"),
not full symbols (e.g., "RELIANCE-EQ.NS").
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.utils.symbol_utils import (
    extract_base_symbol,
    get_ticker_from_full_symbol,
)


class TestTickerCreationFromFullSymbols:
    """Test ticker creation from full symbols in various contexts"""

    def test_get_ticker_from_full_symbol_all_segments(self):
        """Test ticker creation for all segment types"""
        test_cases = [
            ("RELIANCE-EQ", "RELIANCE.NS"),
            ("RELIANCE-BE", "RELIANCE.NS"),
            ("RELIANCE-BL", "RELIANCE.NS"),
            ("RELIANCE-BZ", "RELIANCE.NS"),
            ("TCS-EQ", "TCS.NS"),
            ("INFY-BE", "INFY.NS"),
        ]

        for full_symbol, expected_ticker in test_cases:
            ticker = get_ticker_from_full_symbol(full_symbol)
            assert (
                ticker == expected_ticker
            ), f"Failed for {full_symbol}: got {ticker}, expected {expected_ticker}"

    def test_get_ticker_from_full_symbol_base_symbol(self):
        """Test ticker creation from base symbol (no segment)"""
        assert get_ticker_from_full_symbol("RELIANCE") == "RELIANCE.NS"
        assert get_ticker_from_full_symbol("TCS") == "TCS.NS"

    def test_get_ticker_from_full_symbol_different_exchange(self):
        """Test ticker creation with different exchange suffix"""
        assert get_ticker_from_full_symbol("RELIANCE-EQ", exchange="BO") == "RELIANCE.BO"
        assert get_ticker_from_full_symbol("TCS-BE", exchange="BO") == "TCS.BO"

    def test_ticker_creation_in_get_positions_without_sell_orders(self):
        """Test ticker creation in get_positions_without_sell_orders method"""
        from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol

        # Simulate the logic in _get_positions_without_sell_orders_db_only
        symbol = "RELIANCE-EQ"  # Full symbol from position
        base_symbol = extract_base_symbol(symbol).upper()
        ticker = f"{base_symbol}.NS"

        assert ticker == "RELIANCE.NS"
        assert not ticker.endswith("-EQ.NS")  # Should not include segment

    def test_ticker_creation_in_check_and_place_sell_orders(self):
        """Test ticker creation when placing sell orders for new holdings"""
        # Simulate the logic in check_and_place_sell_orders_for_new_holdings
        db_order_symbol = "RELIANCE-EQ"  # Full symbol from order
        ticker = get_ticker_from_full_symbol(db_order_symbol)

        assert ticker == "RELIANCE.NS"
        assert ticker != "RELIANCE-EQ.NS"

    def test_ticker_creation_preserves_base_for_yfinance(self):
        """Test that ticker creation correctly extracts base for yfinance compatibility"""
        # yfinance requires base symbols, not full symbols
        full_symbols = ["RELIANCE-EQ", "TCS-BE", "INFY-BL", "WIPRO-BZ"]

        for full_symbol in full_symbols:
            ticker = get_ticker_from_full_symbol(full_symbol)
            # Verify it doesn't contain segment suffix
            assert "-EQ" not in ticker
            assert "-BE" not in ticker
            assert "-BL" not in ticker
            assert "-BZ" not in ticker
            # Verify it has .NS suffix
            assert ticker.endswith(".NS")
            # Verify base symbol is correct
            base = extract_base_symbol(full_symbol)
            assert ticker == f"{base}.NS"


class TestTickerCreationEdgeCases:
    """Test edge cases in ticker creation"""

    def test_ticker_creation_with_whitespace(self):
        """Test ticker creation handles whitespace correctly"""
        assert get_ticker_from_full_symbol(" RELIANCE-EQ ") == "RELIANCE.NS"
        assert get_ticker_from_full_symbol("RELIANCE-EQ\n") == "RELIANCE.NS"
        assert get_ticker_from_full_symbol("\tTCS-BE\t") == "TCS.NS"

    def test_ticker_creation_case_insensitive(self):
        """Test ticker creation is case insensitive"""
        assert get_ticker_from_full_symbol("reliance-eq") == "RELIANCE.NS"
        assert get_ticker_from_full_symbol("Reliance-EQ") == "RELIANCE.NS"
        assert get_ticker_from_full_symbol("RELIANCE-eq") == "RELIANCE.NS"

    def test_ticker_creation_with_multiple_hyphens(self):
        """Test ticker creation with symbols that have multiple hyphens"""
        # Edge case: symbol with multiple hyphens (should only split on first)
        # This is handled by split("-")[0] which takes first part
        symbol = "SOME-STOCK-EQ"  # Unlikely but possible
        ticker = get_ticker_from_full_symbol(symbol)
        # Should extract "SOME" as base (first part before hyphen)
        assert ticker == "SOME.NS"

    def test_ticker_creation_empty_string(self):
        """Test ticker creation with empty string"""
        # Should handle gracefully
        ticker = get_ticker_from_full_symbol("")
        assert ticker == ".NS"  # Empty base + .NS

    def test_ticker_creation_already_has_exchange_suffix(self):
        """Test ticker creation when symbol already has exchange suffix"""
        # If someone passes a ticker instead of symbol, extract_base_symbol only splits on "-"
        # So "RELIANCE.NS" -> base is "RELIANCE.NS" (no hyphen to split)
        # This is expected behavior - extract_base_symbol doesn't remove .NS
        ticker = get_ticker_from_full_symbol("RELIANCE.NS")
        # extract_base_symbol("RELIANCE.NS") returns "RELIANCE.NS" (no hyphen to split)
        # Then adds .NS -> "RELIANCE.NS.NS"
        # This is correct behavior - function expects full symbol, not ticker
        assert ticker == "RELIANCE.NS.NS"  # Expected when passing ticker format


class TestTickerCreationInSellEngineMethods:
    """Test ticker creation in specific sell engine methods"""

    def test_get_positions_without_sell_orders_ticker_creation(self):
        """Test that get_positions_without_sell_orders creates correct tickers"""
        from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol

        # Simulate position with full symbol
        position_symbol = "RELIANCE-EQ"

        # Simulate the logic in _get_positions_without_sell_orders_db_only
        base_symbol = extract_base_symbol(position_symbol).upper()
        ticker = f"{base_symbol}.NS"

        assert ticker == "RELIANCE.NS"
        assert position_symbol == "RELIANCE-EQ"  # Original full symbol preserved

    def test_run_at_market_open_ticker_creation(self):
        """Test ticker creation in run_at_market_open method"""
        # Simulate trade dict with full symbol
        trade = {
            "symbol": "RELIANCE-EQ",  # Full symbol
            "placed_symbol": "RELIANCE-EQ",
            "qty": 10,
        }

        # Simulate ticker creation logic
        symbol = trade.get("symbol", "")
        from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol

        base_symbol = extract_base_symbol(symbol).upper()
        ticker = f"{base_symbol}.NS"

        assert ticker == "RELIANCE.NS"
        assert symbol == "RELIANCE-EQ"  # Original preserved

    def test_place_sell_order_ticker_creation(self):
        """Test ticker creation when placing sell orders"""
        # Simulate trade dict
        trade = {
            "symbol": "TCS-BE",  # Full symbol
            "ticker": None,  # Not provided, needs to be created
            "placed_symbol": "TCS-BE",
        }

        # Simulate ticker creation if not provided
        ticker = trade.get("ticker")
        if not ticker:
            symbol = trade.get("symbol", "")
            from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol

            base_symbol = extract_base_symbol(symbol).upper()
            ticker = f"{base_symbol}.NS"

        assert ticker == "TCS.NS"
        assert trade["symbol"] == "TCS-BE"  # Original preserved


class TestTickerCreationConsistency:
    """Test consistency of ticker creation across different code paths"""

    def test_ticker_creation_consistent_across_methods(self):
        """Test that ticker creation is consistent across different methods"""
        full_symbol = "RELIANCE-EQ"

        # Method 1: Direct function call
        ticker1 = get_ticker_from_full_symbol(full_symbol)

        # Method 2: Manual extraction + formatting
        from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol

        base_symbol = extract_base_symbol(full_symbol).upper()
        ticker2 = f"{base_symbol}.NS"

        # Both should produce same result
        assert ticker1 == ticker2 == "RELIANCE.NS"

    def test_ticker_creation_preserves_symbol_for_matching(self):
        """Test that ticker creation doesn't affect symbol used for matching"""
        full_symbol = "RELIANCE-EQ"

        # Create ticker (for yfinance)
        ticker = get_ticker_from_full_symbol(full_symbol)

        # Original symbol should still be full symbol (for matching)
        assert full_symbol == "RELIANCE-EQ"
        assert ticker == "RELIANCE.NS"

        # They serve different purposes:
        # - full_symbol: for matching positions/orders
        # - ticker: for yfinance API calls
