"""
Shared helper for order sizing and max order value capping.
"""

import logging
from decimal import Decimal
from math import floor

from modules.kotak_neo_auto_trader import config

logger = logging.getLogger(__name__)


def apply_max_order_value_cap(
    qty: int,
    price: float | Decimal,
    min_qty: int,
    symbol: str,
    max_order_val: float | Decimal | None = None,
) -> int:
    """
    Enforce MAX_ORDER_VALUE cap on a calculated quantity.

    If the order value exceeds the cap, the quantity is truncated to the
    maximum allowed size. If the resulting capped quantity is less than
    the minimum required quantity (min_qty), returns 0.

    Args:
        qty: The raw calculated quantity.
        price: Price per share.
        min_qty: Minimum quantity floor constraint.
        symbol: The ticker/broker symbol for logging.
        max_order_val: Optional custom cap value (uses config value if None).

    Returns:
        The capped quantity (or 0 if below min_qty floor).
    """
    if not isinstance(max_order_val, (int, float, Decimal)):
        max_order_val = getattr(config, "MAX_ORDER_VALUE", 500000)

    max_allowed = floor(float(max_order_val) / float(price))
    if qty > max_allowed:
        original_qty = qty
        qty = max_allowed
        logger.warning(
            "Order value for %s exceeds max order value limit of %s. "
            "Capping and truncating order quantity from %d to %d.",
            symbol,
            max_order_val,
            original_qty,
            qty,
        )
        if qty < min_qty:
            return 0

    return qty
