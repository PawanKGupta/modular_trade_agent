"""OHLCV cache console logging (opt-in via OHLCV_CACHE_DEBUG or --ohlcv-cache-debug)."""

from __future__ import annotations

import logging
import os


def ohlcv_cache_debug_enabled() -> bool:
    """True when OHLCV cache validation lines should appear at INFO on the console."""
    return os.getenv("OHLCV_CACHE_DEBUG", "false").lower() in ("1", "true", "yes", "on")


def enable_ohlcv_cache_debug() -> None:
    """Turn on INFO-level OHLCV cache lines for the current process."""
    os.environ["OHLCV_CACHE_DEBUG"] = "true"


def log_ohlcv_cache(logger: logging.Logger, msg: str, *args) -> None:
    """Log at INFO when debug enabled, else DEBUG (hidden on default trade_agent console)."""
    if ohlcv_cache_debug_enabled():
        logger.info(msg, *args)
    else:
        logger.debug(msg, *args)
