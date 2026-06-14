"""
Parse Kotak Neo quote depth and format 9:05 pre-market depth log lines.

Kotak ``filter=all`` returns up to **5** levels in ``depth.buy`` and ``depth.sell``.
Observability only — does not affect order placement or sizing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

# Kotak Neo REST quote depth exposes five bid and five ask levels.
KOTAK_DEPTH_LEVELS = 5

DepthSide = Literal["buy", "sell"]

# Human-readable detail strings for INFO logs (stable for operators).
DEPTH_DETAIL_QUOTE_UNAVAILABLE = "quote API returned no data"
DEPTH_DETAIL_API_FAULT = "quote API fault response"
DEPTH_DETAIL_NO_TOKEN = "scrip token not found"
DEPTH_DETAIL_FETCH_ERROR = "depth fetch exception"
DEPTH_DETAIL_NOT_FETCHED = "depth not fetched"
DEPTH_DETAIL_EMPTY_BOOK = "API ok, no live bid/ask levels"


class DepthFetchStatus(str, Enum):
    """Whether Kotak depth was fetched and parsed successfully."""

    OK = "ok"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class DepthLevel:
    """One price level from Kotak ``depth.sell`` or ``depth.buy``."""

    price: float
    quantity: float
    orders: int


@dataclass(frozen=True)
class MarketDepthSnapshot:
    """Five bid and five ask levels plus fetch outcome metadata."""

    bid_levels: tuple[DepthLevel | None, ...]
    ask_levels: tuple[DepthLevel | None, ...]
    status: DepthFetchStatus = DepthFetchStatus.UNAVAILABLE
    status_detail: str = DEPTH_DETAIL_NOT_FETCHED


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


def unavailable_depth_snapshot(
    detail: str, *, max_levels: int = KOTAK_DEPTH_LEVELS
) -> MarketDepthSnapshot:
    """Build a snapshot when depth could not be loaded (log-only)."""
    return MarketDepthSnapshot(
        bid_levels=_empty_depth(max_levels),
        ask_levels=_empty_depth(max_levels),
        status=DepthFetchStatus.UNAVAILABLE,
        status_detail=detail,
    )


def _live_level_count(
    bid_levels: tuple[DepthLevel | None, ...],
    ask_levels: tuple[DepthLevel | None, ...],
) -> int:
    return sum(1 for level in (*bid_levels, *ask_levels) if level is not None)


def _classify_parsed_depth(
    bid_levels: tuple[DepthLevel | None, ...],
    ask_levels: tuple[DepthLevel | None, ...],
) -> MarketDepthSnapshot:
    if _live_level_count(bid_levels, ask_levels) > 0:
        return MarketDepthSnapshot(
            bid_levels=bid_levels,
            ask_levels=ask_levels,
            status=DepthFetchStatus.OK,
            status_detail="",
        )
    return MarketDepthSnapshot(
        bid_levels=bid_levels,
        ask_levels=ask_levels,
        status=DepthFetchStatus.EMPTY,
        status_detail=DEPTH_DETAIL_EMPTY_BOOK,
    )


def _quote_failure_detail(data: Any) -> str | None:
    """Return a failure detail when ``data`` has no parseable quote row."""
    if data is None:
        return DEPTH_DETAIL_QUOTE_UNAVAILABLE
    if isinstance(data, dict) and "fault" in data:
        return DEPTH_DETAIL_API_FAULT
    if isinstance(data, list):
        if not data:
            return DEPTH_DETAIL_QUOTE_UNAVAILABLE
        if all(isinstance(item, dict) and "fault" in item for item in data):
            return DEPTH_DETAIL_API_FAULT
    if _first_valid_quote_row(data) is None:
        return DEPTH_DETAIL_QUOTE_UNAVAILABLE
    return None


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
    bid_levels = extract_depth_side_from_quote_row(row, "buy", max_levels=max_levels)
    ask_levels = extract_depth_side_from_quote_row(row, "sell", max_levels=max_levels)
    return _classify_parsed_depth(bid_levels, ask_levels)


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
    failure = _quote_failure_detail(data)
    if failure is not None:
        return unavailable_depth_snapshot(failure, max_levels=max_levels)

    row = _first_valid_quote_row(data)
    assert row is not None  # guarded by _quote_failure_detail
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
    snapshot: MarketDepthSnapshot,
    entry_type: str | None = None,
) -> str:
    """Build observability text for bid and ask depth at 9:05."""
    kind = entry_type or "buy"
    ltp_part = f"LTP Rs {ltp:.2f}" if ltp and ltp > 0 else "LTP N/A"
    status_tag = snapshot.status.value

    if snapshot.status == DepthFetchStatus.UNAVAILABLE:
        return (
            f"{symbol} ({kind}): pre-market depth [{status_tag}] — "
            f"{snapshot.status_detail}; {ltp_part}"
        )

    if snapshot.status == DepthFetchStatus.EMPTY:
        return (
            f"{symbol} ({kind}): pre-market depth [{status_tag}] — "
            f"{snapshot.status_detail}; {ltp_part}"
        )

    bids = _format_side_depth("bids", snapshot.bid_levels)
    asks = _format_side_depth("asks", snapshot.ask_levels)
    return (
        f"{symbol} ({kind}): pre-market depth [{status_tag}] — "
        f"{bids}; {asks}; {ltp_part}"
    )


def format_premarket_ask_depth_log(
    symbol: str,
    *,
    ltp: float | None,
    ask_levels: tuple[DepthLevel | None, ...],
    entry_type: str | None = None,
) -> str:
    """Ask-only formatter (backward compatible)."""
    empty_bids = _empty_depth(KOTAK_DEPTH_LEVELS)
    live_asks = sum(1 for level in ask_levels if level is not None)
    if live_asks == 0:
        snapshot = MarketDepthSnapshot(
            bid_levels=empty_bids,
            ask_levels=ask_levels,
            status=DepthFetchStatus.EMPTY,
            status_detail=DEPTH_DETAIL_EMPTY_BOOK,
        )
    else:
        snapshot = MarketDepthSnapshot(
            bid_levels=empty_bids,
            ask_levels=ask_levels,
            status=DepthFetchStatus.OK,
            status_detail="",
        )
    return format_premarket_depth_log(symbol, ltp=ltp, snapshot=snapshot, entry_type=entry_type)


def log_premarket_depth(
    logger: logging.Logger,
    symbol: str,
    *,
    ltp: float | None,
    snapshot: MarketDepthSnapshot,
    entry_type: str | None = None,
) -> None:
    """Log bid and ask depth at 9:05; failures must not propagate to callers."""
    try:
        message = format_premarket_depth_log(
            symbol,
            ltp=ltp,
            snapshot=snapshot,
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
    empty_bids = _empty_depth(KOTAK_DEPTH_LEVELS)
    live_asks = sum(1 for level in ask_levels if level is not None)
    if live_asks == 0:
        snapshot = MarketDepthSnapshot(
            bid_levels=empty_bids,
            ask_levels=ask_levels,
            status=DepthFetchStatus.EMPTY,
            status_detail=DEPTH_DETAIL_EMPTY_BOOK,
        )
    else:
        snapshot = MarketDepthSnapshot(
            bid_levels=empty_bids,
            ask_levels=ask_levels,
            status=DepthFetchStatus.OK,
            status_detail="",
        )
    log_premarket_depth(
        logger, symbol, ltp=ltp, snapshot=snapshot, entry_type=entry_type
    )


format_premarket_best_ask_log = format_premarket_ask_depth_log
log_premarket_best_ask = log_premarket_ask_depth
