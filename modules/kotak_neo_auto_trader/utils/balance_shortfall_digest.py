"""
Balance shortfall digest — batch multiple entry/re-entry shortfalls into one alert.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from modules.kotak_neo_auto_trader.utils.trading_notification_messages import strip_markdown_for_plain

EntryType = Literal["entry", "reentry"]


@dataclass(frozen=True)
class BalanceShortfallItem:
    """One symbol shortfall against full planned buy/re-entry size."""

    broker_symbol: str
    qty: int
    close: float
    required_cash: float
    avail_cash: float | None
    shortfall: float
    entry_type: EntryType
    affordable_qty: int | None = None


def _shortfall_line(item: BalanceShortfallItem, *, markdown: bool) -> str:
    sym = f"`{item.broker_symbol}`" if markdown else item.broker_symbol
    line = (
        f"• {sym} — need Rs {item.required_cash:,.0f} "
        f"({item.qty} @ Rs {item.close:.2f}); "
        f"available Rs {(item.avail_cash or 0.0):,.0f}; "
        f"shortfall Rs {item.shortfall:,.0f}"
    )
    if (
        item.entry_type == "reentry"
        and item.affordable_qty is not None
        and 0 < item.affordable_qty < item.qty
    ):
        line += f" — placing {item.affordable_qty} shares"
    return line


def _digest_title(*, dry_run: bool, entry_count: int, reentry_count: int) -> str:
    if dry_run:
        return "Balance Shortfall Summary (Evening Preview)"
    parts: list[str] = []
    if entry_count:
        parts.append(f"{entry_count} entr{'y' if entry_count == 1 else 'ies'}")
    if reentry_count:
        parts.append(f"{reentry_count} re-entr{'y' if reentry_count == 1 else 'ies'}")
    detail = " + ".join(parts) if parts else "0 shortfalls"
    return f"Balance Shortfall Summary — {detail}"


def _digest_footer(*, dry_run: bool, items: list[BalanceShortfallItem]) -> str:
    if dry_run:
        return "No orders placed. Fund account before morning buy run (9:01 AM IST)."
    has_partial_reentry = any(
        i.entry_type == "reentry"
        and i.affordable_qty is not None
        and 0 < i.affordable_qty < i.qty
        for i in items
    )
    if has_partial_reentry:
        return (
            "Partial re-entries placed at reduced size where noted. "
            "Add funds for full planned sizes. "
            "Zero-margin symbols saved for premarket_retry."
        )
    return "Orders saved for premarket_retry or manually where noted."


def format_balance_shortfall_digest_telegram(
    items: list[BalanceShortfallItem],
    *,
    dry_run: bool,
) -> str:
    """Telegram Markdown body for a batched balance shortfall digest."""
    entries = [i for i in items if i.entry_type == "entry"]
    reentries = [i for i in items if i.entry_type == "reentry"]
    total_shortfall = sum(i.shortfall for i in items)

    lines = [
        f"*{_digest_title(dry_run=dry_run, entry_count=len(entries), reentry_count=len(reentries))}*",
        "",
    ]
    if entries:
        lines.append(f"*New entries ({len(entries)}):*")
        lines.extend(_shortfall_line(i, markdown=True) for i in entries)
        lines.append("")
    if reentries:
        lines.append(f"*Re-entries ({len(reentries)}):*")
        lines.extend(_shortfall_line(i, markdown=True) for i in reentries)
        lines.append("")
    lines.append(f"Total shortfall: Rs {total_shortfall:,.0f} across {len(items)} symbol(s).")
    lines.append("")
    lines.append(_digest_footer(dry_run=dry_run, items=items))
    return "\n".join(lines)


def format_balance_shortfall_digest_plain(
    items: list[BalanceShortfallItem],
    *,
    dry_run: bool,
) -> str:
    """Plain-text digest for in-app and email."""
    return strip_markdown_for_plain(
        format_balance_shortfall_digest_telegram(items, dry_run=dry_run)
    )


def format_balance_shortfall_digest_title(
    items: list[BalanceShortfallItem],
    *,
    dry_run: bool,
) -> str:
    """Notification title for a digest (no markdown)."""
    entries = sum(1 for i in items if i.entry_type == "entry")
    reentries = sum(1 for i in items if i.entry_type == "reentry")
    return _digest_title(dry_run=dry_run, entry_count=entries, reentry_count=reentries)
