"""Tests for re-entry summary log formatting."""

from modules.kotak_neo_auto_trader.reentry_logging import (
    format_reentry_check_complete,
    format_reentry_run_buy_orders_detail,
)


def test_format_reentry_run_buy_orders_detail_no_opportunity():
    summary = {
        "attempted": 1,
        "placed": 0,
        "failed_balance": 0,
        "skipped_invalid_rsi": 1,
        "skipped_duplicates": 0,
    }
    line = format_reentry_run_buy_orders_detail(summary)
    assert "Evaluated: 1" in line
    assert "Placed: 0" in line
    assert "No re-entry opportunity: 1" in line
    assert "Attempted" not in line


def test_format_reentry_check_complete_includes_skipped_other():
    summary = {
        "attempted": 2,
        "placed": 1,
        "failed_balance": 0,
        "skipped_invalid_rsi": 0,
        "skipped_duplicates": 1,
        "skipped_duplicate_level": 0,
    }
    line = format_reentry_check_complete(summary)
    assert "evaluated=2" in line
    assert "placed=1" in line
    assert "skipped_other=1" in line
    assert "attempted=" not in line
