"""Carry-forward loss (high-water mark) performance fee invoice calculator.

Pure logic: no I/O. Monetary inputs/outputs are dimensionless numbers (same unit as PnL),
e.g. INR or paise, as long as all three inputs share the same unit.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any


def _d(value: Decimal | float | int | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def compute_performance_fee_invoice(
    previous_carry_forward_loss: Decimal | float | int | str,
    current_month_pnl: Decimal | float | int | str,
    fee_percentage: Decimal | float | int | str,
) -> dict[str, Any]:
    """
    Apply loss recovery before fees; never charge on negative net profit after recovery.

    Returns a dict suitable for JSON serialization (float values).
    """
    prev = _d(previous_carry_forward_loss)
    cur = _d(current_month_pnl)
    fee_pct = _d(fee_percentage)

    if prev < 0:
        prev = Decimal("0")
    if fee_pct < 0:
        fee_pct = Decimal("0")

    if cur < 0:
        new_carry = prev + (-cur)
        chargeable = Decimal("0")
    elif prev > 0:
        net = cur - prev
        if net > 0:
            chargeable = net
            new_carry = Decimal("0")
        else:
            chargeable = Decimal("0")
            new_carry = abs(net)
    else:
        chargeable = cur
        new_carry = Decimal("0")

    if chargeable < 0:
        chargeable = Decimal("0")

    if chargeable == 0:
        fee_amount = Decimal("0")
    else:
        fee_amount = (chargeable * (fee_pct / Decimal("100"))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    payable = fee_amount

    def _num(x: Decimal) -> float:
        return float(x.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))

    return {
        "current_month_pnl": _num(cur),
        "previous_carry_forward_loss": _num(prev),
        "chargeable_profit": _num(chargeable),
        "fee_amount": _num(fee_amount),
        "new_carry_forward_loss": _num(new_carry),
        "payable_amount": _num(payable),
    }
