"""Unit tests for OHLCV price cache repository and trading-day gaps."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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


def test_upsert_many_and_get_range(db_session):
    repo = PriceCacheRepository(db_session)
    rows = [
        {
            "symbol": "TEST.NS",
            "date": date(2024, 1, 2),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000,
        },
        {
            "symbol": "TEST.NS",
            "date": date(2024, 1, 3),
            "open": 101.0,
            "high": 102.0,
            "low": 100.0,
            "close": 101.5,
            "volume": 1100,
        },
    ]
    n = repo.upsert_many(rows)
    assert n >= 1

    bars = repo.get_range("TEST.NS", date(2024, 1, 1), date(2024, 1, 10))
    assert len(bars) == 2
    assert bars[0].close == 100.5

    repo.upsert_many(
        [
            {
                "symbol": "TEST.NS",
                "date": date(2024, 1, 2),
                "close": 200.0,
            }
        ]
    )
    updated = repo.get("TEST.NS", date(2024, 1, 2))
    assert updated.close == 200.0


def test_missing_trading_dates_skips_weekend(db_session):
    repo = PriceCacheRepository(db_session)
    repo.create_or_update("X.NS", date(2024, 6, 3), close=10.0)  # Monday
    missing = repo.get_missing_trading_dates("X.NS", date(2024, 6, 3), date(2024, 6, 7))
    trading = list(iter_trading_days(date(2024, 6, 3), date(2024, 6, 7)))
    assert date(2024, 6, 3) not in missing
    assert all(d in trading for d in missing)


def test_invalidate_symbol(db_session):
    repo = PriceCacheRepository(db_session)
    repo.create_or_update("Z.NS", date(2024, 1, 2), close=1.0)
    deleted = repo.invalidate_symbol("Z.NS")
    assert deleted >= 1
    assert repo.get("Z.NS", date(2024, 1, 2)) is None
