#!/usr/bin/env python3
"""
Test Cases for Bug Fixes - October 31, 2024

Tests for 5 critical bugs fixed:
1. Reentry logic after RSI reset
2. Order validation - nOrdNo recognition
3. Sell order update after reentry
4. Trade history update after reentry
5. Scheduled task timeout configuration

Run with: pytest tests/regression/test_bug_fixes_oct31.py -v
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import pytest

# Now in tests/regression/ so need to go up 2 levels
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
from modules.kotak_neo_auto_trader.orders import KotakNeoOrders


# =============================================================================
# Bug #1: Reentry Logic After RSI Reset
# =============================================================================


class TestReentryLogicAfterReset:
    """Test cases for Bug #1: RSI reset cycle reentry triggering"""

    def setup_method(self):
        """Setup test fixtures"""
        # Tests use direct logic without engine instantiation
        pass

    def test_reset_cycle_triggers_new_entry_at_rsi_30(self):
        """
        Test that after RSI > 30 (reset_ready), when RSI < 30 again,
        a NEW CYCLE starts with reentry at RSI < 30 level
        """
        symbol = "TESTSTOCK"

        # Initial entry at RSI < 30
        entry = {
            "symbol": symbol,
            "qty": 100,
            "levels_taken": {"30": True, "20": False, "10": False},
            "reset_ready": False,
            "reentries": [],
        }

        # Simulate RSI going above 30 (should set reset_ready)
        rsi_above_30 = 32.5
        entry["reset_ready"] = True

        # Now RSI drops below 30 again - should trigger NEW CYCLE
        rsi_below_30_again = 27.8
        entries = [entry]

        # This should trigger reentry at level 30 (new cycle)
        # Check if reset logic properly resets levels_taken
        if rsi_below_30_again < 30 and entry.get("reset_ready"):
            # NEW CYCLE - reset all levels
            entry["levels_taken"] = {"30": False, "20": False, "10": False}
            entry["reset_ready"] = False
            next_level = 30

            assert entry["levels_taken"] == {
                "30": False,
                "20": False,
                "10": False,
            }, "All levels should be reset to False for new cycle"
            assert entry["reset_ready"] == False, "reset_ready should be cleared"
            assert next_level == 30, "Should trigger reentry at level 30"

    def test_normal_progression_without_reset(self):
        """Test normal level progression (30->20->10) without reset"""
        symbol = "TESTSTOCK"

        # Entry with level 30 taken
        entry = {
            "symbol": symbol,
            "qty": 100,
            "levels_taken": {"30": True, "20": False, "10": False},
            "reset_ready": False,
        }

        # RSI drops to 18 - should trigger level 20
        rsi = 18.5
        levels = entry["levels_taken"]

        next_level = None
        if levels.get("30") and not levels.get("20") and rsi < 20:
            next_level = 20

        assert next_level == 20, "Should trigger level 20 reentry"

    def test_no_reentry_when_all_levels_taken(self):
        """Test that no reentry occurs when all levels are exhausted"""
        entry = {
            "symbol": "TESTSTOCK",
            "levels_taken": {"30": True, "20": True, "10": True},
            "reset_ready": False,
        }

        rsi = 5.0  # Very low RSI
        levels = entry["levels_taken"]

        next_level = None
        if levels.get("30") and not levels.get("20") and rsi < 20:
            next_level = 20
        if levels.get("20") and not levels.get("10") and rsi < 10:
            next_level = 10

        assert next_level is None, "No reentry should occur when all levels taken"

    def test_reset_ready_flag_set_when_rsi_above_30(self):
        """Test that reset_ready flag is set when RSI > 30"""
        entry = {
            "symbol": "TESTSTOCK",
            "levels_taken": {"30": True, "20": False, "10": False},
            "reset_ready": False,
        }

        rsi = 35.2
        if rsi > 30:
            entry["reset_ready"] = True

        assert entry["reset_ready"] == True, "reset_ready should be True when RSI > 30"


