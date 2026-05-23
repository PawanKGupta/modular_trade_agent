"""Unit tests for OHLCV bulk-analysis CSV operator fields."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.application.services import ohlcv_bulk_ops
from src.application.services.ohlcv_bulk_ops import (
    apply_ohlcv_ops_fields,
    record_analysis_yahoo_calls,
    reset_symbol_yahoo_counter,
)


def test_record_analysis_yahoo_calls_stores_counter():
    row: dict = {"ticker": "X.NS"}
    with patch.object(ohlcv_bulk_ops, "get_ohlcv_cache_stats", return_value={"yahoo_calls": 3}):
        record_analysis_yahoo_calls(row)
    assert row["_yahoo_calls_analysis"] == 3


def test_apply_ohlcv_ops_fields_sums_analysis_and_backtest():
    row = {"ticker": "Y.NS", "_yahoo_calls_analysis": 2}
    with patch.object(ohlcv_bulk_ops, "get_ohlcv_cache_stats", return_value={"yahoo_calls": 1}):
        with patch.object(ohlcv_bulk_ops, "_read_cache_health_status", return_value="healthy"):
            apply_ohlcv_ops_fields(row, "Y.NS")
    assert row["yahoo_calls"] == 3
    assert row["cache_health_status"] == "healthy"
    assert "_yahoo_calls_analysis" not in row


def test_apply_ohlcv_ops_fields_respects_health_override():
    row = {"ticker": "Z.NS", "_yahoo_calls_analysis": 0}
    with patch.object(ohlcv_bulk_ops, "get_ohlcv_cache_stats", return_value={"yahoo_calls": 0}):
        apply_ohlcv_ops_fields(row, "Z.NS", cache_health_override="skipped")
    assert row["cache_health_status"] == "skipped"


def test_reset_symbol_yahoo_counter_delegates():
    with patch.object(ohlcv_bulk_ops, "reset_ohlcv_cache_stats") as reset:
        reset_symbol_yahoo_counter()
    reset.assert_called_once()


def test_read_cache_health_disabled_when_cache_off():
    with patch.object(ohlcv_bulk_ops, "OHLCV_CACHE_ENABLED", False):
        assert ohlcv_bulk_ops._read_cache_health_status("A.NS") == "disabled"


def test_read_cache_health_empty_when_no_meta_rows():
    mock_db = MagicMock()
    mock_repo = MagicMock()
    mock_repo.get_symbol_meta.return_value = MagicMock(row_count=0)
    with patch.object(ohlcv_bulk_ops, "OHLCV_CACHE_ENABLED", True):
        with patch("src.infrastructure.db.session.SessionLocal", return_value=mock_db):
            with patch(
                "src.infrastructure.persistence.price_cache_repository.PriceCacheRepository",
                return_value=mock_repo,
            ):
                assert ohlcv_bulk_ops._read_cache_health_status("B.NS") == "empty"
    mock_db.close.assert_called_once()
