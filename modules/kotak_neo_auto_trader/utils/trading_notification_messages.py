"""
Compact trading notification message templates (Telegram Markdown).

Observability for operators — short lines, no duplicate timestamps in body.
"""

from __future__ import annotations

from modules.kotak_neo_auto_trader.utils.market_depth_utils import (
    DepthFetchStatus,
    MarketDepthSnapshot,
)


def _format_depth_hint(snapshot: MarketDepthSnapshot | None) -> str | None:
    """One-line best bid/ask when depth fetch succeeded."""
    if snapshot is None or snapshot.status != DepthFetchStatus.OK:
        return None
    best_bid = next((level for level in snapshot.bid_levels if level is not None), None)
    best_ask = next((level for level in snapshot.ask_levels if level is not None), None)
    parts: list[str] = []
    if best_ask is not None:
        parts.append(f"Ask ₹{best_ask.price:.2f}×{best_ask.quantity:g}")
    if best_bid is not None:
        parts.append(f"Bid ₹{best_bid.price:.2f}×{best_bid.quantity:g}")
    return " · ".join(parts) if parts else None


def format_premarket_adjusted_telegram(
    *,
    symbol: str,
    entry_type: str | None,
    original_qty: int,
    new_qty: int,
    premarket_ltp: float,
    gap_pct: float,
    market_depth: MarketDepthSnapshot | None = None,
) -> str:
    """Telegram body for 9:05 pre-market MARKET finalize (ORDER_MODIFIED preference)."""
    kind = entry_type or "buy"
    qty_part = f"qty {original_qty}→{new_qty} MARKET"
    price_part = f"LTP ₹{premarket_ltp:.2f} ({gap_pct:+.1f}%)"
    lines = [f"*9:05 Pre-market* · `{symbol}` ({kind})", f"{qty_part} · {price_part}"]
    depth_line = _format_depth_hint(market_depth)
    if depth_line:
        lines.append(depth_line)
    return "\n".join(lines)


def format_premarket_ema9_cancel_telegram(
    *,
    symbol: str,
    entry_type: str | None,
    premarket_ltp: float,
    ema9: float,
    ema9_threshold: float,
) -> str:
    """Telegram body for 9:05 EMA9 gap-up cancel (ORDER_CANCELLED preference)."""
    kind = entry_type or "buy"
    return (
        f"*9:05 Cancelled* · `{symbol}` ({kind})\n"
        f"Pre-open ₹{premarket_ltp:.2f} > EMA9−1% ₹{ema9_threshold:.2f} "
        f"(EMA9 ₹{ema9:.2f})"
    )


def strip_markdown_for_plain(text: str) -> str:
    """Best-effort plain text from Telegram Markdown bodies."""
    plain = text.replace("`", "")
    for marker in ("**", "*", "__", "_"):
        plain = plain.replace(marker, "")
    return plain


def format_balance_shortfall_telegram(
    *,
    broker_symbol: str,
    qty: int,
    close: float,
    required_cash: float,
    avail_cash: float | None,
    shortfall: float,
    dry_run: bool,
    entry_type: str = "entry",
) -> str:
    """Telegram body for insufficient buy margin (evening preview or morning buy)."""
    is_reentry = entry_type == "reentry"
    if dry_run:
        if is_reentry:
            header = "*Insufficient Margin (Evening Re-entry Preview)*"
        else:
            header = "*Insufficient Margin (Evening Preview)*"
        footer = "No order placed. Fund account before morning buy run (9:01 AM IST)."
    elif is_reentry:
        header = "*Insufficient Balance - Re-entry BUY*"
        footer = "Re-entry saved for retry at premarket_retry or manually."
    else:
        header = "*Insufficient Balance - BUY*"
        footer = "Order saved for retry at premarket_retry or manually."
    return (
        f"{header}\n\n"
        f"Symbol: `{broker_symbol}`\n"
        f"Needed: Rs {required_cash:,.0f} for {qty} @ Rs {close:.2f}\n"
        f"Available: Rs {(avail_cash or 0.0):,.0f}\n"
        f"Shortfall: Rs {shortfall:,.0f}\n\n"
        f"{footer}"
    )


def format_balance_shortfall_plain(
    *,
    broker_symbol: str,
    qty: int,
    close: float,
    required_cash: float,
    avail_cash: float | None,
    shortfall: float,
    dry_run: bool,
    entry_type: str = "entry",
) -> str:
    """Plain-text body for in-app and email balance shortfall alerts."""
    return strip_markdown_for_plain(
        format_balance_shortfall_telegram(
            broker_symbol=broker_symbol,
            qty=qty,
            close=close,
            required_cash=required_cash,
            avail_cash=avail_cash,
            shortfall=shortfall,
            dry_run=dry_run,
            entry_type=entry_type,
        )
    )


def format_premarket_task_in_app_summary(summary: dict[str, int]) -> str:
    """One-line in-app summary after premarket_amo_adjustment task completes."""
    adjusted = int(summary.get("adjusted") or 0)
    cancelled = int(summary.get("cancelled_above_ema9") or 0)
    failed = int(summary.get("modification_failed") or 0)
    parts: list[str] = []
    if adjusted:
        parts.append(f"{adjusted} adjusted")
    if cancelled:
        parts.append(f"{cancelled} cancelled (EMA9)")
    if failed:
        parts.append(f"{failed} failed")
    if not parts:
        return "9:05 pre-market: no order changes."
    return f"9:05 pre-market: {', '.join(parts)}."
