"""Tests for batched balance shortfall digest formatting."""

from modules.kotak_neo_auto_trader.utils.balance_shortfall_digest import (
    BalanceShortfallItem,
    format_balance_shortfall_digest_plain,
    format_balance_shortfall_digest_telegram,
    format_balance_shortfall_digest_title,
)


def _item(
    symbol: str,
    *,
    entry_type: str = "entry",
    affordable_qty: int | None = None,
) -> BalanceShortfallItem:
    return BalanceShortfallItem(
        broker_symbol=symbol,
        qty=10,
        close=100.0,
        required_cash=1000.0,
        avail_cash=200.0,
        shortfall=800.0,
        entry_type=entry_type,  # type: ignore[arg-type]
        affordable_qty=affordable_qty,
    )


def test_digest_title_live_multi_section():
    items = [_item("AAA-EQ"), _item("BBB-EQ"), _item("CCC-EQ", entry_type="reentry")]
    title = format_balance_shortfall_digest_title(items, dry_run=False)
    assert title == "Balance Shortfall Summary — 2 entries + 1 re-entry"


def test_digest_telegram_groups_sections_and_total():
    items = [
        _item("AAA-EQ"),
        _item("BBB-EQ"),
        _item("CCC-EQ", entry_type="reentry", affordable_qty=5),
    ]
    body = format_balance_shortfall_digest_telegram(items, dry_run=False)
    assert "New entries (2):" in body
    assert "Re-entries (1):" in body
    assert "AAA-EQ" in body
    assert "CCC-EQ" in body
    assert "placing 5 shares" in body
    assert "Total shortfall: Rs 2,400" in body


def test_digest_preview_title_and_footer():
    items = [_item("AAA-EQ")]
    title = format_balance_shortfall_digest_title(items, dry_run=True)
    assert title == "Balance Shortfall Summary (Evening Preview)"
    plain = format_balance_shortfall_digest_plain(items, dry_run=True)
    assert "9:01 AM IST" in plain
