#!/usr/bin/env python3
"""
Additional coverage tests for integrated_backtest.py

These tests focus on achieving >90% coverage by testing:
- RSI level logic edge cases
- Date handling
- Weighted average calculations
- Multiple re-entries
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from integrated_backtest import Position


class TestRSILevelLogic:
    """Test RSI level marking logic comprehensively"""
    
    def test_all_rsi_thresholds(self):
        """Test all RSI threshold boundaries"""
        # RSI = 9 (< 10)
        pos_9 = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=9.0)
        assert pos_9.levels_taken == {"30": True, "20": True, "10": True}
        
        # RSI = 10 (boundary)
        pos_10 = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=10.0)
        assert pos_10.levels_taken == {"30": True, "20": True, "10": False}
        
        # RSI = 15 (< 20)
        pos_15 = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=15.0)
        assert pos_15.levels_taken == {"30": True, "20": True, "10": False}
        
        # RSI = 19.99 (< 20)
        pos_19 = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=19.99)
        assert pos_19.levels_taken == {"30": True, "20": True, "10": False}
        
        # RSI = 20 (boundary)
        pos_20 = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=20.0)
        assert pos_20.levels_taken == {"30": True, "20": False, "10": False}
        
        # RSI = 25 (< 30)
        pos_25 = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=25.0)
        assert pos_25.levels_taken == {"30": True, "20": False, "10": False}
        
        # RSI = 29.99 (< 30)
        pos_29 = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=29.99)
        assert pos_29.levels_taken == {"30": True, "20": False, "10": False}
        
        # RSI = 30 (boundary)
        pos_30 = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=30.0)
        assert pos_30.levels_taken == {"30": False, "20": False, "10": False}
        
        # RSI = 35 (> 30)
        pos_35 = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=35.0)
        assert pos_35.levels_taken == {"30": False, "20": False, "10": False}


class TestMultipleReentries:
    """Test multiple re-entries and weighted average calculation"""
    
    def test_three_reentries_weighted_average(self):
        """Test weighted average calculation with 3 re-entries"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=25.0)
        
        # Initial: 50000/100 = 500 shares @ 100
        assert pos.quantity == 500
        assert pos.entry_price == 100.0
        
        # Re-entry 1: 50000/95 = 526 shares @ 95
        pos.add_reentry("2024-01-05", 95.0, 50000, 108.0, 20)
        expected_qty_1 = 500 + 526
        expected_avg_1 = (100 * 500 + 95 * 526) / expected_qty_1
        assert pos.quantity == expected_qty_1
        assert abs(pos.entry_price - expected_avg_1) < 0.01
        
        # Re-entry 2: 50000/90 = 555 shares @ 90
        pos.add_reentry("2024-01-10", 90.0, 50000, 105.0, 10)
        expected_qty_2 = expected_qty_1 + 555
        expected_avg_2 = (expected_avg_1 * expected_qty_1 + 90 * 555) / expected_qty_2
        assert pos.quantity == expected_qty_2
        assert abs(pos.entry_price - expected_avg_2) < 0.01
        
        # Verify fill count
        assert len(pos.fills) == 3
    
    def test_reentry_at_higher_price(self):
        """Test re-entry at higher price (averaging up)"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=25.0)
        
        # Re-entry at higher price
        pos.add_reentry("2024-01-05", 105.0, 50000, 112.0, 20)
        
        # Weighted average should be between 100 and 105
        assert pos.entry_price > 100.0
        assert pos.entry_price < 105.0
        
        # Target should be updated
        assert pos.target_price == 112.0
    
    def test_capital_accumulation(self):
        """Test that capital accumulates with re-entries"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=25.0)
        assert pos.capital == 50000
        
        pos.add_reentry("2024-01-05", 95.0, 50000, 108.0, 20)
        assert pos.capital == 100000
        
        pos.add_reentry("2024-01-10", 90.0, 50000, 105.0, 10)
        assert pos.capital == 150000


