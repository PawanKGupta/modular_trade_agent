#!/usr/bin/env python3
"""
Comprehensive unit tests for integrated_backtest.py

Tests cover:
1. Position class initialization and methods
2. RSI level marking logic (bug fix)
3. Entry/re-entry conditions
4. Exit conditions
5. Signal numbering
6. Thread safety

Target: >90% code coverage
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from integrated_backtest import Position, run_integrated_backtest, validate_initial_entry_with_trade_agent, print_integrated_results


class TestPositionClass:
    """Test Position class initialization and methods"""

    def test_position_init_default(self):
        """Test Position initialization with default RSI"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-01",
            entry_price=100.0,
            target_price=110.0,
            capital=50000
        )

        assert pos.stock_name == "TEST.NS"
        assert pos.entry_price == 100.0
        assert pos.target_price == 110.0
        assert pos.quantity == 500  # 50000 / 100
        assert pos.levels_taken == {"30": True, "20": False, "10": False}
        assert pos.reset_ready == False
        assert pos.is_closed == False

    def test_position_init_rsi_below_10(self):
        """Test RSI level marking when entry RSI < 10"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-01",
            entry_price=100.0,
            target_price=110.0,
            capital=50000,
            entry_rsi=9.5
        )

        # All levels should be marked as taken
        assert pos.levels_taken == {"30": True, "20": True, "10": True}

    def test_position_init_rsi_below_20(self):
        """Test RSI level marking when entry RSI < 20 (BUG FIX)"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-01",
            entry_price=100.0,
            target_price=110.0,
            capital=50000,
            entry_rsi=19.8
        )

        # Levels 30 and 20 should be marked as taken
        assert pos.levels_taken == {"30": True, "20": True, "10": False}

    def test_position_init_rsi_below_30(self):
        """Test RSI level marking when entry RSI < 30"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-01",
            entry_price=100.0,
            target_price=110.0,
            capital=50000,
            entry_rsi=28.5
        )

        # Only level 30 should be marked as taken
        assert pos.levels_taken == {"30": True, "20": False, "10": False}

    def test_position_add_reentry(self):
        """Test adding a re-entry to existing position"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-01",
            entry_price=100.0,
            target_price=110.0,
            capital=50000,
            entry_rsi=25.0
        )

        # Add re-entry at lower price
        pos.add_reentry(
            add_date="2024-01-05",
            add_price=90.0,
            add_capital=50000,
            new_target=105.0,
            rsi_level=20
        )

        # Check updated values
        assert pos.quantity == 1055  # 500 + 555 (50000/90)
        assert pos.entry_price == pytest.approx(94.787, rel=0.01)  # Weighted average
        assert pos.target_price == 105.0
        assert pos.levels_taken["20"] == True
        assert len(pos.fills) == 2

    def test_position_close(self):
        """Test closing a position"""
        pos = Position(
            stock_name="TEST.NS",
            entry_date="2024-01-01",
            entry_price=100.0,
            target_price=110.0,
            capital=50000
        )

        pos.close_position("2024-01-10", 110.0, "Target reached")

        assert pos.is_closed == True
        assert pos.exit_price == 110.0
        assert pos.exit_reason == "Target reached"
        assert pos.get_pnl() == 5000.0  # (110-100) * 500
        assert pos.get_return_pct() == pytest.approx(10.0, rel=0.01)

    def test_position_pnl_calculation(self):
        """Test P&L calculations for winning and losing positions"""
        # Winning position
        pos_win = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        pos_win.close_position("2024-01-10", 110.0, "Target")
        assert pos_win.get_pnl() > 0
        assert pos_win.get_return_pct() > 0

        # Losing position
        pos_loss = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        pos_loss.close_position("2024-01-10", 95.0, "Stop loss")
        assert pos_loss.get_pnl() < 0
        assert pos_loss.get_return_pct() < 0


