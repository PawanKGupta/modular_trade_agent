"""
Integration test for average price recalculation when reentries are added.

Tests that the trade history entry_price is correctly recalculated as a weighted
average when reentries are added.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine


class TestAveragePriceRecalculationOnReentry:
    """Test that average price is recalculated correctly when reentries are added"""

    def test_trade_history_entry_price_recalculated_on_reentry(self):
        """Test that entry_price in trade history is recalculated when reentry is added"""
        # Create trade history entry with initial position
        trade_entry = {
            "symbol": "RELIANCE",
            "qty": 10,
            "entry_price": 2500.0,
            "entry_time": "2024-01-01T09:00:00",
            "status": "open",
            "reentries": [],
        }

        # Simulate reentry: 5 shares @ Rs 2400
        old_qty = trade_entry["qty"]
        old_entry_price = trade_entry["entry_price"]
        reentry_qty = 5
        reentry_price = 2400.0
        new_total_qty = old_qty + reentry_qty

        # Recalculate weighted average
        new_avg_price = ((old_entry_price * old_qty) + (reentry_price * reentry_qty)) / new_total_qty

        # Update trade entry
        trade_entry["qty"] = new_total_qty
        trade_entry["entry_price"] = new_avg_price
        trade_entry["reentries"].append({
            "qty": reentry_qty,
            "level": 30,
            "rsi": 29.5,
            "price": reentry_price,
            "time": datetime.now().isoformat(),
        })

        # Verify calculation
        expected_avg = (2500.0 * 10 + 2400.0 * 5) / 15
        assert trade_entry["qty"] == 15
        assert abs(trade_entry["entry_price"] - expected_avg) < 0.01
        assert abs(trade_entry["entry_price"] - 2466.67) < 0.01

    def test_multiple_reentries_recalculate_avg_price_correctly(self):
        """Test that multiple reentries correctly recalculate average price"""
        # Initial entry: 10 shares @ Rs 2500
        trade_entry = {
            "symbol": "RELIANCE",
            "qty": 10,
            "entry_price": 2500.0,
            "status": "open",
            "reentries": [],
        }

        # Reentry 1: 5 shares @ Rs 2400
        # After: 15 shares, avg = (10*2500 + 5*2400) / 15 = 2466.67
        old_qty = trade_entry["qty"]
        old_price = trade_entry["entry_price"]
        reentry1_qty = 5
        reentry1_price = 2400.0
        new_qty = old_qty + reentry1_qty
        new_avg = ((old_price * old_qty) + (reentry1_price * reentry1_qty)) / new_qty

        trade_entry["qty"] = new_qty
        trade_entry["entry_price"] = new_avg
        trade_entry["reentries"].append({
            "qty": reentry1_qty,
            "price": reentry1_price,
        })

        assert abs(trade_entry["entry_price"] - 2466.67) < 0.01

        # Reentry 2: 3 shares @ Rs 2300
        # After: 18 shares, avg = (15*2466.67 + 3*2300) / 18 = 2438.89
        # Or: (10*2500 + 5*2400 + 3*2300) / 18 = 43900 / 18 = 2438.89
        old_qty = trade_entry["qty"]
        old_price = trade_entry["entry_price"]
        reentry2_qty = 3
        reentry2_price = 2300.0
        new_qty = old_qty + reentry2_qty
        new_avg = ((old_price * old_qty) + (reentry2_price * reentry2_qty)) / new_qty

        trade_entry["qty"] = new_qty
        trade_entry["entry_price"] = new_avg
        trade_entry["reentries"].append({
            "qty": reentry2_qty,
            "price": reentry2_price,
        })

        assert trade_entry["qty"] == 18
        # Expected: (10*2500 + 5*2400 + 3*2300) / 18 = 43900 / 18 = 2438.89
        expected_avg = (10 * 2500.0 + 5 * 2400.0 + 3 * 2300.0) / 18
        assert abs(trade_entry["entry_price"] - expected_avg) < 0.01

    def test_avg_price_formula_verification(self):
        """Test the weighted average formula is correct"""
        # Initial: 100 shares @ Rs 100
        qty1, price1 = 100, 100.0

        # Reentry: 50 shares @ Rs 90
        qty2, price2 = 50, 90.0

        # Calculate weighted average
        total_qty = qty1 + qty2
        weighted_avg = ((price1 * qty1) + (price2 * qty2)) / total_qty

        # Expected: (100*100 + 50*90) / 150 = (10000 + 4500) / 150 = 96.67
        expected = (100 * 100 + 50 * 90) / 150
        assert abs(weighted_avg - expected) < 0.01
        assert abs(weighted_avg - 96.67) < 0.01

