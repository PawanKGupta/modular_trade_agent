"""
Dispatch 9:05 pre-market Telegram notifications (PR1).

Failures are logged only — never raises to callers.
"""

from __future__ import annotations

import logging
from typing import Any

from modules.kotak_neo_auto_trader.utils.market_depth_utils import MarketDepthSnapshot
from modules.kotak_neo_auto_trader.utils.trading_notification_messages import (
    format_premarket_adjusted_telegram,
    format_premarket_ema9_cancel_telegram,
)

logger = logging.getLogger(__name__)


def _resolve_telegram_notifier(engine_or_adapter: Any, db_session: Any, user_id: int):
    """Resolve per-user Telegram notifier from engine/adapter or factory."""
    notifier = getattr(engine_or_adapter, "telegram_notifier", None)
    if notifier is not None and getattr(notifier, "enabled", False):
        return notifier
    try:
        from modules.kotak_neo_auto_trader.telegram_notifier import get_telegram_notifier

        return get_telegram_notifier(db_session=db_session)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not resolve Telegram notifier for user %s: %s", user_id, exc)
        return None


def _resolve_order_state_manager(engine_or_adapter: Any) -> Any | None:
    """Best-effort OrderStateManager for post-9:05 baseline sync."""
    direct = getattr(engine_or_adapter, "order_state_manager", None)
    if direct is not None:
        return direct
    sell_manager = getattr(engine_or_adapter, "sell_manager", None)
    if sell_manager is not None:
        return getattr(sell_manager, "state_manager", None)
    return None


def notify_premarket_adjusted(
    *,
    engine_or_adapter: Any,
    user_id: int,
    db_session: Any,
    symbol: str,
    order_id: str,
    entry_type: str | None,
    original_qty: int,
    new_qty: int,
    premarket_ltp: float,
    gap_pct: float,
    market_depth: MarketDepthSnapshot | None = None,
) -> None:
    """Send 9:05 adjust notification; uses ORDER_MODIFIED user preference."""
    try:
        notifier = _resolve_telegram_notifier(engine_or_adapter, db_session, user_id)
        if not notifier or not getattr(notifier, "enabled", False):
            return
        message = format_premarket_adjusted_telegram(
            symbol=symbol,
            entry_type=entry_type,
            original_qty=original_qty,
            new_qty=new_qty,
            premarket_ltp=premarket_ltp,
            gap_pct=gap_pct,
            market_depth=market_depth,
        )
        notifier.notify_premarket_adjusted(
            symbol=symbol,
            order_id=order_id,
            message_text=message,
            user_id=user_id,
        )
        state_mgr = _resolve_order_state_manager(engine_or_adapter)
        if state_mgr is not None and hasattr(state_mgr, "record_system_modification"):
            state_mgr.record_system_modification(
                order_id=order_id,
                quantity=new_qty,
                price=None,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to send 9:05 pre-market adjust notification for %s: %s",
            symbol,
            exc,
            exc_info=True,
        )


def notify_premarket_ema9_cancelled(
    *,
    engine_or_adapter: Any,
    user_id: int,
    db_session: Any,
    symbol: str,
    order_id: str,
    entry_type: str | None,
    premarket_ltp: float,
    ema9: float,
    ema9_threshold: float,
) -> None:
    """Send 9:05 EMA9 cancel notification; uses ORDER_CANCELLED user preference."""
    try:
        notifier = _resolve_telegram_notifier(engine_or_adapter, db_session, user_id)
        if not notifier or not getattr(notifier, "enabled", False):
            return
        message = format_premarket_ema9_cancel_telegram(
            symbol=symbol,
            entry_type=entry_type,
            premarket_ltp=premarket_ltp,
            ema9=ema9,
            ema9_threshold=ema9_threshold,
        )
        notifier.notify_premarket_cancelled_ema9(
            symbol=symbol,
            order_id=order_id,
            message_text=message,
            user_id=user_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to send 9:05 EMA9 cancel notification for %s: %s",
            symbol,
            exc,
            exc_info=True,
        )
