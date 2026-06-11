"""
Generation tokens for unified trading service start/stop lifecycle.

Each start/stop bumps a per-user generation counter. Background scheduler threads
capture their generation at start; on thread exit they update DB ``service_running``
only when their generation still matches. This prevents a slow-exiting old thread
from marking the service stopped after a newer start has already set it running.
"""

from __future__ import annotations

import threading

_state_lock = threading.Lock()
_generations: dict[int, int] = {}


def bump_service_generation(user_id: int) -> int:
    """Advance lifecycle generation for *user_id* and return the new value."""
    with _state_lock:
        new_gen = _generations.get(user_id, 0) + 1
        _generations[user_id] = new_gen
        return new_gen


def current_service_generation(user_id: int) -> int:
    """Return the current lifecycle generation for *user_id* (0 if never started)."""
    with _state_lock:
        return _generations.get(user_id, 0)


def is_generation_current(user_id: int, generation: int) -> bool:
    """Return True when *generation* is still the active lifecycle for *user_id*."""
    with _state_lock:
        return _generations.get(user_id, 0) == generation


def should_apply_thread_exit_status(user_id: int, generation: int) -> bool:
    """Return True when a scheduler thread may set DB status to stopped on exit."""
    return is_generation_current(user_id, generation)


def reset_service_generation(user_id: int | None = None) -> None:
    """Clear generation state (all users or one user). Intended for tests."""
    with _state_lock:
        if user_id is None:
            _generations.clear()
        else:
            _generations.pop(user_id, None)
