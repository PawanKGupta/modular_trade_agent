"""
Tests for ManualOrderMatcher reconciliation with symbol normalization
and pre_existing_qty validation.

Tests the fixes for:
1. Symbol mismatch (MIRZAINT-EQ vs MIRZAINT)
2. Stale pre_existing_qty causing false manual sell detection
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.manual_order_matcher import ManualOrderMatcher  # noqa: E402
from modules.kotak_neo_auto_trader.tracking_scope import TrackingScope  # noqa: E402


@pytest.fixture
def mock_tracking_scope():
    """Create a mock TrackingScope"""
    scope = Mock(spec=TrackingScope)
    scope.get_tracked_symbols = Mock(return_value=[])
    scope.get_tracking_entry = Mock(return_value=None)
    scope.update_tracked_qty = Mock()
    scope.add_related_order = Mock()
    return scope


@pytest.fixture
def manual_matcher(mock_tracking_scope):
    """Create ManualOrderMatcher instance with mocked dependencies"""
    return ManualOrderMatcher(tracking_scope=mock_tracking_scope)


class TestSymbolNormalizationInReconciliation:
    """Test symbol normalization fixes for reconciliation"""

    def test_reconcile_handles_symbol_mismatch_with_eq_suffix(
        self, manual_matcher, mock_tracking_scope
    ):
        """Test that reconciliation handles MIRZAINT-EQ (tracked) vs MIRZAINT (holdings)"""
        # Setup: Tracked symbol is MIRZAINT-EQ, holdings has MIRZAINT
        tracked_symbol = "MIRZAINT-EQ"
        mock_tracking_scope.get_tracked_symbols.return_value = [tracked_symbol]

        tracking_entry = {
            "current_tracked_qty": 267,
            "pre_existing_qty": 0,
            "symbol": tracked_symbol,
        }
        mock_tracking_scope.get_tracking_entry.return_value = tracking_entry

        # Broker holdings: MIRZAINT (without -EQ suffix)
        broker_holdings = [
            {
                "symbol": "MIRZAINT",  # Base symbol, no -EQ suffix
                "qty": 267,
            }
        ]

        # Execute reconciliation
        result = manual_matcher.reconcile_holdings_with_tracking(broker_holdings)

        # Verify: Should match (normalized lookup should work)
        assert result["matched"] == 1
        assert result["manual_buys_detected"] == 0
        assert result["manual_sells_detected"] == 0
        assert len(result["discrepancies"]) == 0

    def test_reconcile_handles_symbol_mismatch_reverse(self, manual_matcher, mock_tracking_scope):
        """Test that reconciliation handles MIRZAINT (tracked) vs MIRZAINT-EQ (holdings)"""
        # Setup: Tracked symbol is MIRZAINT, holdings has MIRZAINT-EQ
        tracked_symbol = "MIRZAINT"
        mock_tracking_scope.get_tracked_symbols.return_value = [tracked_symbol]

        tracking_entry = {
            "current_tracked_qty": 267,
            "pre_existing_qty": 0,
            "symbol": tracked_symbol,
        }
        mock_tracking_scope.get_tracking_entry.return_value = tracking_entry

        # Broker holdings: MIRZAINT-EQ (with -EQ suffix)
        broker_holdings = [
            {
                "symbol": "MIRZAINT-EQ",  # Full symbol with -EQ suffix
                "qty": 267,
            }
        ]

        # Execute reconciliation
        result = manual_matcher.reconcile_holdings_with_tracking(broker_holdings)

        # Verify: Should match (normalized lookup should work)
        assert result["matched"] == 1
        assert result["manual_buys_detected"] == 0
        assert result["manual_sells_detected"] == 0

    def test_reconcile_detects_manual_sell_with_symbol_normalization(
        self, manual_matcher, mock_tracking_scope
    ):
        """Test that manual sell is detected correctly even with symbol normalization"""
        # Setup: Tracked symbol is RELIANCE-EQ, holdings has RELIANCE with less qty
        tracked_symbol = "RELIANCE-EQ"
        mock_tracking_scope.get_tracked_symbols.return_value = [tracked_symbol]

        tracking_entry = {
            "current_tracked_qty": 100,
            "pre_existing_qty": 0,
            "symbol": tracked_symbol,
        }
        mock_tracking_scope.get_tracking_entry.return_value = tracking_entry

        # Broker holdings: RELIANCE with 50 shares (manual partial sell)
        broker_holdings = [
            {
                "symbol": "RELIANCE",  # Base symbol
                "qty": 50,  # Less than tracked (100)
            }
        ]

        # Execute reconciliation
        result = manual_matcher.reconcile_holdings_with_tracking(broker_holdings)

        # Verify: Should detect manual sell
        assert result["matched"] == 0
        assert result["manual_sells_detected"] == 1
        assert len(result["discrepancies"]) == 1
        assert result["discrepancies"][0]["qty_diff"] == -50
        assert result["discrepancies"][0]["trade_type"] == "MANUAL_SELL"

    def test_reconcile_detects_manual_buy_with_symbol_normalization(
        self, manual_matcher, mock_tracking_scope
    ):
        """Test that manual buy is detected correctly even with symbol normalization"""
        # Setup: Tracked symbol is TCS-EQ, holdings has TCS with more qty
        tracked_symbol = "TCS-EQ"
        mock_tracking_scope.get_tracked_symbols.return_value = [tracked_symbol]

        tracking_entry = {
            "current_tracked_qty": 50,
            "pre_existing_qty": 0,
            "symbol": tracked_symbol,
        }
        mock_tracking_scope.get_tracking_entry.return_value = tracking_entry

        # Broker holdings: TCS with 80 shares (manual buy)
        broker_holdings = [
            {
                "symbol": "TCS",  # Base symbol
                "qty": 80,  # More than tracked (50)
            }
        ]

        # Execute reconciliation
        result = manual_matcher.reconcile_holdings_with_tracking(broker_holdings)

        # Verify: Should detect manual buy
        assert result["matched"] == 0
        assert result["manual_buys_detected"] == 1
        assert len(result["discrepancies"]) == 1
        assert result["discrepancies"][0]["qty_diff"] == 30
        assert result["discrepancies"][0]["trade_type"] == "MANUAL_BUY"


class TestPreExistingQtyValidation:
    """Test pre_existing_qty validation and cleanup"""

    def test_validate_cleans_stale_pre_existing_qty_when_both_zero(self, manual_matcher):
        """Test that stale pre_existing_qty is reset when broker_qty=0 and system_qty=0"""
        symbol = "MIRZAINT-EQ"
        broker_qty = 0
        system_qty = 0
        pre_existing_qty = 1096  # Stale value

        # Execute validation
        validated_qty = manual_matcher.validate_and_clean_pre_existing_qty(
            symbol, broker_qty, system_qty, pre_existing_qty
        )

        # Verify: Should be reset to 0
        assert validated_qty == 0

    def test_validate_preserves_valid_pre_existing_qty(self, manual_matcher):
        """Test that valid pre_existing_qty is preserved"""
        symbol = "RELIANCE-EQ"
        broker_qty = 150  # Broker has 150
        system_qty = 50  # System tracked 50
        pre_existing_qty = 100  # Pre-existing 100 (valid: 50 + 100 = 150)

        # Execute validation
        validated_qty = manual_matcher.validate_and_clean_pre_existing_qty(
            symbol, broker_qty, system_qty, pre_existing_qty
        )

        # Verify: Should be preserved
        assert validated_qty == 100

    def test_validate_warns_on_suspiciously_large_pre_existing_qty(self, manual_matcher, caplog):
        """Test that suspiciously large pre_existing_qty triggers warning"""
        symbol = "TCS-EQ"
        broker_qty = 0  # Broker has 0
        system_qty = 10  # System tracked 10
        pre_existing_qty = 50  # Pre-existing 50 (more than 2x system_qty)

        # Execute validation
        with caplog.at_level("WARNING"):
            validated_qty = manual_matcher.validate_and_clean_pre_existing_qty(
                symbol, broker_qty, system_qty, pre_existing_qty
            )

        # Verify: Should be preserved but warning logged
        assert validated_qty == 50
        assert "suspiciously large" in caplog.text.lower()

    def test_reconcile_resets_stale_pre_existing_qty(self, manual_matcher, mock_tracking_scope):
        """Test that reconciliation resets stale pre_existing_qty and prevents false manual sell"""
        # Setup: Tracked symbol with stale pre_existing_qty
        tracked_symbol = "MIRZAINT-EQ"
        mock_tracking_scope.get_tracked_symbols.return_value = [tracked_symbol]

        tracking_entry = {
            "current_tracked_qty": 0,  # System qty is 0
            "pre_existing_qty": 1096,  # Stale pre-existing qty
            "symbol": tracked_symbol,
        }
        mock_tracking_scope.get_tracking_entry.return_value = tracking_entry

        # Broker holdings: MIRZAINT with 0 qty (or not in holdings)
        broker_holdings = [
            {
                "symbol": "MIRZAINT",
                "qty": 0,
            }
        ]

        # Execute reconciliation
        result = manual_matcher.reconcile_holdings_with_tracking(broker_holdings)

        # Verify: Should match (pre_existing_qty should be reset to 0)
        # Expected: 0 (system: 0, pre-existing: 0 after cleanup)
        # Broker: 0
        # Should match, not detect false manual sell
        assert result["matched"] == 1
        assert result["manual_sells_detected"] == 0
        assert len(result["discrepancies"]) == 0

    def test_reconcile_handles_pre_existing_qty_with_symbol_mismatch(
        self, manual_matcher, mock_tracking_scope
    ):
        """Test reconciliation with both symbol mismatch and pre_existing_qty"""
        # Setup: Tracked symbol is MIRZAINT-EQ with pre_existing_qty
        tracked_symbol = "MIRZAINT-EQ"
        mock_tracking_scope.get_tracked_symbols.return_value = [tracked_symbol]

        tracking_entry = {
            "current_tracked_qty": 267,
            "pre_existing_qty": 0,  # No pre-existing
            "symbol": tracked_symbol,
        }
        mock_tracking_scope.get_tracking_entry.return_value = tracking_entry

        # Broker holdings: MIRZAINT with matching qty
        broker_holdings = [
            {
                "symbol": "MIRZAINT",  # Base symbol (normalized match)
                "qty": 267,
            }
        ]

        # Execute reconciliation
        result = manual_matcher.reconcile_holdings_with_tracking(broker_holdings)

        # Verify: Should match perfectly
        assert result["matched"] == 1
        assert result["manual_buys_detected"] == 0
        assert result["manual_sells_detected"] == 0

    def test_reconcile_handles_pre_existing_qty_correctly(
        self, manual_matcher, mock_tracking_scope
    ):
        """Test that reconciliation correctly includes valid pre_existing_qty in expected total"""
        # Setup: Tracked symbol with valid pre_existing_qty
        tracked_symbol = "RELIANCE-EQ"
        mock_tracking_scope.get_tracked_symbols.return_value = [tracked_symbol]

        tracking_entry = {
            "current_tracked_qty": 100,  # System bought 100
            "pre_existing_qty": 50,  # Had 50 before
            "symbol": tracked_symbol,
        }
        mock_tracking_scope.get_tracking_entry.return_value = tracking_entry

        # Broker holdings: RELIANCE with 150 total (100 + 50)
        broker_holdings = [
            {
                "symbol": "RELIANCE",
                "qty": 150,  # Matches expected: 100 + 50
            }
        ]

        # Execute reconciliation
        result = manual_matcher.reconcile_holdings_with_tracking(broker_holdings)

        # Verify: Should match perfectly
        assert result["matched"] == 1
        assert result["manual_buys_detected"] == 0
        assert result["manual_sells_detected"] == 0


class TestReconciliationEdgeCases:
    """Test edge cases in reconciliation"""

    def test_reconcile_handles_missing_tracking_entry(self, manual_matcher, mock_tracking_scope):
        """Test that reconciliation handles missing tracking entry gracefully"""
        tracked_symbol = "MISSING-EQ"
        mock_tracking_scope.get_tracked_symbols.return_value = [tracked_symbol]
        mock_tracking_scope.get_tracking_entry.return_value = None  # Entry not found

        broker_holdings = [
            {
                "symbol": "MISSING",
                "qty": 100,
            }
        ]

        # Execute reconciliation
        result = manual_matcher.reconcile_holdings_with_tracking(broker_holdings)

        # Verify: Should skip gracefully
        assert result["matched"] == 0
        assert len(result["discrepancies"]) == 0

    def test_reconcile_handles_empty_holdings(self, manual_matcher, mock_tracking_scope):
        """Test that reconciliation handles empty holdings list"""
        tracked_symbol = "RELIANCE-EQ"
        mock_tracking_scope.get_tracked_symbols.return_value = [tracked_symbol]

        tracking_entry = {
            "current_tracked_qty": 100,
            "pre_existing_qty": 0,
            "symbol": tracked_symbol,
        }
        mock_tracking_scope.get_tracking_entry.return_value = tracking_entry

        # Empty holdings
        broker_holdings = []

        # Execute reconciliation
        result = manual_matcher.reconcile_holdings_with_tracking(broker_holdings)

        # Verify: Should detect manual sell (broker_qty=0, expected=100)
        assert result["matched"] == 0
        assert result["manual_sells_detected"] == 1

    def test_reconcile_handles_multiple_symbol_variants(self, manual_matcher, mock_tracking_scope):
        """Test that reconciliation handles multiple symbol formats correctly"""
        # Setup: Multiple tracked symbols with different formats
        tracked_symbols = ["RELIANCE-EQ", "TCS", "INFY-BE"]
        mock_tracking_scope.get_tracked_symbols.return_value = tracked_symbols

        # Create tracking entries
        def get_tracking_entry(symbol, status="active"):
            entries = {
                "RELIANCE-EQ": {
                    "current_tracked_qty": 100,
                    "pre_existing_qty": 0,
                    "symbol": "RELIANCE-EQ",
                },
                "TCS": {
                    "current_tracked_qty": 50,
                    "pre_existing_qty": 0,
                    "symbol": "TCS",
                },
                "INFY-BE": {
                    "current_tracked_qty": 75,
                    "pre_existing_qty": 0,
                    "symbol": "INFY-BE",
                },
            }
            return entries.get(symbol)

        mock_tracking_scope.get_tracking_entry.side_effect = get_tracking_entry

        # Broker holdings with base symbols
        broker_holdings = [
            {"symbol": "RELIANCE", "qty": 100},  # Matches RELIANCE-EQ
            {"symbol": "TCS", "qty": 50},  # Matches TCS
            {"symbol": "INFY", "qty": 75},  # Matches INFY-BE
        ]

        # Execute reconciliation
        result = manual_matcher.reconcile_holdings_with_tracking(broker_holdings)

        # Verify: All should match
        assert result["matched"] == 3
        assert result["manual_buys_detected"] == 0
        assert result["manual_sells_detected"] == 0
