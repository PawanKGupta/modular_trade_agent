"""In-memory security event counters for operator monitoring."""

from __future__ import annotations

import threading
from collections import defaultdict

_lock = threading.Lock()
_counters: dict[str, int] = defaultdict(int)


def increment(event: str, *, amount: int = 1) -> None:
    with _lock:
        _counters[event] += amount


def get_counts() -> dict[str, int]:
    with _lock:
        return dict(_counters)


def reset_for_tests() -> None:
    with _lock:
        _counters.clear()
