"""
Parse Kotak Neo quote depth and format 9:05 pre-market depth log lines.

Kotak ``filter=all`` returns up to **5** levels in ``depth.buy`` and ``depth.sell``.
Observability only — does not affect order placement or sizing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

# Kotak Neo REST quote depth exposes five bid and five ask levels.
KOTAK_DEPTH_LEVELS = 5

DepthSide = Literal["buy", "sell"]


@dataclass(frozen=True)
class DepthLevel:
    """One price level from Kotak ``depth.sell`` or ``depth.buy``."""

    price: float
    quantity: float
    orders: int


@dataclass(frozen=True)
class MarketDepthSnapshot:
    """Five bid and five ask levels from a single Kotak quote row."""

    bid_levels: tuple[DepthLevel | None, ...]
    ask_levels: tuple[DepthLevel | None, ...]


# Backward-compatible alias (first ask level).
BestAskLevel = DepthLevel


def _to_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(str(value).replace(",", "").strip())
        return parsed
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _parse_depth_level(level: object) -> DepthLevel | None:
    if not isinstance(level, dict):
        return None
    price = _to_float(level.get("price"))
    if price is None or price <= 0:
        return None
    quantity = _to_float(level.get("quantity")) or 0.0
    orders = _to_int(level.get("orders")) or 0
    return DepthLevel(price=price, quantity=quantity, orders=orders)


def _empty_depth(max_levels: int) -> tuple[DepthLevel | None, ...]:
    return tuple(None for _ in range(max_levels))


def extract_depth_side_from_quote_row(
    row: dict[str, Any],
    side: DepthSide,
    *,
    max_levels: int = KOTAK_DEPTH_LEVELS,
) -> tuple[DepthLevel | None, ...]:
    """
    Return up to five levels for ``buy`` (bids) or ``sell`` (asks).

    Each slot is ``None`` when Kotak returns a zero/empty level (common off-hours).
    """
    depth = row.get("depth")
    if not isinstance(depth, dict):
        return _empty_depth(max_levels)

    side_levels = depth.get(side)
    if not isinstance(side_levels, list):
        return _empty_depth(max_levels)

    parsed: list[DepthLevel | None] = []
    for level in side_levels[:max_levels]:
        parsed.append(_parse_depth_level(level))

    while len(parsed) < max_levels:
        parsed.append(None)

    return tuple(parsed[:max_levels])


def extract_market_depth_from_quote_row(
    row: dict[str, Any], *, max_levels: int = KOTAK_DEPTH_LEVELS
) -> MarketDepthSnapshot:
    """Return bid and ask depth from one Kotak ``filter=all`` quote row."""
    return MarketDepthSnapshot(
        bid_levels=extract_depth_side_from_quote_row(row, "buy", max_levels=max_levels),
        ask_levels=extract_depth_side_from_quote_row(row, "sell", max_levels=max_levels),
    )


def _first_valid_quote_row(data: Any) -> dict[str, Any] | None:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "fault" not in item:
                return item
        return None
    if isinstance(data, dict) and "fault" not in data:
        return data
    return None


def extract_market_depth_from_quote_payload(
    data: Any, *, max_levels: int = KOTAK_DEPTH_LEVELS
) -> MarketDepthSnapshot:
    """Extract bid and ask depth from Kotak quotes API list or single-row dict."""
    empty = MarketDepthSnapshot(
        bid_levels=_empty_depth(max_levels),
        ask_levels=_empty_depth(max_levels),
    )
    row = _first_valid_quote_row(data)
    if row is None:
        return empty
    return extract_market_depth_from_quote_row(row, max_levels=max_levels)


def extract_sell_depth_from_quote_row(
    row: dict[str, Any], *, max_levels: int = KOTAK_DEPTH_LEVELS
) -> tuple[DepthLevel | None, ...]:
    """Return up to five ask levels from a Kotak ``filter=all`` quote row."""
    return extract_depth_side_from_quote_row(row, "sell", max_levels=max_levels)


def extract_buy_depth_from_quote_row(
    row: dict[str, Any], *, max_levels: int = KOTAK_DEPTH_LEVELS
) -> tuple[DepthLevel | None, ...]:
    """Return up to five bid levels from a Kotak ``filter=all`` quote row."""
    return extract_depth_side_from_quote_row(row, "buy", max_levels=max_levels)


def extract_sell_depth_from_quote_payload(
    data: Any, *, max_levels: int = KOTAK_DEPTH_LEVELS
) -> tuple[DepthLevel | None, ...]:
    """Extract sell depth from Kotak quotes API list or single-row dict."""
    return extract_market_depth_from_quote_payload(data, max_levels=max_levels).ask_levels


def extract_buy_depth_from_quote_payload(
    data: Any, *, max_levels: int = KOTAK_DEPTH_LEVELS
) -> tuple[DepthLevel | None, ...]:
    """Extract buy depth from Kotak quotes API list or single-row dict."""
    return extract_market_depth_from_quote_payload(data, max_levels=max_levels).bid_levels


def extract_best_ask_from_quote_row(row: dict[str, Any]) -> DepthLevel | None:
    """Return the first non-zero ask level (best ask)."""
    for level in extract_sell_depth_from_quote_row(row):
        if level is not None:
            return level
    return None


def extract_best_bid_from_quote_row(row: dict[str, Any]) -> DepthLevel | None:
    """Return the first non-zero bid level (best bid)."""
    for level in extract_buy_depth_from_quote_row(row):
        if level is not None:
            return level
    return None


def extract_best_ask_from_quote_payload(data: Any) -> DepthLevel | None:
    """Extract best ask from Kotak quotes API list or single-row dict."""
    for level in extract_sell_depth_from_quote_payload(data):
        if level is not None:
            return level
    return None


def _format_depth_level(level: DepthLevel | None) -> str:
    if level is None:
        return "—"
    return f"Rs {level.price:.2f} × {level.quantity:g} ({level.orders} ord)"


def _format_side_depth(label: str, levels: tuple[DepthLevel | None, ...]) -> str:
    level_parts = [
        f"L{i + 1}: {_format_depth_level(level)}"
        for i, level in enumerate(levels[:KOTAK_DEPTH_LEVELS])
    ]
    available = sum(1 for level in levels if level is not None)
    liquidity = "no liquidity" if available == 0 else f"{available} live"
    return f"{label} (5 levels, {liquidity}) — {' | '.join(level_parts)}"


def format_premarket_depth_log(
    symbol: str,
    *,
    ltp: float | None,
    bid_levels: tuple[DepthLevel | None, ...],
    ask_levels: tuple[DepthLevel | None, ...],
    entry_type: str | None = None,
) -> str:
    """Build observability text for bid and ask depth at 9:05."""
    kind = entry_type or "buy"
    ltp_part = f"LTP Rs {ltp:.2f}" if ltp and ltp > 0 else "LTP N/A"
    bids = _format_side_depth("bids", bid_levels)
    asks = _format_side_depth("asks", ask_levels)
    return f"{symbol} ({kind}): pre-market depth — {bids}; {asks}; {ltp_part}"


def format_premarket_ask_depth_log(
    symbol: str,
    *,
    ltp: float | None,
    ask_levels: tuple[DepthLevel | None, ...],
    entry_type: str | None = None,
) -> str:
    """Ask-only formatter (backward compatible)."""
    kind = entry_type or "buy"
    ltp_part = f"LTP Rs {ltp:.2f}" if ltp and ltp > 0 else "LTP N/A"
    return (
        f"{symbol} ({kind}): pre-market depth — "
        f"{_format_side_depth('asks', ask_levels)}; {ltp_part}"
    )


def log_premarket_depth(
    logger: logging.Logger,
    symbol: str,
    *,
    ltp: float | None,
    bid_levels: tuple[DepthLevel | None, ...],
    ask_levels: tuple[DepthLevel | None, ...],
    entry_type: str | None = None,
) -> None:
    """Log bid and ask depth at 9:05; failures must not propagate to callers."""
    try:
        message = format_premarket_depth_log(
            symbol,
            ltp=ltp,
            bid_levels=bid_levels,
            ask_levels=ask_levels,
            entry_type=entry_type,
        )
        logger.info(message)
    except Exception as exc:  # noqa: BLE001
        logger.debug("%s: failed to log pre-market depth: %s", symbol, exc)


def log_premarket_ask_depth(
    logger: logging.Logger,
    symbol: str,
    *,
    ltp: float | None,
    ask_levels: tuple[DepthLevel | None, ...],
    entry_type: str | None = None,
) -> None:
    """Backward-compatible ask-only logger."""
    log_premarket_depth(
        logger,
        symbol,
        ltp=ltp,
        bid_levels=_empty_depth(KOTAK_DEPTH_LEVELS),
        ask_levels=ask_levels,
        entry_type=entry_type,
    )


format_premarket_best_ask_log = format_premarket_ask_depth_log
log_premarket_best_ask = log_premarket_ask_depth
