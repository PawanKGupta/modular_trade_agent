#!/usr/bin/env python3
"""
Unified sell target (EMA9) calculation for paper and live broker paths.

Uses the same realtime EMA9 formula everywhere; LTP comes from PriceService
(Kotak live cache when configured, otherwise Yahoo). Does not require Kotak for paper.
"""

from __future__ import annotations

from decimal import ROUND_UP, Decimal
from typing import TYPE_CHECKING, Any

from utils.logger import logger

if TYPE_CHECKING:
    from modules.kotak_neo_auto_trader.services.indicator_service import IndicatorService
    from modules.kotak_neo_auto_trader.services.price_service import PriceService


def round_sell_price(
    price: float,
    *,
    exchange: str = "NSE",
    symbol: str | None = None,
    scrip_master: Any | None = None,
) -> float:
    """
    Round price to exchange tick size (scrip master when available, else NSE/BSE rules).

    Matches SellOrderManager.round_to_tick_size behavior for placement parity.
    """
    if price <= 0:
        return price

    tick_size = None
    if symbol and scrip_master:
        try:
            tick_size = scrip_master.get_tick_size(symbol, exchange=exchange)
        except Exception as e:
            logger.debug(f"Tick size lookup failed for {symbol}: {e}")

    if tick_size is None or tick_size <= 0:
        if exchange.upper() == "BSE":
            tick_size = 0.01 if price < 10 else 0.05
        elif price >= 1000:
            tick_size = 0.10
        else:
            tick_size = 0.05

    price_decimal = Decimal(str(price))
    tick_decimal = Decimal(str(tick_size))
    rounded = (price_decimal / tick_decimal).quantize(Decimal("1"), rounding=ROUND_UP) * tick_decimal
    return float(rounded.quantize(Decimal("0.01")))


def compute_sell_target(
    ticker: str,
    *,
    broker_symbol: str | None = None,
    indicator_service: IndicatorService | None = None,
    price_service: PriceService | None = None,
    live_price_manager: Any | None = None,
    scrip_master: Any | None = None,
    exchange: str = "NSE",
    round_price: bool = True,
    current_ltp: float | None = None,
) -> float | None:
    """
    Compute EMA9 sell target using the same path as live SellOrderManager.

    LTP resolution (via PriceService when live_price_manager is None for paper):
      1. Kotak LivePriceCache when provided and populated
      2. Yahoo / cached 1m OHLCV
      3. Yesterday's EMA9 only (inside calculate_ema9_realtime)

    Args:
        ticker: Yahoo ticker (e.g. RELIANCE.NS)
        broker_symbol: Full trading symbol (e.g. RELIANCE-EQ) for LTP lookup
        indicator_service: Optional; created with price_service if omitted
        price_service: Optional; created with live_price_manager if omitted
        live_price_manager: LivePriceCache for broker; None for paper
        scrip_master: Optional KotakNeoScripMaster for tick rounding
        exchange: NSE or BSE for tick rules
        round_price: Apply tick-size rounding when True
        current_ltp: Optional explicit LTP (skips price fetch)

    Returns:
        Target price or None if EMA9 cannot be computed
    """
    from modules.kotak_neo_auto_trader.services import (  # noqa: PLC0415
        get_indicator_service,
        get_price_service,
    )
    ps = price_service or get_price_service(
        live_price_manager=live_price_manager, enable_caching=True
    )
    ind = indicator_service or get_indicator_service(price_service=ps, enable_caching=True)

    ema9 = ind.calculate_ema9_realtime(
        ticker=ticker,
        broker_symbol=broker_symbol,
        current_ltp=current_ltp,
    )
    if ema9 is None or ema9 <= 0:
        return None

    if not round_price:
        return ema9

    tick_symbol = broker_symbol
    if not tick_symbol:
        base = ticker.replace(".NS", "").replace(".BO", "")
        tick_symbol = f"{base}-EQ" if base else None
    rounded = round_sell_price(ema9, exchange=exchange, symbol=tick_symbol, scrip_master=scrip_master)
    if rounded != ema9:
        logger.debug(
            f"Sell target rounded {tick_symbol or ticker}: Rs {ema9:.4f} -> Rs {rounded:.2f} (tick)"
        )
    return rounded
