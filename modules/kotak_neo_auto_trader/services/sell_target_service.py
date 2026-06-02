#!/usr/bin/env python3
"""
Unified sell target (EMA9) calculation for paper and live broker paths.

Uses the same realtime EMA9 formula everywhere; LTP comes from PriceService
(Kotak live cache when configured, otherwise Yahoo). Does not require Kotak for paper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_UP, Decimal
from typing import TYPE_CHECKING, Any, Literal

from utils.logger import logger

if TYPE_CHECKING:
    from modules.kotak_neo_auto_trader.services.indicator_service import IndicatorService
    from modules.kotak_neo_auto_trader.services.price_service import PriceService

PreparedSellAction = Literal["place", "invalid_tick"]


@dataclass(frozen=True)
class PreparedSellLimit:
    """Result of normalizing a raw EMA9 target for broker limit-sell placement."""

    price: float | None
    action: PreparedSellAction
    raw_target: float
    tick_size: float | None = None
    adjustments: tuple[str, ...] = field(default_factory=tuple)


def _price_to_paise(price: float) -> int:
    """Convert rupees to integer paise, rounding up fractional paise (conservative for sell limits)."""
    return int((Decimal(str(price)) * 100).to_integral_value(rounding=ROUND_UP))


def _paise_to_rupees(paise: int) -> float:
    return float((Decimal(paise) / Decimal(100)).quantize(Decimal("0.01")))


def _tick_to_paise(tick_size: float) -> int:
    return max(1, int((Decimal(str(tick_size)) * 100).quantize(Decimal("1"))))


def nse_fallback_tick_size_by_price(price: float) -> float:
    """
    NSE cash-equity tick ladder when scrip master tick is unavailable.

    Bands align with common NSE tick rules; coarser ticks apply at higher prices.
    """
    if price < 1000:
        return 0.05
    if price < 5000:
        return 0.10
    if price < 20000:
        return 0.50
    return 1.00


def bse_fallback_tick_size_by_price(price: float) -> float:
    if price < 10:
        return 0.01
    return 0.05


def exchange_fallback_tick_size_by_price(price: float, exchange: str) -> float:
    if exchange.upper() == "BSE":
        return bse_fallback_tick_size_by_price(price)
    return nse_fallback_tick_size_by_price(price)


def resolve_tick_size(
    price: float,
    *,
    exchange: str = "NSE",
    symbol: str | None = None,
    scrip_master: Any | None = None,
) -> tuple[float, str]:
    """
    Resolve tick size in rupees for limit-price rounding.

    Uses the coarser of scrip-master tick and exchange price-band fallback so a
    fine scrip tick (e.g. 0.10) cannot leave high-priced symbols off the broker grid
    when the band requires 0.50 or 1.00 (e.g. LINDEINDIA ~7140).

    Returns:
        (tick_size_rupees, source_label) for logging
    """
    band_tick = exchange_fallback_tick_size_by_price(price, exchange)
    scrip_tick: float | None = None

    if symbol and scrip_master:
        try:
            raw_tick = scrip_master.get_tick_size(symbol, exchange=exchange)
            if raw_tick is not None:
                scrip_tick = float(raw_tick)
        except (TypeError, ValueError) as e:
            logger.debug(f"Tick size from scrip master not numeric for {symbol}: {e}")
        except Exception as e:
            logger.debug(f"Tick size lookup failed for {symbol}: {e}")

    if scrip_tick is not None and scrip_tick > 0:
        effective = max(float(scrip_tick), band_tick)
        if effective > scrip_tick:
            return effective, "scrip_master+band_floor"
        return float(scrip_tick), "scrip_master"

    return band_tick, "exchange_fallback"


def is_price_on_tick_grid(price: float, tick_size: float) -> bool:
    """True when price (paise) is an integer multiple of tick_size (paise)."""
    if price <= 0 or tick_size <= 0:
        return True
    tick_paise = _tick_to_paise(tick_size)
    return _price_to_paise(price) % tick_paise == 0


def _round_up_to_tick_paise(price_paise: int, tick_paise: int) -> int:
    if tick_paise <= 0:
        return price_paise
    return ((price_paise + tick_paise - 1) // tick_paise) * tick_paise


def round_sell_price(
    price: float,
    *,
    exchange: str = "NSE",
    symbol: str | None = None,
    scrip_master: Any | None = None,
) -> float:
    """
    Round price up to exchange tick size (scrip master when available, else NSE/BSE rules).

    Matches SellOrderManager.round_to_tick_size behavior for placement parity.
    """
    if price <= 0:
        return price

    tick_size, source = resolve_tick_size(
        price, exchange=exchange, symbol=symbol, scrip_master=scrip_master
    )
    price_paise = _price_to_paise(price)
    tick_paise = _tick_to_paise(tick_size)
    rounded_paise = _round_up_to_tick_paise(price_paise, tick_paise)
    rounded = _paise_to_rupees(rounded_paise)

    if not is_price_on_tick_grid(rounded, tick_size):
        logger.warning(
            "Sell price %s still off tick grid after round (tick=%s, source=%s, symbol=%s)",
            rounded,
            tick_size,
            source,
            symbol,
        )

    if rounded != price:
        logger.debug(
            "Sell price rounded %s: Rs %.4f -> Rs %.2f (tick=%s, source=%s)",
            symbol or exchange,
            price,
            rounded,
            tick_size,
            source,
        )
    elif not is_price_on_tick_grid(price, tick_size):
        logger.warning(
            "Sell price Rs %.4f unchanged but not on tick grid (tick=%s, source=%s, symbol=%s)",
            price,
            tick_size,
            source,
            symbol,
        )

    return rounded


def prepare_broker_sell_limit_price(
    raw_target: float,
    *,
    exchange: str = "NSE",
    symbol: str | None = None,
    scrip_master: Any | None = None,
) -> PreparedSellLimit:
    """
    Normalize a raw EMA9 target for Kotak limit-sell submission (PR1: tick grid only).

    Circuit capping is deferred to PR2; this helper is the single entry for live place/modify.
    """
    if raw_target <= 0:
        return PreparedSellLimit(
            price=None,
            action="invalid_tick",
            raw_target=raw_target,
            adjustments=("non_positive_target",),
        )

    tick_size, source = resolve_tick_size(
        raw_target, exchange=exchange, symbol=symbol, scrip_master=scrip_master
    )
    rounded = round_sell_price(
        raw_target, exchange=exchange, symbol=symbol, scrip_master=scrip_master
    )

    adjustments: list[str] = []
    if rounded != raw_target:
        adjustments.append(f"tick_round:{raw_target:.4f}->{rounded:.2f}")
    adjustments.append(f"tick={tick_size}:{source}")

    if not is_price_on_tick_grid(rounded, tick_size):
        return PreparedSellLimit(
            price=None,
            action="invalid_tick",
            raw_target=raw_target,
            tick_size=tick_size,
            adjustments=tuple(adjustments + ["off_tick_grid_after_round"]),
        )

    return PreparedSellLimit(
        price=rounded,
        action="place",
        raw_target=raw_target,
        tick_size=tick_size,
        adjustments=tuple(adjustments),
    )


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
