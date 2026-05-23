"""Tests for OHLCV cache debug logging toggle."""

from __future__ import annotations

import logging

from src.application.services.ohlcv_cache_logging import (
    enable_ohlcv_cache_debug,
    log_ohlcv_cache,
    ohlcv_cache_debug_enabled,
)


def test_debug_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OHLCV_CACHE_DEBUG", raising=False)
    assert not ohlcv_cache_debug_enabled()


def test_enable_sets_env(monkeypatch):
    monkeypatch.delenv("OHLCV_CACHE_DEBUG", raising=False)
    enable_ohlcv_cache_debug()
    assert ohlcv_cache_debug_enabled()


def test_log_ohlcv_cache_uses_info_when_debug(monkeypatch, caplog):
    enable_ohlcv_cache_debug()
    test_logger = logging.getLogger("test_ohlcv_cache_logging")
    with caplog.at_level(logging.DEBUG):
        log_ohlcv_cache(test_logger, "hello %s", "world")
    assert any("hello world" in r.message and r.levelname == "INFO" for r in caplog.records)