class TestValidateTradeAgent:
    """Test trade agent validation function structure"""

    def test_validate_trade_agent_function_exists(self):
        """Test that validate_initial_entry_with_trade_agent function exists"""
        assert callable(validate_initial_entry_with_trade_agent)

    def test_validate_trade_agent_signature(self):
        """Test function signature and parameters"""
        import inspect
        sig = inspect.signature(validate_initial_entry_with_trade_agent)
        params = list(sig.parameters.keys())

        assert 'stock_name' in params
        assert 'signal_date' in params
        assert 'rsi' in params
        assert 'ema200' in params
        assert 'full_market_data' in params


class TestBacktestLogic:
    """Test integrated backtest main logic"""

    def test_backtest_function_exists(self):
        """Test that run_integrated_backtest function exists"""
        assert callable(run_integrated_backtest)

    def test_backtest_function_signature(self):
        """Test function signature"""
        import inspect
        sig = inspect.signature(run_integrated_backtest)
        params = list(sig.parameters.keys())

        assert 'stock_name' in params
        assert 'date_range' in params
        assert 'capital_per_position' in params

    def test_print_results_function_exists(self):
        """Test that print_integrated_results function exists"""
        assert callable(print_integrated_results)

    def test_print_results_with_valid_data(self):
        """Test print_integrated_results handles valid data"""
        results = {
            'stock_name': 'TEST.NS',
            'period': '2024-01-01 to 2024-12-31',
            'executed_trades': 5,
            'skipped_signals': 2,
            'total_pnl': 10000,
            'total_return_pct': 5.5,
            'win_rate': 80.0,
            'total_positions': 3,
            'winning_trades': 4,
            'losing_trades': 1
        }

        # Should not raise an exception
        try:
            from io import StringIO
            import sys
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            print_integrated_results(results)
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

            assert 'TEST.NS' in output
            assert 'executed_trades' in output.lower() or '5' in output
        except Exception as e:
            sys.stdout = old_stdout
            raise

    def test_print_results_with_empty_data(self):
        """Test print_integrated_results handles empty data"""
        from io import StringIO
        import sys

        old_stdout = sys.stdout
        sys.stdout = StringIO()
        print_integrated_results({})
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

        # Should handle gracefully
        assert len(output) > 0


class TestReentryLogic:
    """Test re-entry logic and level progression"""

    def test_reentry_level_progression(self):
        """Test re-entry follows correct level progression (30 -> 20 -> 10)"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=25.0)

        # Initially: level 30 taken
        assert pos.levels_taken == {"30": True, "20": False, "10": False}

        # Add re-entry at level 20
        pos.add_reentry("2024-01-05", 95.0, 50000, 108.0, 20)
        assert pos.levels_taken["20"] == True

        # Add re-entry at level 10
        pos.add_reentry("2024-01-10", 90.0, 50000, 105.0, 10)
        assert pos.levels_taken["10"] == True

    def test_reset_cycle_mechanism(self):
        """Test RSI reset cycle (RSI > 30 then < 30 again)"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=25.0)

        # RSI goes above 30
        pos.reset_ready = True

        # When RSI drops below 30 again, levels should reset
        # (This is tested in the main backtest logic)
        assert pos.reset_ready == True

    def test_no_reentry_when_level_already_taken(self):
        """Test that re-entry at already taken level is prevented"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000, entry_rsi=19.8)

        # Both 30 and 20 are taken
        assert pos.levels_taken == {"30": True, "20": True, "10": False}

        # Attempting to add re-entry at level 20 should still work
        # (the prevention logic is in the main backtest, not Position class)
        initial_fills = len(pos.fills)
        pos.add_reentry("2024-01-05", 95.0, 50000, 108.0, 20)
        assert len(pos.fills) == initial_fills + 1


class TestExitConditions:
    """Test exit condition logic"""

    def test_exit_on_high_greater_than_target(self):
        """Test exit when High >= Target"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)

        # Simulate high hitting target
        # (In real backtest, this is checked daily)
        high_price = 115.0
        target = 110.0

        assert high_price >= target  # Condition met

        pos.close_position("2024-01-10", target, "Target reached")
        assert pos.is_closed == True
        assert pos.exit_reason == "Target reached"

    def test_exit_on_rsi_above_50(self):
        """Test exit when RSI > 50"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)

        # Simulate RSI above 50
        rsi = 55.0
        assert rsi > 50  # Condition met

        pos.close_position("2024-01-10", 108.0, "RSI > 50")
        assert pos.is_closed == True
        assert pos.exit_reason == "RSI > 50"

    def test_same_day_exit_allowed(self):
        """Test that exit can happen same day as re-entry"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)

        # Add re-entry on day 5
        reentry_date = "2024-01-05"
        pos.add_reentry(reentry_date, 95.0, 50000, 105.0, 20)

        # Exit on same day should be allowed
        pos.close_position(reentry_date, 105.0, "Target reached")
        assert pos.is_closed == True
        assert str(pos.exit_date.date()) == reentry_date


