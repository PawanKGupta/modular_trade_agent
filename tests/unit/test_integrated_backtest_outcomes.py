#!/usr/bin/env python3
"""
Unit tests for ML outcome tracking in integrated_backtest.py (Phase 3).

Tests that outcome features (exit_reason, days_to_exit, max_drawdown_pct) 
are correctly tracked and exported.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
import pandas as pd
from datetime import datetime, timedelta

from integrated_backtest import Position


class TestPositionOutcomeTracking:
    """Test Position class outcome tracking features"""
    
    def test_position_initialization_includes_outcome_fields(self):
        """Test that Position initializes with outcome tracking fields"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-15",
            entry_price=1000.0,
            target_price=1100.0,
            capital=100000,
            entry_rsi=28.0
        )
        
        assert hasattr(pos, 'max_drawdown_pct')
        assert hasattr(pos, 'daily_lows')
        assert pos.max_drawdown_pct == 0.0
        assert pos.daily_lows == []
    
    def test_update_drawdown_tracks_worst_loss(self):
        """Test that update_drawdown correctly tracks worst unrealized loss"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-15",
            entry_price=1000.0,
            target_price=1100.0
        )
        
        # Simulate daily price action
        pos.update_drawdown("2024-01-16", 985.0)  # Down 1.5%
        assert pos.max_drawdown_pct == -1.5
        assert len(pos.daily_lows) == 1
        
        pos.update_drawdown("2024-01-17", 970.0)  # Down 3% (worse)
        assert pos.max_drawdown_pct == -3.0
        assert len(pos.daily_lows) == 2
        
        pos.update_drawdown("2024-01-18", 990.0)  # Recovering, but max_dd stays
        assert pos.max_drawdown_pct == -3.0  # Stays at worst
        assert len(pos.daily_lows) == 3
    
    def test_update_drawdown_no_drawdown_scenario(self):
        """Test drawdown tracking when position never goes negative"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-15",
            entry_price=1000.0,
            target_price=1100.0
        )
        
        # Price always above entry
        pos.update_drawdown("2024-01-16", 1005.0)
        pos.update_drawdown("2024-01-17", 1010.0)
        pos.update_drawdown("2024-01-18", 1020.0)
        
        assert pos.max_drawdown_pct == 0.0  # Never went negative
        assert len(pos.daily_lows) == 3
    
    def test_get_days_to_exit(self):
        """Test days_to_exit calculation"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-15",
            entry_price=1000.0,
            target_price=1100.0
        )
        
        # Before closing
        assert pos.get_days_to_exit() == 0
        
        # After closing (7 days later)
        pos.close_position("2024-01-22", 1100.0, "Target reached")
        assert pos.get_days_to_exit() == 7
    
    def test_outcome_features_in_export(self):
        """Test that outcome features are included when position is exported"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-15",
            entry_price=1000.0,
            target_price=1100.0,
            capital=100000
        )
        
        # Simulate trade journey
        pos.update_drawdown("2024-01-16", 985.0)  # -1.5%
        pos.update_drawdown("2024-01-17", 975.0)  # -2.5% (worst)
        pos.update_drawdown("2024-01-18", 995.0)  # Recovering
        pos.update_drawdown("2024-01-19", 1020.0)  # Above entry
        pos.close_position("2024-01-20", 1100.0, "Target reached")
        
        # Export would happen in backtest results
        # Verify the Position object has all required attributes
        assert pos.exit_reason == "Target reached"
        assert pos.get_days_to_exit() == 5
        assert pos.max_drawdown_pct == -2.5
        assert pos.get_pnl() > 0
        assert pos.get_return_pct() == 10.0


