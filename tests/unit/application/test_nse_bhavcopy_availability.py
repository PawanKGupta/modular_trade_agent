"""Tests for NSE bhavcopy publish-window and same-day indicator policy."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.application.services.nse_bhavcopy_availability import (
    filter_nse_intraday_gap_dates,
    nse_bhavcopy_ingest_allowed_for_date,
    nse_bhavcopy_ingest_allowed_for_today,
    nse_today_bhavcopy_published,
    reset_nse_bhavcopy_publish_probe_cache,
    should_use_same_day_close_for_indicators,
)

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture(autouse=True)
def _clear_probe_cache():
    reset_nse_bhavcopy_publish_probe_cache()
    yield
    reset_nse_bhavcopy_publish_probe_cache()


def _patch_ist(monkeypatch, when: datetime) -> None:
    """Patch IST clock where production code reads it (module-level import in availability)."""
    for target in (
        "src.infrastructure.db.timezone_utils.ist_now",
        "src.application.services.nse_bhavcopy_availability.ist_now",
    ):
        monkeypatch.setattr(target, lambda when=when: when)


def test_ingest_allowed_for_historical_date_always(monkeypatch):
    _patch_ist(monkeypatch, datetime(2026, 6, 12, 10, 0, tzinfo=IST))
    assert nse_bhavcopy_ingest_allowed_for_date(date(2026, 6, 11)) is True


def test_ingest_not_allowed_during_market_hours(monkeypatch):
    _patch_ist(monkeypatch, datetime(2026, 6, 12, 11, 0, tzinfo=IST))
    monkeypatch.setattr("core.volume_analysis.is_market_hours", lambda: True)
    monkeypatch.setattr(
        "src.infrastructure.utils.holiday_calendar.is_trading_day",
        lambda _d: True,
    )
    assert nse_bhavcopy_ingest_allowed_for_today() is False


def test_ingest_not_allowed_post_close_before_earliest(monkeypatch):
    _patch_ist(monkeypatch, datetime(2026, 6, 12, 16, 30, tzinfo=IST))
    monkeypatch.setattr("core.volume_analysis.is_market_hours", lambda: False)
    monkeypatch.setattr(
        "src.infrastructure.utils.holiday_calendar.is_trading_day",
        lambda _d: True,
    )
    assert nse_bhavcopy_ingest_allowed_for_today() is False


def test_ingest_allowed_after_earliest(monkeypatch):
    _patch_ist(monkeypatch, datetime(2026, 6, 12, 18, 0, tzinfo=IST))
    monkeypatch.setattr("core.volume_analysis.is_market_hours", lambda: False)
    monkeypatch.setattr(
        "src.infrastructure.utils.holiday_calendar.is_trading_day",
        lambda _d: True,
    )
    assert nse_bhavcopy_ingest_allowed_for_today() is True


def test_filter_drops_today_when_ingest_not_allowed(monkeypatch):
    today = date(2026, 6, 12)
    yesterday = date(2026, 6, 11)
    _patch_ist(monkeypatch, datetime(2026, 6, 12, 16, 0, tzinfo=IST))
    monkeypatch.setattr(
        "src.application.services.nse_bhavcopy_availability.nse_bhavcopy_ingest_allowed_for_date",
        lambda d: d != today,
    )
    assert filter_nse_intraday_gap_dates([today]) == []
    assert filter_nse_intraday_gap_dates([yesterday, today]) == [yesterday]


def test_publish_probe_skipped_before_ingest_window(monkeypatch):
    today = date(2026, 6, 12)
    _patch_ist(monkeypatch, datetime(2026, 6, 12, 16, 0, tzinfo=IST))
    monkeypatch.setattr(
        "src.application.services.nse_bhavcopy_availability.daily_ohlcv_uses_nse",
        lambda: True,
    )
    monkeypatch.setattr(
        "src.application.services.nse_bhavcopy_availability.nse_bhavcopy_ingest_allowed_for_today",
        lambda: False,
    )
    fetcher = MagicMock()
    fetcher.has_cached_bhavcopy.return_value = False
    monkeypatch.setattr(
        "src.infrastructure.data_providers.nse_bhavcopy_fetcher.NseBhavcopyFetcher",
        lambda: fetcher,
    )
    assert nse_today_bhavcopy_published() is False
    fetcher.is_bhavcopy_available_on_nse.assert_not_called()


def test_publish_probe_uses_disk_cache_before_earliest(monkeypatch):
    today = date(2026, 6, 12)
    _patch_ist(monkeypatch, datetime(2026, 6, 12, 16, 0, tzinfo=IST))
    monkeypatch.setattr(
        "src.application.services.nse_bhavcopy_availability.daily_ohlcv_uses_nse",
        lambda: True,
    )
    fetcher = MagicMock()
    fetcher.has_cached_bhavcopy.return_value = True
    monkeypatch.setattr(
        "src.infrastructure.data_providers.nse_bhavcopy_fetcher.NseBhavcopyFetcher",
        lambda: fetcher,
    )
    assert nse_today_bhavcopy_published() is True
    fetcher.is_bhavcopy_available_on_nse.assert_not_called()


def test_should_use_same_day_false_when_early_schedule_no_bhavcopy(monkeypatch):
    """Operator runs analysis at 16:00 — must not treat today as closed until bhavcopy exists."""
    _patch_ist(monkeypatch, datetime(2026, 6, 12, 16, 0, tzinfo=IST))
    monkeypatch.setattr("core.volume_analysis.is_market_hours", lambda: False)
    monkeypatch.setattr(
        "src.infrastructure.utils.holiday_calendar.is_trading_day",
        lambda _d: True,
    )
    monkeypatch.setattr(
        "src.application.services.nse_bhavcopy_availability.daily_ohlcv_uses_nse",
        lambda: True,
    )
    monkeypatch.setattr(
        "src.application.services.nse_bhavcopy_availability.nse_today_bhavcopy_published",
        lambda **_: False,
    )
    assert should_use_same_day_close_for_indicators() is False


def test_should_use_same_day_true_when_bhavcopy_published(monkeypatch):
    _patch_ist(monkeypatch, datetime(2026, 6, 12, 19, 0, tzinfo=IST))
    monkeypatch.setattr("core.volume_analysis.is_market_hours", lambda: False)
    monkeypatch.setattr(
        "src.infrastructure.utils.holiday_calendar.is_trading_day",
        lambda _d: True,
    )
    monkeypatch.setattr(
        "src.application.services.nse_bhavcopy_availability.daily_ohlcv_uses_nse",
        lambda: True,
    )
    monkeypatch.setattr(
        "src.application.services.nse_bhavcopy_availability.nse_today_bhavcopy_published",
        lambda **_: True,
    )
    assert should_use_same_day_close_for_indicators() is True


def test_should_use_same_day_yahoo_legacy_after_1530(monkeypatch):
    _patch_ist(monkeypatch, datetime(2026, 6, 12, 16, 0, tzinfo=IST))
    monkeypatch.setattr("core.volume_analysis.is_market_hours", lambda: False)
    monkeypatch.setattr(
        "src.infrastructure.utils.holiday_calendar.is_trading_day",
        lambda _d: True,
    )
    monkeypatch.setattr(
        "src.application.services.nse_bhavcopy_availability.daily_ohlcv_uses_nse",
        lambda: False,
    )
    assert should_use_same_day_close_for_indicators() is True


def test_ingest_trading_day_skips_today_before_earliest(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from src.application.services.nse_bhavcopy_ingest_service import NseBhavcopyIngestService
    from src.infrastructure.db.base import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db_session = sessionmaker(bind=engine)()

    today = date(2026, 6, 12)
    _patch_ist(monkeypatch, datetime(2026, 6, 12, 16, 30, tzinfo=IST))
    monkeypatch.setattr("core.volume_analysis.is_market_hours", lambda: False)
    monkeypatch.setattr(
        "src.infrastructure.utils.holiday_calendar.is_trading_day",
        lambda _d: True,
    )

    fetcher = MagicMock()
    svc = NseBhavcopyIngestService(db_session, fetcher=fetcher)
    assert svc.ingest_trading_day(today, ["DMART.NS"]) == 0
    fetcher.download_bhavcopy.assert_not_called()
    db_session.close()