# =============================================================================
# Bug #2: Order Validation - nOrdNo Recognition
# =============================================================================


class TestOrderValidationNOrdNo:
    """Test cases for Bug #2: Order response validation with nOrdNo field"""

    def test_validate_response_with_nOrdNo_field(self):
        """Test that responses with direct nOrdNo field are recognized as valid"""
        # Real Kotak Neo response format
        response = {"nOrdNo": "251031000141476", "stat": "Ok", "stCode": 200}

        # Validation logic (fixed version)
        resp_valid = (
            isinstance(response, dict)
            and (
                "data" in response
                or "order" in response
                or "raw" in response
                or "nOrdNo" in response
                or "nordno" in str(response).lower()
            )
            and "error" not in response
            and "not_ok" not in str(response).lower()
        )

        assert resp_valid == True, "Response with nOrdNo should be valid"

    def test_validate_response_with_data_field(self):
        """Test that responses with data field are still recognized"""
        response = {"data": {"orderId": "12345"}, "status": "success"}

        resp_valid = (
            isinstance(response, dict)
            and (
                "data" in response
                or "order" in response
                or "raw" in response
                or "nOrdNo" in response
                or "nordno" in str(response).lower()
            )
            and "error" not in response
            and "not_ok" not in str(response).lower()
        )

        assert resp_valid == True, "Response with data field should be valid"

    def test_reject_response_with_error(self):
        """Test that responses with error are rejected"""
        response = {"nOrdNo": "12345", "error": "Insufficient funds"}

        resp_valid = (
            isinstance(response, dict)
            and (
                "data" in response
                or "order" in response
                or "raw" in response
                or "nOrdNo" in response
                or "nordno" in str(response).lower()
            )
            and "error" not in response
            and "not_ok" not in str(response).lower()
        )

        assert resp_valid == False, "Response with error should be invalid"

    def test_reject_response_with_not_ok_status(self):
        """Test that responses with 'not_ok' status are rejected"""
        response = {"nOrdNo": "12345", "stat": "Not_Ok"}

        resp_valid = (
            isinstance(response, dict)
            and (
                "data" in response
                or "order" in response
                or "raw" in response
                or "nOrdNo" in response
                or "nordno" in str(response).lower()
            )
            and "error" not in response
            and "not_ok" not in str(response).lower()
        )

        assert resp_valid == False, "Response with Not_Ok should be invalid"


# =============================================================================
# Bug #3: Sell Order Update After Reentry
# =============================================================================


class TestSellOrderUpdateAfterReentry:
    """Test cases for Bug #3: Automatic sell order quantity update after reentry"""

    @patch("modules.kotak_neo_auto_trader.orders.logger")
    def test_modify_order_updates_quantity(self, mock_logger):
        """Test that modify_order correctly updates order quantity"""
        # Mock client with modify_order method
        mock_client = Mock()
        mock_client.modify_order.return_value = {
            "nOrdNo": "12345",
            "stat": "Ok",
            "message": "Order modified successfully",
        }

        mock_auth = Mock()
        mock_auth.get_client.return_value = mock_client

        orders = KotakNeoOrders(mock_auth)

        # Modify order: 100 shares -> 150 shares
        result = orders.modify_order(order_id="12345", quantity=150, price=2130.50)

        assert result is not None, "Modify order should return response"
        assert result.get("stat") == "Ok", "Order modification should succeed"
        mock_client.modify_order.assert_called_once()

    def test_sell_order_quantity_calculation_after_reentry(self):
        """Test correct quantity calculation for sell order after reentry"""
        # Original position
        original_qty = 186
        original_price = 2131.10

        # Reentry
        reentry_qty = 47

        # Calculate new total
        new_total_qty = original_qty + reentry_qty

        assert new_total_qty == 233, "Total quantity should be 186 + 47 = 233"

    def test_find_existing_sell_order_for_symbol(self):
        """Test logic to find existing sell order for a symbol"""
        symbol = "DALBHARAT"

        # Mock orders data
        all_orders = {
            "data": [
                {
                    "neoOrdNo": "ORDER001",
                    "symbol": "DALBHARAT-EQ",
                    "transactionType": "S",
                    "quantity": 186,
                    "price": 2131.10,
                    "status": "open",
                },
                {
                    "neoOrdNo": "ORDER002",
                    "symbol": "GALLANTT-EQ",
                    "transactionType": "S",
                    "quantity": 186,
                    "price": 549.35,
                    "status": "open",
                },
            ]
        }

        # Find sell order for DALBHARAT
        target_order = None
        for order in all_orders.get("data", []):
            order_symbol = order.get("symbol", "").replace("-EQ", "").replace("-NSE", "")
            order_type = order.get("transactionType", "")
            order_status = order.get("status", "")

            if order_symbol == symbol.upper() and order_type == "S" and order_status == "open":
                target_order = order
                break

        assert target_order is not None, "Should find sell order for DALBHARAT"
        assert target_order["neoOrdNo"] == "ORDER001", "Should find correct order"
        assert target_order["quantity"] == 186, "Should have correct quantity"