class TestPositionReentryWithOutcomes:
    """Test outcome tracking works with re-entries"""
    
    def test_drawdown_tracking_continues_after_reentry(self):
        """Test that drawdown tracking continues correctly after re-entry"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-15",
            entry_price=1000.0,
            target_price=1100.0,
            entry_rsi=28.0
        )
        
        # Initial decline
        pos.update_drawdown("2024-01-16", 970.0)  # -3%
        assert pos.max_drawdown_pct == -3.0
        
        # Re-entry at lower level
        pos.add_reentry("2024-01-17", 950.0, 50000, 1050.0, 20)
        
        # New average entry is (1000*100 + 950*52.63) / 152.63 ≈ 978
        # Continue tracking drawdown
        pos.update_drawdown("2024-01-18", 940.0)
        
        # Drawdown should be calculated from AVERAGE entry, not original
        # (940 - 978) / 978 * 100 ≈ -3.88%
        assert pos.max_drawdown_pct < -3.5
        assert len(pos.daily_lows) == 2
    
    def test_days_to_exit_uses_original_entry_date(self):
        """Test that days_to_exit uses original entry, not re-entry dates"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-15",
            entry_price=1000.0,
            target_price=1100.0,
            entry_rsi=28.0
        )
        
        # Re-entry 5 days later
        pos.add_reentry("2024-01-20", 950.0, 50000, 1050.0, 20)
        
        # Exit 10 days after original entry
        pos.close_position("2024-01-25", 1050.0, "Target reached")
        
        # Days should be from original entry (Jan 15) to exit (Jan 25) = 10 days
        assert pos.get_days_to_exit() == 10  # Not 5 days from re-entry


class TestOutcomeFeatureValues:
    """Test that outcome features have correct values and types"""
    
    def test_max_drawdown_is_negative_or_zero(self):
        """Test that max_drawdown is always <= 0"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-15",
            entry_price=1000.0,
            target_price=1100.0
        )
        
        pos.update_drawdown("2024-01-16", 1050.0)  # Above entry
        assert pos.max_drawdown_pct == 0.0  # Should stay at 0 when above entry
        
        pos.update_drawdown("2024-01-17", 950.0)  # Below entry
        assert pos.max_drawdown_pct < 0  # Should be negative
    
    def test_exit_reason_values(self):
        """Test exit_reason contains expected values"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-15",
            entry_price=1000.0,
            target_price=1100.0
        )
        
        # Test different exit reasons
        pos.close_position("2024-01-20", 1100.0, "Target reached")
        assert pos.exit_reason == "Target reached"
        
        pos2 = Position("TEST2.NS", "2024-01-15", 1000.0, 1100.0)
        pos2.close_position("2024-01-20", 1020.0, "RSI > 50")
        assert pos2.exit_reason == "RSI > 50"
        
        pos3 = Position("TEST3.NS", "2024-01-15", 1000.0, 1100.0)
        pos3.close_position("2024-02-15", 990.0, "End of period")
        assert pos3.exit_reason == "End of period"
    
    def test_days_to_exit_is_integer(self):
        """Test that days_to_exit returns integer"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-15",
            entry_price=1000.0,
            target_price=1100.0
        )
        
        pos.close_position("2024-01-25", 1100.0, "Target reached")
        days = pos.get_days_to_exit()
        
        assert isinstance(days, int)
        assert days == 10
    
    def test_outcome_features_for_losing_trade(self):
        """Test outcome features for a losing trade"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-15",
            entry_price=1000.0,
            target_price=1100.0
        )
        
        # Losing trade journey
        pos.update_drawdown("2024-01-16", 980.0)  # -2%
        pos.update_drawdown("2024-01-17", 960.0)  # -4%
        pos.update_drawdown("2024-01-18", 950.0)  # -5% (worst)
        pos.update_drawdown("2024-01-19", 970.0)  # Slight recovery
        pos.close_position("2024-01-20", 970.0, "RSI > 50")  # Exit at loss
        
        assert pos.get_pnl() < 0  # Loss
        assert pos.get_return_pct() == -3.0  # 3% loss
        assert pos.max_drawdown_pct == -5.0  # Worst point was -5%
        assert pos.get_days_to_exit() == 5
        assert pos.exit_reason == "RSI > 50"

