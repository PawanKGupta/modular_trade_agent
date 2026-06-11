"""
Tests for timezone utilities
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.infrastructure.db.timezone_utils import (
    IST,
    db_timestamp_to_utc_for_api,
    ist_now,
    ist_now_naive,
    ist_to_utc,
    service_status_heartbeat_age_seconds,
    utc_to_ist,
)


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


def test_service_status_heartbeat_age_utc_naive_stored_value():
    """Legacy psycopg2 storage: naive UTC must not appear ~5.5h stale vs IST now."""
    reference = datetime(2026, 6, 11, 23, 0, 46, tzinfo=IST)
    # 17:30:36 UTC naive == 23:00:36 IST (about 10s before reference)
    utc_naive = datetime(2026, 6, 11, 17, 30, 36, 700984)
    age = service_status_heartbeat_age_seconds(utc_naive, reference=reference)
    assert age is not None
    assert age < 120
    assert age > 5


def test_service_status_heartbeat_age_wrong_ist_naive_would_be_hours():
    """Document false stale: treating UTC-naive as IST gives ~19800s for this row."""
    reference = datetime(2026, 6, 11, 23, 0, 46, tzinfo=IST)
    utc_naive = datetime(2026, 6, 11, 17, 30, 36, 700984)
    wrong_age = (reference - utc_naive.replace(tzinfo=IST)).total_seconds()
    correct_age = service_status_heartbeat_age_seconds(utc_naive, reference=reference)
    assert wrong_age > 19000
    assert correct_age is not None
    assert correct_age < 120


def test_service_status_heartbeat_age_ist_naive_stored_value():
    """New writes via ist_now_naive(): naive IST wall-clock."""
    reference = datetime(2026, 6, 11, 23, 0, 46, tzinfo=IST)
    ist_naive = datetime(2026, 6, 11, 23, 0, 36)
    age = service_status_heartbeat_age_seconds(ist_naive, reference=reference)
    assert age is not None
    assert 5 < age < 20


def test_db_timestamp_to_utc_for_api_ist_naive_heartbeat():
    """IST-naive heartbeat must serialize as true UTC, not UTC-labeled IST wall clock."""
    reference = datetime(2026, 6, 11, 23, 43, 49, tzinfo=IST)
    ist_naive = datetime(2026, 6, 11, 23, 43, 49)
    utc_api = db_timestamp_to_utc_for_api(ist_naive, reference=reference)
    assert utc_api is not None
    assert utc_api.tzinfo == UTC
    assert utc_api.hour == 18
    assert utc_api.minute == 13
    assert utc_api.day == 11


def test_db_timestamp_to_utc_for_api_matches_ist_aware():
    reference = ist_now()
    naive = ist_now_naive()
    from_api = db_timestamp_to_utc_for_api(naive, reference=reference)
    aware_ist = naive.replace(tzinfo=IST)
    assert from_api == ist_to_utc(aware_ist)