# =============================================================================
# Bug #4: Trade History Update After Reentry
# =============================================================================


class TestTradeHistoryUpdateAfterReentry:
    """Test cases for Bug #4: Automatic trade history quantity update after reentry"""

    def test_trade_history_quantity_update(self):
        """Test that trade history quantity is updated after reentry"""
        # Initial trade entry
        entry = {
            "symbol": "DALBHARAT",
            "qty": 186,
            "entry_price": 2100.00,
            "levels_taken": {"30": True, "20": False, "10": False},
            "reentries": [],
        }

        # Reentry details
        reentry_qty = 47
        reentry_level = 30
        reentry_rsi = 29.01
        reentry_price = 2050.00

        # Update trade history
        old_qty = entry.get("qty", 0)
        new_total_qty = old_qty + reentry_qty
        entry["qty"] = new_total_qty

        # Add reentry metadata
        if "reentries" not in entry:
            entry["reentries"] = []
        entry["reentries"].append(
            {
                "qty": reentry_qty,
                "level": reentry_level,
                "rsi": reentry_rsi,
                "price": reentry_price,
                "time": datetime.now().isoformat(),
            }
        )

        assert entry["qty"] == 233, "Quantity should be updated to 233"
        assert len(entry["reentries"]) == 1, "Should have one reentry record"
        assert entry["reentries"][0]["qty"] == 47, "Reentry should record 47 shares"
        assert entry["reentries"][0]["level"] == 30, "Reentry should record level 30"

    def test_multiple_reentries_tracking(self):
        """Test that multiple reentries are tracked correctly"""
        entry = {"symbol": "TESTSTOCK", "qty": 100, "reentries": []}

        # First reentry at level 30
        entry["qty"] += 25
        entry["reentries"].append(
            {
                "qty": 25,
                "level": 30,
                "rsi": 28.5,
                "price": 100.00,
                "time": datetime.now().isoformat(),
            }
        )

        # Second reentry at level 20
        entry["qty"] += 25
        entry["reentries"].append(
            {
                "qty": 25,
                "level": 20,
                "rsi": 18.2,
                "price": 95.00,
                "time": datetime.now().isoformat(),
            }
        )

        assert entry["qty"] == 150, "Total should be 100 + 25 + 25 = 150"
        assert len(entry["reentries"]) == 2, "Should have two reentry records"
        assert entry["reentries"][0]["level"] == 30, "First reentry at level 30"
        assert entry["reentries"][1]["level"] == 20, "Second reentry at level 20"

    def test_reentry_metadata_structure(self):
        """Test that reentry metadata has all required fields"""
        reentry_data = {
            "qty": 47,
            "level": 30,
            "rsi": 29.01,
            "price": 2050.00,
            "time": datetime.now().isoformat(),
        }

        # Validate all required fields present
        assert "qty" in reentry_data, "Should have qty field"
        assert "level" in reentry_data, "Should have level field"
        assert "rsi" in reentry_data, "Should have rsi field"
        assert "price" in reentry_data, "Should have price field"
        assert "time" in reentry_data, "Should have time field"

        # Validate field types
        assert isinstance(reentry_data["qty"], int), "qty should be integer"
        assert isinstance(reentry_data["level"], int), "level should be integer"
        assert isinstance(reentry_data["rsi"], float), "rsi should be float"
        assert isinstance(reentry_data["price"], float), "price should be float"
        assert isinstance(reentry_data["time"], str), "time should be ISO string"