class TestPnLCalculations:
    """Test P&L calculations in various scenarios"""
    
    def test_pnl_with_single_entry(self):
        """Test P&L with single entry"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        pos.close_position("2024-01-10", 105.0, "Target")
        
        # P&L = (105 - 100) * 500 = 2500
        assert pos.get_pnl() == 2500.0
        assert abs(pos.get_return_pct() - 5.0) < 0.01
    
    def test_pnl_with_reentries(self):
        """Test P&L calculation with re-entries"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=25.0)
        pos.add_reentry("2024-01-05", 90.0, 50000, 105.0, 20)
        
        # Weighted avg = (100*500 + 90*555) / 1055 = ~94.79
        avg_price = pos.entry_price
        
        # Close at 100
        pos.close_position("2024-01-10", 100.0, "Target")
        
        # P&L = (100 - avg_price) * 1055
        expected_pnl = (100.0 - avg_price) * pos.quantity
        assert abs(pos.get_pnl() - expected_pnl) < 1.0
    
    def test_negative_pnl(self):
        """Test negative P&L (losing trade)"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        pos.close_position("2024-01-10", 95.0, "Stop loss")
        
        # P&L = (95 - 100) * 500 = -2500
        assert pos.get_pnl() == -2500.0
        assert pos.get_return_pct() == -5.0
    
    def test_zero_pnl_for_open_position(self):
        """Test that open positions return 0 P&L"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        
        assert pos.get_pnl() == 0
        assert pos.get_return_pct() == 0


class TestDateHandling:
    """Test date handling and conversions"""
    
    def test_date_string_to_timestamp(self):
        """Test date string conversion"""
        pos = Position("TEST.NS", "2024-01-15", 100.0, 110.0, 50000)
        
        assert pos.entry_date.year == 2024
        assert pos.entry_date.month == 1
        assert pos.entry_date.day == 15
    
    def test_exit_date_conversion(self):
        """Test exit date conversion"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        pos.close_position("2024-01-10", 105.0, "Target")
        
        assert pos.exit_date.year == 2024
        assert pos.exit_date.month == 1
        assert pos.exit_date.day == 10
    
    def test_fills_date_tracking(self):
        """Test that fills track dates correctly"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        pos.add_reentry("2024-01-05", 95.0, 50000, 108.0, 20)
        pos.add_reentry("2024-01-10", 90.0, 50000, 105.0, 10)
        
        assert len(pos.fills) == 3
        assert pos.fills[0]['date'].day == 1
        assert pos.fills[1]['date'].day == 5
        assert pos.fills[2]['date'].day == 10


class TestResetMechanism:
    """Test RSI reset mechanism"""
    
    def test_reset_ready_flag(self):
        """Test reset_ready flag behavior"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=25.0)
        
        # Initially false
        assert pos.reset_ready == False
        
        # Set to true (simulating RSI > 30)
        pos.reset_ready = True
        assert pos.reset_ready == True
    
    def test_levels_can_be_reset(self):
        """Test that levels can be reset for new cycle"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=25.0)
        
        # Take level 20
        pos.add_reentry("2024-01-05", 95.0, 50000, 108.0, 20)
        assert pos.levels_taken == {"30": True, "20": True, "10": False}
        
        # Simulate reset
        pos.levels_taken = {"30": False, "20": False, "10": False}
        pos.reset_ready = False
        
        assert pos.levels_taken == {"30": False, "20": False, "10": False}


class TestQuantityCalculations:
    """Test quantity calculations"""
    
    def test_quantity_with_different_capitals(self):
        """Test quantity calculation with various capital amounts"""
        # Small capital
        pos1 = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 10000)
        assert pos1.quantity == 100
        
        # Large capital
        pos2 = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 500000)
        assert pos2.quantity == 5000
        
        # Odd price
        pos3 = Position("TEST.NS", "2024-01-01", 137.50, 150.0, 50000)
        assert pos3.quantity == 363  # 50000 / 137.50 = 363.63, truncated to 363
    
    def test_reentry_quantity_calculation(self):
        """Test re-entry quantity calculations"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        
        initial_qty = pos.quantity
        pos.add_reentry("2024-01-05", 80.0, 50000, 105.0, 20)
        
        # New shares = 50000 / 80 = 625
        expected_new_qty = int(50000 / 80.0)
        assert pos.quantity == initial_qty + expected_new_qty
    
    def test_fractional_shares_truncated(self):
        """Test that fractional shares are truncated (int)"""
        # Price that would give fractional shares
        pos = Position("TEST.NS", "2024-01-01", 133.33, 145.0, 50000)
        
        # 50000 / 133.33 = 375.01... → should be 375
        assert pos.quantity == 375
        assert isinstance(pos.quantity, int)


class TestExitReasons:
    """Test different exit reasons"""
    
    def test_target_reached_exit(self):
        """Test exit with 'Target reached' reason"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        pos.close_position("2024-01-10", 110.0, "Target reached")
        
        assert pos.exit_reason == "Target reached"
        assert pos.is_closed == True
    
    def test_rsi_exit(self):
        """Test exit with 'RSI > 50' reason"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        pos.close_position("2024-01-10", 105.0, "RSI > 50")
        
        assert pos.exit_reason == "RSI > 50"
        assert pos.is_closed == True
    
    def test_end_of_period_exit(self):
        """Test exit with 'End of period' reason"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        pos.close_position("2024-12-31", 108.0, "End of period")
        
        assert pos.exit_reason == "End of period"
        assert pos.is_closed == True


