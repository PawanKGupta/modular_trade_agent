"""
Shared helpers for 9:05 pre-market pending buy adjustment (live + paper).
"""

from __future__ import annotations

from math import floor

PREMARKET_LIMIT_PROXY_LOG = (
    "LIMIT @ signal close was a placement proxy; finalizing MARKET for open "
    "execution at pre-market-sized qty"
)


def compute_premarket_qty(
    execution_capital: float, premarket_price: float, *, min_qty: int = 1
) -> int:
    """
    Recalculate share count to keep notional near ``execution_capital``.

    Args:
        execution_capital: Liquidity-aware capital budget (same basis as 9:01 placement).
        premarket_price: Pre-market LTP (must be positive).
        min_qty: Minimum shares (live uses ``config.MIN_QTY``).

    Returns:
        Floored quantity, at least ``min_qty``.

    Raises:
        ValueError: When ``premarket_price`` is missing or non-positive.
    """
    if not premarket_price or premarket_price <= 0:
        raise ValueError("premarket_price must be positive")
    return max(min_qty, floor(execution_capital / premarket_price))


def needs_premarket_market_finalize(
    *, is_limit: bool, new_qty: int, original_qty: int
) -> bool:
    """
    Return True when 9:05 should modify/replace the order as MARKET.

    LIMIT pre-open orders always finalize (even when qty is unchanged) so a stale
    close proxy is not left into the open. MARKET orders finalize only on qty change.
    """
    if is_limit:
        return True
    return new_qty != original_qty