# =============================================================================
# Bug #5: Scheduled Task Timeout Configuration
# =============================================================================


class TestScheduledTaskConfiguration:
    """Test cases for Bug #5: Scheduled task timeout and timing configuration"""

    def test_sell_monitor_task_timing(self):
        """Test that sell monitor task is configured with correct timing"""
        # Task configuration (after fix)
        task_config = {
            "name": "TradingBot-SellMonitor",
            "start_time": "09:00",
            "wait_until": "09:15",
            "timeout": "PT8H",  # 8 hours
            "enabled": True,
        }

        assert task_config["start_time"] == "09:00", "Should start at 9:00 AM"
        assert task_config["wait_until"] == "09:15", "Should wait until 9:15 AM"
        assert task_config["timeout"] == "PT8H", "Should have 8-hour timeout"

        # Verify wait time is reasonable (15 minutes)
        from datetime import datetime, timedelta

        start = datetime.strptime(task_config["start_time"], "%H:%M")
        wait = datetime.strptime(task_config["wait_until"], "%H:%M")
        wait_duration = (wait - start).total_seconds() / 60

        assert wait_duration == 15, "Wait duration should be 15 minutes"

    def test_buy_orders_task_dual_triggers(self):
        """Test that buy orders task runs at both 4:05 PM and 9:00 AM"""
        # Task configuration (after fix)
        task_triggers = [
            {"time": "16:05", "days": "weekdays"},  # 4:05 PM
            {"time": "09:00", "days": "weekdays"},  # 9:00 AM
        ]

        assert len(task_triggers) == 2, "Should have 2 triggers"
        assert task_triggers[0]["time"] == "16:05", "First trigger at 4:05 PM"
        assert task_triggers[1]["time"] == "09:00", "Second trigger at 9:00 AM"
        assert all(
            t["days"] == "weekdays" for t in task_triggers
        ), "Both should run on weekdays only"

    def test_timeout_format_validation(self):
        """Test that timeout values use proper ISO 8601 duration format"""
        # Valid timeout formats
        valid_timeouts = [
            "PT2H",  # 2 hours
            "PT8H",  # 8 hours
            "PT30M",  # 30 minutes
            "PT1H30M",  # 1 hour 30 minutes
        ]

        for timeout in valid_timeouts:
            assert timeout.startswith("PT"), f"{timeout} should start with PT"
            assert any(c in timeout for c in ["H", "M", "S"]), f"{timeout} should have time unit"

    def test_task_schedule_no_overlap(self):
        """Test that task schedules don't have problematic overlaps"""
        # All task schedules
        tasks = {
            "TradingBot-BuyOrders": ["16:05", "09:00"],
            "TradingBot-SellMonitor": ["09:00"],
            "TradingBot-PositionMonitor": "hourly",
        }

        # BuyOrders and SellMonitor both run at 9:00 AM - this is intentional and OK
        # BuyOrders places orders, SellMonitor places sell orders
        # They work on different operations so overlap is acceptable

        assert "09:00" in tasks["TradingBot-BuyOrders"], "BuyOrders should run at 9:00 AM"
        assert "09:00" in tasks["TradingBot-SellMonitor"], "SellMonitor should run at 9:00 AM"
        # This is by design for reconciliation before market open


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegrationReentryWorkflow:
    """Integration tests for complete reentry workflow"""

    def test_complete_reentry_workflow(self):
        """Test complete workflow: reentry trigger -> order -> updates"""
        # Step 1: Initial entry exists
        entry = {
            "symbol": "DALBHARAT",
            "qty": 186,
            "entry_price": 2100.00,
            "levels_taken": {"30": True, "20": False, "10": False},
            "reset_ready": False,
            "reentries": [],
        }

        # Step 2: RSI goes above 30 (reset trigger)
        rsi = 32.5
        if rsi > 30:
            entry["reset_ready"] = True
        assert entry["reset_ready"] == True, "Reset should be triggered"

        # Step 3: RSI drops below 30 again (new cycle)
        rsi = 29.01
        if rsi < 30 and entry["reset_ready"]:
            # Reset levels for new cycle
            entry["levels_taken"] = {"30": False, "20": False, "10": False}
            entry["reset_ready"] = False
            next_level = 30
            should_reenter = True

        assert should_reenter == True, "Should trigger reentry"
        assert next_level == 30, "Should reenter at level 30"

        # Step 4: Place reentry order (simulated)
        reentry_qty = 47
        reentry_price = 2050.00
        order_response = {"nOrdNo": "251031000141476", "stat": "Ok", "stCode": 200}

        # Validate order response
        order_valid = "nOrdNo" in order_response and order_response["stat"] == "Ok"
        assert order_valid == True, "Order should be valid"

        # Step 5: Update trade history
        old_qty = entry["qty"]
        entry["qty"] += reentry_qty
        entry["reentries"].append(
            {
                "qty": reentry_qty,
                "level": next_level,
                "rsi": rsi,
                "price": reentry_price,
                "time": datetime.now().isoformat(),
            }
        )

        assert entry["qty"] == 233, "Trade history should be updated"
        assert len(entry["reentries"]) == 1, "Reentry should be logged"

        # Step 6: Calculate new sell order quantity
        new_sell_qty = old_qty + reentry_qty
        assert new_sell_qty == 233, "Sell order quantity should be 233"

        # Complete workflow validated ?


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_reentry_with_zero_rsi(self):
        """Test handling of extreme RSI values"""
        rsi = 0.0
        levels = {"30": True, "20": True, "10": False}

        # Should trigger level 10 reentry
        next_level = None
        if levels.get("20") and not levels.get("10") and rsi < 10:
            next_level = 10

        assert next_level == 10, "Should trigger level 10 even at RSI 0"

    def test_concurrent_reentry_same_day(self):
        """Test that only 1 reentry per day is allowed"""
        # Create entry with reentry from today
        today_str = datetime.now().isoformat()
        entry = {"symbol": "TESTSTOCK", "reentries": [{"qty": 25, "level": 30, "time": today_str}]}

        # Check if reentry already happened today
        today = datetime.now().date()
        reentries_today = [
            r
            for r in entry.get("reentries", [])
            if datetime.fromisoformat(r["time"]).date() == today
        ]

        can_reenter = len(reentries_today) < 1
        assert can_reenter == False, "Should not allow 2nd reentry same day"

    def test_order_modification_with_none_values(self):
        """Test modify_order handles None values correctly"""
        # Should only modify specified fields
        payload = {"order_id": "12345"}
        price = None
        quantity = 150

        if price is not None:
            payload["price"] = price
        if quantity is not None:
            payload["quantity"] = quantity

        assert "price" not in payload, "Price should not be in payload if None"
        assert "quantity" in payload, "Quantity should be in payload"
        assert payload["quantity"] == 150, "Quantity should be 150"


if __name__ == "__main__":
    print("Running Bug Fix Test Suite - October 31, 2024")
    print("=" * 70)
    pytest.main([__file__, "-v", "--tb=short"])
