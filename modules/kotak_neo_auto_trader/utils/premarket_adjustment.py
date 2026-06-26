"""
Shared helpers for 9:05 pre-market pending buy adjustment (live + paper).
"""

from __future__ import annotations

from math import floor

from modules.kotak_neo_auto_trader.utils.order_sizing_helper import apply_max_order_value_cap

PREMARKET_LIMIT_PROXY_LOG = (
    "LIMIT @ signal close was a placement proxy; finalizing MARKET for open "
    "execution at pre-market-sized qty"
)


def compute_premarket_qty(
    execution_capital: float,
    premarket_price: float,
    *,
    min_qty: int = 1,
    max_order_val: float | None = None,
) -> int:
    """
    Recalculate share count to keep notional near ``execution_capital``.

    Args:
        execution_capital: Liquidity-aware capital budget (same basis as 9:01 placement).
        premarket_price: Pre-market LTP (must be positive).
        min_qty: Minimum shares (live uses ``config.MIN_QTY``).
        max_order_val: Optional custom cap value (uses config value if None).

    Returns:
        Floored quantity, at least ``min_qty`` (or 0 if capped below min_qty).

    Raises:
        ValueError: When ``premarket_price`` is missing or non-positive.
    """
    if not premarket_price or premarket_price <= 0:
        raise ValueError("premarket_price must be positive")

    qty = max(min_qty, floor(execution_capital / premarket_price))
    return apply_max_order_value_cap(
        qty, premarket_price, min_qty, "Premarket", max_order_val=max_order_val
    )


def needs_premarket_market_finalize(*, is_limit: bool, new_qty: int, original_qty: int) -> bool:
    """
    Return True when 9:05 should modify/replace the order as MARKET.

    LIMIT pre-open orders always finalize (even when qty is unchanged) so a stale
    close proxy is not left into the open. MARKET orders finalize only on qty change.
    """
    if is_limit:
        return True
    return new_qty != original_qty
