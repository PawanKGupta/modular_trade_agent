"""Tests for NSE bhavcopy ingest skip-cached-days behavior."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.application.services.nse_bhavcopy_ingest_service import NseBhavcopyIngestService
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


def test_fill_symbol_range_skips_download_when_date_cached(db_session, sample_df):
    fetcher = MagicMock()
    fetcher.download_bhavcopy.return_value = sample_df

    svc = NseBhavcopyIngestService(db_session, fetcher=fetcher)
    assert svc.fill_symbol_range("DMART.NS", date(2026, 6, 2), date(2026, 6, 2)) == 1
    fetcher.download_bhavcopy.assert_called_once()

    fetcher.download_bhavcopy.reset_mock()
    assert svc.fill_symbol_range("DMART.NS", date(2026, 6, 2), date(2026, 6, 2)) == 0
    fetcher.download_bhavcopy.assert_not_called()
