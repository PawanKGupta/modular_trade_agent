"""Same-day same-level re-entry guard helpers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from modules.kotak_neo_auto_trader.reentry_logging import is_reentry_db_order
from src.infrastructure.db.models import OrderStatus as DbOrderStatus


def _normalize_symbol(symbol: str) -> str:
    return (
        symbol.upper()
        .replace("-EQ", "")
        .replace("-BE", "")
        .replace("-BL", "")
        .replace("-BZ", "")
        .replace(".NS", "")
        .replace(".BO", "")
    )


def _extract_reentries_list(reentries_raw: Any) -> list[dict[str, Any]]:
    if not reentries_raw:
        return []
    if isinstance(reentries_raw, dict):
        reentries = reentries_raw.get("reentries", [])
    elif isinstance(reentries_raw, list):
        reentries = reentries_raw
    else:
        return []
    if not isinstance(reentries, list):
        return []
    return [r for r in reentries if isinstance(r, dict)]


def _reentry_record_placed_date(reentry: dict[str, Any], today: date) -> date | None:
    """Return placement date for a reentry record (placed_at preferred over time)."""
    placed_at_str = reentry.get("placed_at")
    placed_at_checked = False
    if placed_at_str:
        try:
            placed_at_checked = True
            return datetime.fromisoformat(str(placed_at_str)).date()
        except (TypeError, ValueError):
            pass

    if not placed_at_checked:
        reentry_time = reentry.get("time")
        if reentry_time:
            try:
                return datetime.fromisoformat(str(reentry_time)).date()
            except (TypeError, ValueError):
                try:
                    return datetime.strptime(str(reentry_time).split("T")[0], "%Y-%m-%d").date()
                except (TypeError, ValueError):
                    return None
    return None


def reentry_level_used_today(position: Any, level: int, today: date) -> bool:
    """Return True when a filled re-entry at ``level`` was placed on ``today``."""
    if not position:
        return False

    for reentry in _extract_reentries_list(getattr(position, "reentries", None)):
        reentry_level = reentry.get("level")
        if reentry_level is None:
            continue
        try:
            if int(reentry_level) != level:
                continue
        except (TypeError, ValueError):
            continue

        placed_date = _reentry_record_placed_date(reentry, today)
        if placed_date == today:
            return True

    return False


def _order_reentry_level(order: Any) -> int | None:
    metadata = getattr(order, "order_metadata", None)
    if isinstance(metadata, dict):
        level = metadata.get("reentry_level")
        if level is not None:
            try:
                return int(level)
            except (TypeError, ValueError):
                return None
    return None


def _order_placed_date(order: Any) -> date | None:
    placed_at = getattr(order, "placed_at", None)
    if placed_at is None:
        return None
    if isinstance(placed_at, datetime):
        return placed_at.date()
    try:
        return datetime.fromisoformat(str(placed_at)).date()
    except (TypeError, ValueError):
        return None


def _pending_reentry_order_blocks(order: Any) -> bool:
    if getattr(order, "side", None) != "buy":
        return False
    if not is_reentry_db_order(order):
        return False
    status = getattr(order, "status", None)
    if status in {DbOrderStatus.PENDING, DbOrderStatus.ONGOING}:
        return getattr(order, "execution_qty", None) is None
    if status == DbOrderStatus.CLOSED:
        execution_qty = getattr(order, "execution_qty", None)
        return execution_qty is not None and float(execution_qty) > 0
    return False


def has_reentry_at_level_today(
    *,
    position: Any,
    orders: list[Any] | None,
    base_symbol: str,
    level: int,
    today: date,
) -> bool:
    """
    Return True when ``level`` already has a system re-entry today (IST date).

    Blocks on:
    - Filled re-entry records in ``position.reentries`` placed today at ``level``
    - Pending or filled re-entry buy orders placed today at ``level``

    Does not block cancelled/failed orders or re-entries placed on prior days.
    """
    if reentry_level_used_today(position, level, today):
        return True

    if not orders:
        return False

    base_clean = _normalize_symbol(base_symbol)
    for order in orders:
        order_symbol = _normalize_symbol(
            getattr(order, "base_symbol", None) or getattr(order, "symbol", "") or ""
        )
        if order_symbol != base_clean:
            continue
        if _order_reentry_level(order) != level:
            continue
        if _order_placed_date(order) != today:
            continue
        if _pending_reentry_order_blocks(order):
            return True

    return False
