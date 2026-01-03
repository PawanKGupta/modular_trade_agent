from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.infrastructure.db.connection_monitor import (
    check_pool_health,
    get_active_connections_count,
    get_pool_status,
    log_pool_status,
)


class _Engine:
    def __init__(self, pool: object):
        self.pool = pool


def test_get_pool_status_static_pool_returns_zero_dict():
    engine = _Engine(pool=SimpleNamespace())

    status = get_pool_status(engine)

    assert status == {
        "pool_size": 0,
        "checked_in": 0,
        "checked_out": 0,
        "overflow": 0,
        "max_overflow": 0,
        "total_connections": 0,
        "utilization_percent": 0.0,
    }


class _CounterPool:
    def __init__(
        self,
        size: int,
        checked_in: int,
        checked_out: int,
        overflow: int,
        max_overflow: int,
    ):
        self._size = size
        self._checked_in = checked_in
        self._checked_out = checked_out
        self._overflow = overflow
        self._max_overflow = max_overflow

    def size(self) -> int:
        return self._size

    def checkedin(self) -> int:
        return self._checked_in

    def checkedout(self) -> int:
        return self._checked_out

    def overflow(self) -> int:
        return self._overflow


def test_get_pool_status_uses_pool_metrics_and_utilization():
    pool = _CounterPool(size=5, checked_in=2, checked_out=1, overflow=2, max_overflow=1)
    engine = _Engine(pool=pool)

    status = get_pool_status(engine)

    assert status["pool_size"] == 5
    assert status["checked_in"] == 2
    assert status["checked_out"] == 1
    assert status["overflow"] == 2
    assert status["max_overflow"] == 1
    assert status["total_connections"] == 5
    assert status["utilization_percent"] == pytest.approx(83.333333, rel=1e-3)


def test_log_pool_status_prints_to_logger():
    pool = _CounterPool(size=3, checked_in=1, checked_out=1, overflow=0, max_overflow=1)
    engine = _Engine(pool=pool)
    logger = Mock()

    log_pool_status(engine, logger=logger)

    logger.info.assert_called_once()
    assert "DB Connection Pool Status" in logger.info.call_args[0][0]


def test_check_pool_health_detects_exhausted_pool():
    pool = _CounterPool(size=3, checked_in=0, checked_out=3, overflow=0, max_overflow=0)
    engine = _Engine(pool=pool)

    is_healthy, message = check_pool_health(engine)

    assert is_healthy is False
    assert "Connection pool exhausted" in message


def test_check_pool_health_warns_when_utilization_high():
    pool = _CounterPool(size=8, checked_in=0, checked_out=7, overflow=2, max_overflow=2)
    engine = _Engine(pool=pool)

    is_healthy, message = check_pool_health(engine)

    assert is_healthy is True
    assert "High pool utilization" in message


def test_check_pool_health_reports_healthy_status():
    pool = _CounterPool(size=10, checked_in=6, checked_out=1, overflow=1, max_overflow=4)
    engine = _Engine(pool=pool)

    is_healthy, message = check_pool_health(engine)

    assert is_healthy is True
    assert message == "Pool healthy"


def test_get_active_connections_count_handles_missing_method():
    engine = _Engine(pool=SimpleNamespace())

    assert get_active_connections_count(engine) == 0


def test_get_active_connections_count_returns_value():
    pool = _CounterPool(size=2, checked_in=0, checked_out=4, overflow=0, max_overflow=0)
    engine = _Engine(pool=pool)

    assert get_active_connections_count(engine) == 4
