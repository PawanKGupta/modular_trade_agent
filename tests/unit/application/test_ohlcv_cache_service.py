"""Unit tests for OhlcvCacheService merge and gap-fill hooks."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.application.services.ohlcv_cache_service import OhlcvCacheService, reset_ohlcv_cache_stats
from src.infrastructure.db.base import Base
from src.infrastructure.persistence.price_cache_repository import PriceCacheRepository
from src.infrastructure.utils.holiday_calendar import iter_trading_days


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


def _fake_yahoo(symbol, days=365, interval="1d", end_date=None, add_current_day=True):
    idx = pd.date_range("2024-01-01", periods=5, freq="B")
    return pd.DataFrame(
        {
            "date": idx,
            "open": [10.0] * 5,
            "high": [11.0] * 5,
            "low": [9.0] * 5,
            "close": [10.5, 10.6, 10.7, 10.8, 10.9],
            "volume": [100] * 5,
        }
    )


def test_merge_yahoo_wins_on_overlap(db_session):
    svc = OhlcvCacheService(db_session, fetch_func=_fake_yahoo)
    svc.gap_fill("A.NS", date(2024, 1, 1), date(2024, 1, 31), yf_end_date="2024-01-31")

    cached = svc.repo.get_range("A.NS", date(2024, 1, 1), date(2024, 1, 31))
    cached_df = pd.DataFrame(
        {"date": [cached[0].date], "close": [999.0]},
    )
    cached_df["date"] = pd.to_datetime(cached_df["date"])
    fetched = _fake_yahoo("A.NS")
    merged = svc.merge_cached_and_fetched(
        "A.NS",
        date(2024, 1, 1),
        date(2024, 1, 31),
        fetched,
    )
    assert merged["close"].iloc[0] != 999.0


def test_get_ohlcv_uses_fetch_on_empty(db_session):
    reset_ohlcv_cache_stats()

    def counter_fetch(*args, **kwargs):
        return _fake_yahoo(*args, **kwargs)

    svc = OhlcvCacheService(db_session, fetch_func=counter_fetch)
    df = svc.get_ohlcv("B.NS", days=30, end_date="2024-01-31", add_current_day=False)
    assert df is not None
    assert not df.empty
    df2 = svc.get_ohlcv("B.NS", days=30, end_date="2024-01-31", add_current_day=False)
    assert len(df2) == len(df)


def test_get_ohlcv_cache_hit_skips_yahoo_when_warm(db_session):
    reset_ohlcv_cache_stats()
    calls = {"n": 0}

    def counting_fetch(*args, **kwargs):
        calls["n"] += 1
        return _fake_yahoo(*args, **kwargs)

    end = date(2024, 1, 31)
    start = end - timedelta(days=65)
    repo = PriceCacheRepository(db_session)
    for td in iter_trading_days(start, end):
        repo.create_or_update("C.NS", td, close=10.0)

    svc = OhlcvCacheService(db_session, fetch_func=counting_fetch)
    df = svc.get_ohlcv("C.NS", days=60, end_date="2024-01-31", add_current_day=False)
    assert df is not None
    assert calls["n"] == 0

    svc.get_ohlcv("C.NS", days=60, end_date="2024-01-31", add_current_day=False)
    assert calls["n"] == 0


def test_invalidate_symbol_resets_meta_via_repo(db_session):
    repo = PriceCacheRepository(db_session)
    repo.create_or_update("D.NS", date(2024, 1, 2), close=1.0)
    repo.record_fetch_validation(
        "D.NS",
        "1d",
        fetch_status="ok",
        coverage_pct=100.0,
        message="ok",
    )
    svc = OhlcvCacheService(db_session, fetch_func=_fake_yahoo)
    svc.invalidate_symbol("D.NS")
    meta = repo.get_symbol_meta("D.NS")
    assert meta.fetch_status == "unknown"
    assert meta.row_count == 0


def test_cache_hit_revalidates_stale_partial_meta(db_session, monkeypatch):
    reset_ohlcv_cache_stats()
    end = date(2024, 1, 31)
    start = end - timedelta(days=65)
    repo = PriceCacheRepository(db_session)
    for td in iter_trading_days(start, end):
        repo.create_or_update("E.NS", td, close=10.0, open=10.0, high=11.0, low=9.0, volume=100)
    repo.record_fetch_validation(
        "E.NS",
        "1d",
        fetch_status="partial",
        coverage_pct=70.0,
        message="stale partial",
    )

    svc = OhlcvCacheService(db_session, fetch_func=_fake_yahoo)
    df = svc.get_ohlcv("E.NS", days=60, end_date="2024-01-31", add_current_day=False)
    assert df is not None
    meta = repo.get_symbol_meta("E.NS")
    assert meta.fetch_status == "ok"


def test_get_ohlcv_blocks_short_daily_history_on_long_lookback(db_session, monkeypatch):
    monkeypatch.setattr(
        "src.application.services.ohlcv_cache_service.OHLCV_ENFORCE_INDICATOR_MIN_BARS",
        True,
    )
    end = date(2024, 1, 31)
    start = date(2024, 1, 2)
    repo = PriceCacheRepository(db_session)
    for td in iter_trading_days(start, end):
        repo.create_or_update("SHORT.NS", td, close=10.0, open=10.0, high=11.0, low=9.0, volume=100)

    svc = OhlcvCacheService(db_session, fetch_func=_fake_yahoo)
    df_short = svc.get_ohlcv("SHORT.NS", days=30, end_date="2024-01-31", add_current_day=False)
    assert df_short is not None
    df_long = svc.get_ohlcv("SHORT.NS", days=400, end_date="2024-01-31", add_current_day=False)
    assert df_long is None