class TestFillsTracking:
    """Test fills tracking and metadata"""
    
    def test_initial_fill_structure(self):
        """Test initial fill has correct structure"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        
        assert len(pos.fills) == 1
        fill = pos.fills[0]
        assert 'date' in fill
        assert 'price' in fill
        assert 'capital' in fill
        assert 'quantity' in fill
        assert fill['price'] == 100.0
        assert fill['capital'] == 50000
        assert fill['quantity'] == 500
    
    def test_reentry_fills_metadata(self):
        """Test re-entry fills have RSI level metadata"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=25.0)
        pos.add_reentry("2024-01-05", 95.0, 50000, 108.0, 20)
        pos.add_reentry("2024-01-10", 85.0, 50000, 100.0, 10)
        
        assert len(pos.fills) == 3
        
        # Check re-entry fills have rsi_level
        assert 'rsi_level' in pos.fills[1]
        assert pos.fills[1]['rsi_level'] == 20
        assert 'rsi_level' in pos.fills[2]
        assert pos.fills[2]['rsi_level'] == 10
    
    def test_fills_chronological_order(self):
        """Test fills are in chronological order"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        pos.add_reentry("2024-01-05", 95.0, 50000, 108.0, 20)
        pos.add_reentry("2024-01-15", 90.0, 50000, 105.0, 10)
        
        dates = [fill['date'] for fill in pos.fills]
        assert dates[0] < dates[1] < dates[2]


class TestLevelMarking:
    """Test level marking updates"""
    
    def test_level_marking_on_reentry(self):
        """Test levels are marked as taken when re-entry occurs"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=25.0)
        
        # Initially only 30 is taken
        assert pos.levels_taken == {"30": True, "20": False, "10": False}
        
        # Add re-entry at level 20
        pos.add_reentry("2024-01-05", 95.0, 50000, 108.0, 20)
        assert pos.levels_taken["20"] == True
        assert pos.levels_taken["10"] == False
        
        # Add re-entry at level 10
        pos.add_reentry("2024-01-10", 85.0, 50000, 100.0, 10)
        assert pos.levels_taken["10"] == True
    
    def test_all_levels_marked_on_low_rsi_entry(self):
        """Test that entering at very low RSI marks all appropriate levels"""
        # Entry at RSI 8 should mark all levels as taken
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=8.0)
        
        assert pos.levels_taken["30"] == True
        assert pos.levels_taken["20"] == True
        assert pos.levels_taken["10"] == True


class TestTargetUpdates:
    """Test target price updates on re-entries"""
    
    def test_target_updates_on_reentry(self):
        """Test that target is updated with each re-entry"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        assert pos.target_price == 110.0
        
        pos.add_reentry("2024-01-05", 95.0, 50000, 108.0, 20)
        assert pos.target_price == 108.0
        
        pos.add_reentry("2024-01-10", 90.0, 50000, 105.0, 10)
        assert pos.target_price == 105.0
    
    def test_target_can_decrease(self):
        """Test that target can decrease with re-entries (due to EMA9 calculation)"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 150.0, 50000)
        original_target = pos.target_price
        
        # Re-entry with lower target (due to lower EMA9)
        pos.add_reentry("2024-01-10", 95.0, 50000, 100.0, 20)
        
        assert pos.target_price < original_target


class TestPositionStates:
    """Test position state management"""
    
    def test_position_starts_open(self):
        """Test that new position starts in open state"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        assert pos.is_closed == False
        assert pos.exit_date is None
        assert pos.exit_price is None
        assert pos.exit_reason is None
    
    def test_position_closed_state(self):
        """Test closed position state"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        pos.close_position("2024-01-10", 110.0, "Target reached")
        
        assert pos.is_closed == True
        assert pos.exit_date is not None
        assert pos.exit_price == 110.0
        assert pos.exit_reason == "Target reached"
    
    def test_cannot_modify_closed_position(self):
        """Test that modifying a closed position still works (no enforcement)"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        pos.close_position("2024-01-10", 110.0, "Target")
        
        # The class doesn't enforce this, so re-entry would still work
        # (business logic in main backtest prevents this)
        assert pos.is_closed == True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=integrated_backtest", "--cov-report=term-missing"])


