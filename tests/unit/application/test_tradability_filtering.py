"""Tradability filtering tests (EQ-first resolver at persist)."""

from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from src.application.services.individual_service_manager import IndividualServiceManager

_SCRIP_CACHE_PATCH = (
    "src.infrastructure.brokers.tradable_equity_resolver.load_cached_scrip_master"
)


def _inst_row(symbol: str, isin: str = "INE000A01000") -> dict:
    return {"pTrdSymbol": symbol, "pISIN": isin}


def _patch_scrip_cache(instruments: list[dict]):
    from src.infrastructure.brokers.tradable_equity_resolver import (
        build_scrip_master_from_instruments,
    )

    sm = build_scrip_master_from_instruments(instruments)
    return patch(_SCRIP_CACHE_PATCH, return_value=sm)


class TestTradabilityFiltering:
    def test_is_t2t_segment_be_only(self, db_session):
        manager = IndividualServiceManager(db_session)
        instruments = [
            _inst_row("SALSTEEL-BE"),
            _inst_row("RELIANCE-EQ", "INE002A01018"),
        ]
        with _patch_scrip_cache(instruments):
            assert manager._is_t2t_segment("SALSTEEL.NS") is True
            assert manager._is_t2t_segment("RELIANCE.NS") is False

    def test_gallantt_not_t2t_when_eq_and_bl_listed(self, db_session):
        manager = IndividualServiceManager(db_session)
        instruments = [
            _inst_row("GALLANTT-BL", "INE297H01019"),
            _inst_row("GALLANTT-EQ", "INE297H01019"),
        ]
        with _patch_scrip_cache(instruments):
            assert manager._is_t2t_segment("GALLANTT.NS") is False
            assert manager._is_non_tradable_equity("GALLANTT.NS") is False

    def test_non_tradable_etf_at_persist(self, db_session):
        manager = IndividualServiceManager(db_session)
        logger = MagicMock()
        instruments = [
            _inst_row("SILVERAG-EQ", "INF769K01KG6"),
            _inst_row("RELIANCE-EQ", "INE002A01018"),
        ]
        results = [
            {"ticker": "SILVERAG.NS", "verdict": "buy", "status": "success"},
            {"ticker": "RELIANCE.NS", "verdict": "buy", "status": "success"},
        ]
        ist_8am = datetime(2025, 1, 13, 8, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        with (
            _patch_scrip_cache(instruments),
            patch(
                "src.infrastructure.db.timezone_utils.ist_now",
                return_value=ist_8am,
            ),
            patch(
                "src.application.services.individual_service_manager.AnalysisDeduplicationService.should_update_signals",
                return_value=True,
            ),
        ):
            summary = manager._persist_analysis_results(results, logger)
        assert summary["processed"] == 1
        assert summary["t2t_filtered"] == 1

    def test_cache_missing_allows_through(self, db_session):
        manager = IndividualServiceManager(db_session)
        with patch(_SCRIP_CACHE_PATCH, return_value=None):
            assert manager._is_t2t_segment("SALSTEEL.NS") is False
