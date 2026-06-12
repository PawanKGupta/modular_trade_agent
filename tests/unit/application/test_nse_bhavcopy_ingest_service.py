"""Tests for NSE bhavcopy ingest into price_cache."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.application.services.nse_bhavcopy_ingest_service import (
    NseBhavcopyIngestService,
    filter_nse_intraday_gap_dates,
)
from src.infrastructure.data_providers.nse_bhavcopy_fetcher import NseEquityBar
from src.infrastructure.db.base import Base
from src.infrastructure.persistence.price_cache_repository import PriceCacheRepository

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "nse_bhavcopy_sample.csv"


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.read_csv(FIXTURE)


def test_fill_symbol_range_upserts_nse_source(db_session, sample_df):
    fetcher = MagicMock()
    fetcher.download_bhavcopy.return_value = sample_df

    svc = NseBhavcopyIngestService(db_session, fetcher=fetcher)
    n = svc.fill_symbol_range("DMART.NS", date(2026, 6, 2), date(2026, 6, 2))
    assert n == 1

    repo = PriceCacheRepository(db_session)
    bar = repo.get("DMART.NS", date(2026, 6, 2))
    assert bar is not None
    assert bar.close == 4057.0
    assert bar.source == "nse"


def test_fill_symbol_range_skips_today_during_market_hours(db_session, sample_df, monkeypatch):
    """Pre-EOD: do not download bhavcopy when only calendar today is missing."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    ist = ZoneInfo("Asia/Kolkata")
    today = date(2026, 6, 12)

    monkeypatch.setattr(
        "src.application.services.nse_bhavcopy_availability.nse_bhavcopy_ingest_allowed_for_today",
        lambda: False,
    )
    monkeypatch.setattr(
        "src.infrastructure.db.timezone_utils.ist_now",
        lambda: datetime(2026, 6, 12, 10, 0, tzinfo=ist),
    )

    fetcher = MagicMock()
    fetcher.download_bhavcopy.return_value = sample_df

    svc = NseBhavcopyIngestService(db_session, fetcher=fetcher)
    assert svc.fill_symbol_range("DMART.NS", today, today) == 0
    fetcher.download_bhavcopy.assert_not_called()


def test_filter_nse_intraday_gap_dates_drops_today_when_session_open(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    ist = ZoneInfo("Asia/Kolkata")
    today = date(2026, 6, 12)
    yesterday = date(2026, 6, 11)

    monkeypatch.setattr(
        "src.application.services.nse_bhavcopy_availability.nse_bhavcopy_ingest_allowed_for_today",
        lambda: False,
    )
    monkeypatch.setattr(
        "src.infrastructure.db.timezone_utils.ist_now",
        lambda: datetime(2026, 6, 12, 10, 0, tzinfo=ist),
    )

    assert filter_nse_intraday_gap_dates([today]) == []
    assert filter_nse_intraday_gap_dates([yesterday, today]) == [yesterday]


def test_ingest_trading_day_multiple_symbols(db_session, sample_df):
    fetcher = MagicMock()
    fetcher.download_bhavcopy.return_value = sample_df

    svc = NseBhavcopyIngestService(db_session, fetcher=fetcher)
    n = svc.ingest_trading_day(date(2026, 6, 2), ["DMART.NS", "TCS.NS"])
    assert n == 2

    repo = PriceCacheRepository(db_session)
    tcs = repo.get("TCS.NS", date(2026, 6, 2))
    assert tcs is not None
    assert tcs.source == "nse"
