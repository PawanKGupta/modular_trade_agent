"""
Tests for timezone utilities
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.infrastructure.db.timezone_utils import IST, ist_now, ist_to_utc, utc_to_ist


def test_ist_now():
    """Test ist_now returns timezone-aware datetime in IST"""
    result = ist_now()
    assert isinstance(result, datetime)
    assert result.tzinfo == IST
    assert result.tzinfo.utcoffset(None) == timedelta(hours=5, minutes=30)


def test_utc_to_ist_with_utc_aware():
    """Test utc_to_ist with UTC timezone-aware datetime"""
    utc_dt = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
    result = utc_to_ist(utc_dt)
    assert result.tzinfo == IST
    # IST is UTC+5:30, so 10:00 UTC = 15:30 IST
    assert result.hour == 15
    assert result.minute == 30


def test_utc_to_ist_with_naive():
    """Test utc_to_ist with naive datetime (assumed to be UTC)"""
    naive_dt = datetime(2025, 1, 15, 10, 0, 0)
    result = utc_to_ist(naive_dt)
    assert result.tzinfo == IST
    # Naive datetime is assumed UTC, so 10:00 UTC = 15:30 IST
    assert result.hour == 15
    assert result.minute == 30


def test_ist_to_utc_with_ist_aware():
    """Test ist_to_utc with IST timezone-aware datetime"""
    ist_dt = datetime(2025, 1, 15, 15, 30, 0, tzinfo=IST)
    result = ist_to_utc(ist_dt)
    assert result.tzinfo == UTC
    # IST is UTC+5:30, so 15:30 IST = 10:00 UTC
    assert result.hour == 10
    assert result.minute == 0


def test_ist_to_utc_with_naive():
    """Test ist_to_utc with naive datetime (assumed to be IST)"""
    naive_dt = datetime(2025, 1, 15, 15, 30, 0)
    result = ist_to_utc(naive_dt)
    assert result.tzinfo == UTC
    # Naive datetime is assumed IST, so 15:30 IST = 10:00 UTC
    assert result.hour == 10
    assert result.minute == 0


def test_utc_to_ist_roundtrip():
    """Test that utc_to_ist and ist_to_utc are inverse operations"""
    original_utc = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
    ist = utc_to_ist(original_utc)
    back_to_utc = ist_to_utc(ist)
    assert back_to_utc == original_utc


def test_ist_to_utc_roundtrip():
    """Test that ist_to_utc and utc_to_ist are inverse operations"""
    original_ist = datetime(2025, 1, 15, 15, 30, 0, tzinfo=IST)
    utc = ist_to_utc(original_ist)
    back_to_ist = utc_to_ist(utc)
    assert back_to_ist == original_ist