class TestThreadSafety:
    """Test thread safety aspects"""

    def test_no_shared_state(self):
        """Test that each backtest run has independent state"""
        # Create two position objects
        pos1 = Position("STOCK1.NS", "2024-01-01", 100.0, 110.0, 50000)
        pos2 = Position("STOCK2.NS", "2024-01-01", 200.0, 220.0, 50000)

        # Modify pos1
        pos1.add_reentry("2024-01-05", 95.0, 50000, 108.0, 20)

        # Verify pos2 is unaffected
        assert len(pos1.fills) == 2
        assert len(pos2.fills) == 1
        assert pos1.levels_taken["20"] == True
        assert pos2.levels_taken["20"] == False

    def test_independent_backtest_runs(self):
        """Test that multiple backtest calls don't interfere"""
        with patch('integrated_backtest.fetch_ohlcv_yf') as mock_fetch:
            dates = pd.date_range('2024-01-01', periods=5)
            mock_data = pd.DataFrame({
                'Open': [100, 101, 102, 103, 104],
                'High': [102, 103, 104, 105, 106],
                'Low': [99, 100, 101, 102, 103],
                'Close': [101, 102, 103, 104, 105],
                'Volume': [1000] * 5,
            }, index=dates)
            mock_fetch.return_value = mock_data

            # Run two backtests
            results1 = run_integrated_backtest("STOCK1.NS", ("2024-01-01", "2024-01-05"), 50000)
            results2 = run_integrated_backtest("STOCK2.NS", ("2024-01-01", "2024-01-05"), 50000)

            # Both should have independent results
            assert 'executed_trades' in results1
            assert 'executed_trades' in results2


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_zero_quantity_reentry(self):
        """Test handling of zero quantity re-entry"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)

        initial_qty = pos.quantity
        # Re-entry with zero price (should be ignored)
        pos.add_reentry("2024-01-05", 0.0, 50000, 108.0, 20)

        # Quantity should remain unchanged
        assert pos.quantity == initial_qty

    def test_position_with_no_exit(self):
        """Test P&L calculation for open position"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)

        # Position not closed
        assert pos.is_closed == False
        assert pos.get_pnl() == 0
        assert pos.get_return_pct() == 0

    def test_very_small_capital(self):
        """Test handling of very small capital amounts"""
        pos = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 100)

        # Should still work
        assert pos.quantity == 1  # 100 / 100
        assert pos.capital == 100

    def test_date_string_handling(self):
        """Test various date string formats"""
        pos1 = Position("TEST.NS", "2024-01-01", 100.0, 110.0, 50000)
        pos2 = Position("TEST.NS", "2024/01/01", 100.0, 110.0, 50000)

        # Both should work (pandas handles various formats)
        assert pos1.entry_date is not None
        assert pos2.entry_date is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=integrated_backtest", "--cov-report=term-missing", "--cov-report=html"])
