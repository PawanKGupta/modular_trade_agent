"""Runtime context for OHLCV cache behavior during live trading tasks."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Callable, TypeVar

T = TypeVar("T")

_ohlcv_cache_read_only: ContextVar[bool] = ContextVar("ohlcv_cache_read_only", default=False)

# Scheduled / run-once tasks that must not trigger NSE gap-fill or Yahoo at execution time.
OHLCV_READ_ONLY_TASK_NAMES = frozenset(
    {
        "buy_orders",
        "sell_monitor",
        "premarket_retry",
        "premarket_amo_adjustment",
    }
)


def is_ohlcv_cache_read_only() -> bool:
    """True when gap-fill and Yahoo fallback must not run (premarket / market-open tasks)."""
    return _ohlcv_cache_read_only.get()


def set_ohlcv_cache_read_only(value: bool) -> Token:
    return _ohlcv_cache_read_only.set(value)


def reset_ohlcv_cache_read_only(token: Token) -> None:
    _ohlcv_cache_read_only.reset(token)


@contextmanager
def ohlcv_cache_read_only():
    """Skip network gap-fill and Yahoo fallback for OHLCV reads in this context."""
    token = set_ohlcv_cache_read_only(True)
    try:
        yield
    finally:
        reset_ohlcv_cache_read_only(token)


def run_with_ohlcv_cache_read_only(func: Callable[[], T]) -> T:
    with ohlcv_cache_read_only():
        return func()
