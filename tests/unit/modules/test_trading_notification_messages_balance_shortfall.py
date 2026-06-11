"""Tests for balance shortfall notification message templates."""

from modules.kotak_neo_auto_trader.utils.trading_notification_messages import (
    format_balance_shortfall_plain,
    format_balance_shortfall_telegram,
)


def test_format_balance_shortfall_evening_preview():
    body = format_balance_shortfall_telegram(
        broker_symbol="RELIANCE-EQ",
        qty=10,
        close=2500.0,
        required_cash=25000.0,
        avail_cash=5000.0,
        shortfall=20000.0,
        dry_run=True,
    )
    assert "Evening Preview" in body
    assert "RELIANCE-EQ" in body
    assert "20,000" in body
    assert "9:01 AM IST" in body

    plain = format_balance_shortfall_plain(
        broker_symbol="RELIANCE-EQ",
        qty=10,
        close=2500.0,
        required_cash=25000.0,
        avail_cash=5000.0,
        shortfall=20000.0,
        dry_run=True,
    )
    assert "`" not in plain
    assert "RELIANCE-EQ" in plain


def test_format_balance_shortfall_reentry_evening_preview():
    body = format_balance_shortfall_telegram(
        broker_symbol="INFY-EQ",
        qty=8,
        close=1500.0,
        required_cash=12000.0,
        avail_cash=2000.0,
        shortfall=10000.0,
        dry_run=True,
        entry_type="reentry",
    )
    assert "Re-entry Preview" in body
    assert "INFY-EQ" in body


def test_format_balance_shortfall_reentry_partial_live():
    body = format_balance_shortfall_telegram(
        broker_symbol="RELIANCE-EQ",
        qty=100,
        close=100.0,
        required_cash=10000.0,
        avail_cash=5000.0,
        shortfall=5000.0,
        dry_run=False,
        entry_type="reentry",
        affordable_qty=50,
    )
    assert "reduced from 100" in body
    assert "Placing re-entry for 50 shares" in body


def test_format_balance_shortfall_morning_buy():
    body = format_balance_shortfall_telegram(
        broker_symbol="TCS-EQ",
        qty=5,
        close=4000.0,
        required_cash=20000.0,
        avail_cash=10000.0,
        shortfall=10000.0,
        dry_run=False,
    )
    assert "Insufficient Balance" in body
    assert "premarket_retry" in body
