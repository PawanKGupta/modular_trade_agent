"""Human-readable logging helpers for re-entry order checks."""

from __future__ import annotations

from typing import Any


def _int(summary: dict[str, Any], key: str) -> int:
    return int(summary.get(key, 0) or 0)


def format_reentry_run_buy_orders_detail(summary: dict[str, Any]) -> str:
    """One-line breakdown after ``run_buy_orders`` re-entry phase.

    ``attempted`` counts open positions evaluated (not broker placement attempts).
    ``skipped_invalid_rsi`` means no qualifying re-entry level (RSI rules), not bad data.
    """
    evaluated = _int(summary, "attempted")
    placed = _int(summary, "placed")
    failed_balance = _int(summary, "failed_balance")
    no_opportunity = _int(summary, "skipped_invalid_rsi")
    skipped_other = (
        _int(summary, "skipped_duplicates")
        + _int(summary, "skipped_duplicate_level")
        + _int(summary, "skipped_missing_data")
        + _int(summary, "skipped_invalid_qty")
        + _int(summary, "skipped_no_position")
    )
    return (
        f"Evaluated: {evaluated}, Placed: {placed}, "
        f"Failed (balance): {failed_balance}, "
        f"No re-entry opportunity: {no_opportunity}, "
        f"Skipped (other): {skipped_other}"
    )


def format_reentry_check_complete(summary: dict[str, Any]) -> str:
    """Closing line for ``place_reentry_orders()``."""
    evaluated = _int(summary, "attempted")
    placed = _int(summary, "placed")
    failed_balance = _int(summary, "failed_balance")
    no_opportunity = _int(summary, "skipped_invalid_rsi")
    skipped_other = (
        _int(summary, "skipped_duplicates")
        + _int(summary, "skipped_duplicate_level")
        + _int(summary, "skipped_missing_data")
        + _int(summary, "skipped_invalid_qty")
        + _int(summary, "skipped_no_position")
    )
    return (
        f"Re-entry check complete: evaluated={evaluated}, placed={placed}, "
        f"failed_balance={failed_balance}, no_reentry_opportunity={no_opportunity}, "
        f"skipped_other={skipped_other}"
    )
