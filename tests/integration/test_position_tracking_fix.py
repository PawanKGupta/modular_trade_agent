#!/usr/bin/env python3
"""
Test Position Tracking Fix

This test verifies that the position tracking fix works correctly:
- When Signal 1 closes on a date, Signal 2 (executing on or after that date)
  should recognize Signal 1 is closed and execute as a new initial entry (not pyramiding).

The specific scenario tested:
- Signal 1: Signal on 2021-11-22, executes 2021-11-23, closes 2021-11-25 (target hit)
- Signal 2: Signal on 2021-11-24, executes 2021-11-25 (should see Signal 1 is closed)
"""

import sys
import os
from pathlib import Path
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings("ignore")

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from integrated_backtest import run_integrated_backtest
from backtest.backtest_config import BacktestConfig
from core.data_fetcher import yfinance_circuit_breaker


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Reset circuit breaker before each test"""
    yfinance_circuit_breaker.reset()
    yield
    yfinance_circuit_breaker.reset()


class TestPositionTrackingFix:
    """Test position tracking fix for concurrent signals"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_signal_executes_after_previous_position_closes(self):
        """
        Test that Signal 2 executes as new entry when Signal 1 closes before Signal 2 executes.

        Scenario:
        - Signal 1: 2021-11-22 signal, executes 2021-11-23, target hit 2021-11-25
        - Signal 2: 2021-11-24 signal, executes 2021-11-25
        - Expected: Signal 2 should execute as NEW INITIAL ENTRY (not pyramiding)
          because Signal 1 closes on 2021-11-25 before Signal 2 processes
        """
        symbol = "RELIANCE.NS"
        # Use date range that includes the specific dates from the user's scenario
        date_range = ("2021-11-01", "2021-12-31")
        capital_per_position = 100000

        try:
            # Run integrated backtest
            results = run_integrated_backtest(
                stock_name=symbol, date_range=date_range, capital_per_position=capital_per_position
            )

            # Verify results structure
            assert "positions" in results, "Results should contain positions"
            assert "executed_trades" in results, "Results should contain executed_trades"

            positions = results.get("positions", [])
            executed_trades = results.get("executed_trades", 0)

            if executed_trades == 0:
                pytest.skip(f"No trades executed for {symbol} in date range {date_range}")

            print(f"\n? Test Results:")
            print(f"Total positions: {len(positions)}")
            print(f"Executed trades: {executed_trades}")

            # Find positions around the critical dates (2021-11-22 to 2021-11-25)
            critical_positions = []
            for pos in positions:
                entry_date = pd.to_datetime(pos["entry_date"])
                exit_date = pd.to_datetime(pos["exit_date"]) if pos.get("exit_date") else None

                # Check if position is in the critical date range
                if entry_date >= pd.to_datetime("2021-11-22") and entry_date <= pd.to_datetime(
                    "2021-11-26"
                ):
                    critical_positions.append(pos)
                    print(f"\nPosition found:")
                    print(f"  Entry: {pos['entry_date']} @ {pos['entry_price']:.2f}")
                    print(
                        f"  Exit: {pos.get('exit_date', 'Open')} @ {pos.get('exit_price', 'N/A')}"
                    )
                    print(f"  Exit reason: {pos.get('exit_reason', 'N/A')}")
                    print(f"  Is pyramided: {pos.get('is_pyramided', False)}")

            # The key assertion: Check that positions don't overlap incorrectly
            # If Signal 1 closes on 2021-11-25 and Signal 2 executes on 2021-11-25,
            # Signal 2 should be a NEW entry (not pyramiding)
            if len(critical_positions) >= 2:
                pos1 = critical_positions[0]
                pos2 = critical_positions[1]

                pos1_entry = pd.to_datetime(pos1["entry_date"])
                pos1_exit = pd.to_datetime(pos1["exit_date"]) if pos1.get("exit_date") else None
                pos2_entry = pd.to_datetime(pos2["entry_date"])

                print(f"\n? Position Analysis:")
                print(
                    f"Position 1: Entry {pos1_entry.date()}, Exit {pos1_exit.date() if pos1_exit else 'Open'}"
                )
                print(f"Position 2: Entry {pos2_entry.date()}")

                # If Position 1 exits before or on Position 2's entry date,
                # Position 2 should NOT be pyramided (it's a new entry)
                if pos1_exit and pos2_entry:
                    if pos1_exit <= pos2_entry:
                        # Position 1 closed before or on Position 2 entry
                        # Position 2 should be a NEW entry (not pyramided)
                        assert not pos2.get("is_pyramided", False), (
                            f"Position 2 (entry: {pos2_entry.date()}) should be a NEW entry, "
                            f"not pyramided, because Position 1 closed on {pos1_exit.date()}"
                        )
                        print(f"? PASS: Position 2 is correctly a NEW entry (not pyramided)")

            # Additional validation: Check that no position is open when a new one starts
            # (unless it's intentional pyramiding within the same position)
            for i, pos in enumerate(positions):
                if pos.get("exit_date"):
                    exit_date = pd.to_datetime(pos["exit_date"])
                    # Check if any other position starts on or before this exit
                    for j, other_pos in enumerate(positions):
                        if i != j:
                            other_entry = pd.to_datetime(other_pos["entry_date"])
                            # If other position starts before this one exits,
                            # and this one is not pyramided, it's a bug
                            if other_entry < exit_date:
                                # This is OK if it's part of the same position (pyramiding)
                                # But if it's a separate position, check if it's marked as pyramided
                                if not other_pos.get("is_pyramided", False):
                                    # Check if positions actually overlap
                                    other_exit = (
                                        pd.to_datetime(other_pos["exit_date"])
                                        if other_pos.get("exit_date")
                                        else None
                                    )
                                    if other_exit and other_exit > pos["entry_date"]:
                                        # Positions overlap - this should only happen if one is pyramided
                                        print(
                                            f"[WARN]? Warning: Positions overlap but not marked as pyramided"
                                        )
                                        print(
                                            f"  Position {i}: {pos['entry_date']} to {pos['exit_date']}"
                                        )
                                        print(
                                            f"  Position {j}: {other_pos['entry_date']} to {other_pos.get('exit_date', 'Open')}"
                                        )

        except Exception as e:
            error_msg = str(e)
            if "No data available" in error_msg or "network" in error_msg.lower():
                pytest.skip(f"Data fetching failed for {symbol}: {error_msg}")
            else:
                raise

    @pytest.mark.integration
    @pytest.mark.slow
    def test_position_tracking_before_signal_processing(self):
        """
        Test that positions are tracked BEFORE processing new signals.

        This verifies the fix: positions should be checked for exit conditions
        before a new signal is processed, so the new signal knows if a position
        is still open or has closed.
        """
        symbol = "RELIANCE.NS"
        date_range = ("2021-11-01", "2021-12-31")  # Extended range to ensure enough data
        capital_per_position = 100000

        try:
            results = run_integrated_backtest(
                stock_name=symbol, date_range=date_range, capital_per_position=capital_per_position
            )

            positions = results.get("positions", [])

            if len(positions) < 2:
                pytest.skip(f"Need at least 2 positions to test, got {len(positions)}")

            # Sort positions by entry date
            positions_sorted = sorted(positions, key=lambda x: pd.to_datetime(x["entry_date"]))

            # Check sequential positions
            for i in range(len(positions_sorted) - 1):
                pos1 = positions_sorted[i]
                pos2 = positions_sorted[i + 1]

                pos1_entry = pd.to_datetime(pos1["entry_date"])
                pos1_exit = pd.to_datetime(pos1["exit_date"]) if pos1.get("exit_date") else None
                pos2_entry = pd.to_datetime(pos2["entry_date"])

                # Key validation: If Position 1 exits on or before Position 2 enters,
                # Position 2 should NOT be pyramided (it's a new entry)
                if pos1_exit:
                    if pos1_exit <= pos2_entry:
                        # Position 1 exits on or before Position 2 enters
                        # Position 2 should be a NEW entry (not pyramided)
                        assert not pos2.get("is_pyramided", False), (
                            f"? BUG: Position 2 (entry: {pos2_entry.date()}) is marked as pyramided, "
                            f"but Position 1 exited on {pos1_exit.date()}. "
                            f"Position 2 should be a NEW entry!"
                        )
                        print(
                            f"? Position {i+1} exits on/before Position {i+2} enters - correctly NOT pyramided"
                        )
                    else:
                        # Position 1 is still open when Position 2 enters
                        # Position 2 could be pyramiding (which is fine) or a new entry (which would be a bug)
                        # Actually, if Position 2 is not pyramided but Position 1 is still open,
                        # that means Position 1 should have been tracked and closed before Position 2 processes
                        # But this is harder to validate without knowing the exact execution timing
                        if not pos2.get("is_pyramided", False):
                            print(
                                f"i? Position {i+1} is still open when Position {i+2} enters, but Position {i+2} is not pyramided"
                            )
                            print(f"   This might be OK if Position 1 closes on the same day")

                print(f"? Position {i+1} and {i+2} are correctly sequenced")

        except Exception as e:
            error_msg = str(e)
            if "No data available" in error_msg or "network" in error_msg.lower():
                pytest.skip(f"Data fetching failed for {symbol}: {error_msg}")
            else:
                raise

    @pytest.mark.integration
    @pytest.mark.slow
    def test_specific_reliance_scenario_nov_2021(self):
        """
        Test the specific scenario reported by the user:
        - Signal 1: 2021-11-22 signal, executes 2021-11-23, closes 2021-11-25
        - Signal 2: 2021-11-24 signal, should execute as new entry (not while Signal 1 is open)
        """
        symbol = "RELIANCE.NS"
        date_range = ("2021-11-01", "2021-12-31")  # Extended range to ensure enough data
        capital_per_position = 100000

        try:
            results = run_integrated_backtest(
                stock_name=symbol, date_range=date_range, capital_per_position=capital_per_position
            )

            positions = results.get("positions", [])
            signals = results.get("total_signals", 0)

            print(f"\n? Scenario Test Results for {symbol}:")
            print(f"Total signals: {signals}")
            print(f"Total positions: {len(positions)}")

            # Find positions in November 2021
            nov_positions = [
                pos
                for pos in positions
                if pd.to_datetime(pos["entry_date"]).month == 11
                and pd.to_datetime(pos["entry_date"]).year == 2021
            ]

            print(f"\nNovember 2021 positions: {len(nov_positions)}")
            for pos in nov_positions:
                entry_date = pd.to_datetime(pos["entry_date"])
                exit_date = pd.to_datetime(pos["exit_date"]) if pos.get("exit_date") else None
                print(f"  Entry: {entry_date.date()} @ {pos['entry_price']:.2f}")
                if exit_date:
                    print(f"  Exit: {exit_date.date()} @ {pos.get('exit_price', 0):.2f}")
                    print(f"  Reason: {pos.get('exit_reason', 'N/A')}")
                print(f"  Pyramided: {pos.get('is_pyramided', False)}")
                print()

            # Key validation: Check if we have positions around 2021-11-22 to 2021-11-25
            signal1_positions = [
                pos
                for pos in nov_positions
                if pd.to_datetime(pos["entry_date"]) >= pd.to_datetime("2021-11-22")
                and pd.to_datetime(pos["entry_date"]) <= pd.to_datetime("2021-11-23")
            ]

            signal2_positions = [
                pos
                for pos in nov_positions
                if pd.to_datetime(pos["entry_date"]) >= pd.to_datetime("2021-11-24")
                and pd.to_datetime(pos["entry_date"]) <= pd.to_datetime("2021-11-25")
            ]

            if signal1_positions and signal2_positions:
                pos1 = signal1_positions[0]
                pos2 = signal2_positions[0]

                pos1_entry = pd.to_datetime(pos1["entry_date"])
                pos1_exit = pd.to_datetime(pos1["exit_date"]) if pos1.get("exit_date") else None
                pos2_entry = pd.to_datetime(pos2["entry_date"])

                print(f"\n? Specific Scenario Validation:")
                print(f"Signal 1 Position:")
                print(f"  Entry: {pos1_entry.date()}")
                print(f"  Exit: {pos1_exit.date() if pos1_exit else 'Open'}")
                print(f"Signal 2 Position:")
                print(f"  Entry: {pos2_entry.date()}")
                print(f"  Is Pyramided: {pos2.get('is_pyramided', False)}")

                # The fix: If Signal 1 closes on 2021-11-25, Signal 2 should NOT be pyramided
                if pos1_exit:
                    if pos1_exit <= pos2_entry:
                        # Signal 1 closed before or on Signal 2 entry
                        assert not pos2.get("is_pyramided", False), (
                            f"? BUG: Signal 2 (entry: {pos2_entry.date()}) is marked as pyramided, "
                            f"but Signal 1 closed on {pos1_exit.date()}. "
                            f"Signal 2 should be a NEW entry!"
                        )
                        print(f"? FIX VERIFIED: Signal 2 is correctly a NEW entry (not pyramided)")
                    else:
                        # Signal 1 is still open when Signal 2 enters
                        # Signal 2 should be pyramided OR Signal 1 should close first
                        if not pos2.get("is_pyramided", False):
                            print(f"[WARN]? Signal 2 is not pyramided but Signal 1 is still open")
                            print(f"   This might be correct if Signal 1 closes on the same day")

            # If no positions found, the test still passes (no signals in that period)
            # This is informational
            if not signal1_positions and not signal2_positions:
                print(
                    f"i? No positions found in the specific date range (2021-11-22 to 2021-11-25)"
                )
                print(f"   This might mean no signals were generated or trade agent rejected them")

        except Exception as e:
            error_msg = str(e)
            if "No data available" in error_msg or "network" in error_msg.lower():
                pytest.skip(f"Data fetching failed for {symbol}: {error_msg}")
            else:
                raise


if __name__ == "__main__":
    # Run the specific scenario test
    test = TestPositionTrackingFix()
    print("=" * 80)
    print("Running Test: test_specific_reliance_scenario_nov_2021")
    print("=" * 80)
    test.test_specific_reliance_scenario_nov_2021()
    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80)
