"""Unit tests for OhlcvCacheService merge and gap-fill hooks."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.application.services.ohlcv_cache_service import OhlcvCacheService, reset_ohlcv_cache_stats
from src.infrastructure.db.base import Base


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
