"""
Unit tests for AnalysisDeduplicationService

Tests for:
- should_update_signals() time-based logic
- Boolean conversion
- Field mapping and normalization
- Signal creation and update
"""

from freezegun import freeze_time

from src.application.services.analysis_deduplication_service import (
    AnalysisDeduplicationService,
)
from src.infrastructure.db.models import Signals
from src.infrastructure.db.timezone_utils import ist_now


class TestAnalysisDeduplicationService:
    """Test suite for AnalysisDeduplicationService"""

    def test_should_update_signals_weekday_before_9am(self, db_session):
        """Test that updates are allowed before 9AM on weekdays"""
        service = AnalysisDeduplicationService(db_session)
        # Monday 8:00 AM
        with freeze_time("2025-01-13 08:00:00+05:30"):
            assert service.should_update_signals() is True

    def test_should_update_signals_weekday_after_4pm(self, db_session):
        """Test that updates are allowed after 4PM on weekdays"""
        service = AnalysisDeduplicationService(db_session)
        # Monday 4:30 PM
        with freeze_time("2025-01-13 16:30:00+05:30"):
            assert service.should_update_signals() is True

    def test_should_update_signals_weekday_during_trading_hours(self, db_session):
        """Test that updates are blocked between 9AM-4PM on weekdays"""
        service = AnalysisDeduplicationService(db_session)
        # Monday 10:00 AM
        with freeze_time("2025-01-13 10:00:00+05:30"):
            assert service.should_update_signals() is False
        # Monday 3:00 PM
        with freeze_time("2025-01-13 15:00:00+05:30"):
            assert service.should_update_signals() is False

    def test_should_update_signals_weekend_before_9am(self, db_session):
        """Test that updates are allowed before 9AM on weekends"""
        service = AnalysisDeduplicationService(db_session)
        # Saturday 8:00 AM
        with freeze_time("2025-01-11 08:00:00+05:30"):
            assert service.should_update_signals() is True

    def test_should_update_signals_weekend_after_9am(self, db_session):
        """Test that updates are blocked after 9AM on weekends"""
        service = AnalysisDeduplicationService(db_session)
        # Saturday 10:00 AM
        with freeze_time("2025-01-11 10:00:00+05:30"):
            assert service.should_update_signals() is False

    def test_convert_boolean_none(self, db_session):
        """Test boolean conversion with None"""
        service = AnalysisDeduplicationService(db_session)
        assert service._convert_boolean(None) is None

    def test_convert_boolean_true_bool(self, db_session):
        """Test boolean conversion with True boolean"""
        service = AnalysisDeduplicationService(db_session)
        assert service._convert_boolean(True) is True
        assert service._convert_boolean(False) is False

    def test_convert_boolean_string_true(self, db_session):
        """Test boolean conversion with string 'True'"""
        service = AnalysisDeduplicationService(db_session)
        assert service._convert_boolean("True") is True
        assert service._convert_boolean("true") is True
        assert service._convert_boolean("TRUE") is True

    def test_convert_boolean_string_false(self, db_session):
        """Test boolean conversion with string 'False'"""
        service = AnalysisDeduplicationService(db_session)
        assert service._convert_boolean("False") is False
        assert service._convert_boolean("false") is False
        assert service._convert_boolean("FALSE") is False

    def test_convert_boolean_string_other(self, db_session):
        """Test boolean conversion with other string values"""
        service = AnalysisDeduplicationService(db_session)
        assert service._convert_boolean("1") is True
        assert service._convert_boolean("yes") is True
        assert service._convert_boolean("on") is True
        assert service._convert_boolean("0") is False
        assert service._convert_boolean("no") is False
        assert service._convert_boolean("off") is False

    def test_convert_fundamental_assessment_dict(self, db_session):
        """Test fundamental assessment conversion from dict"""
        service = AnalysisDeduplicationService(db_session)
        value = {"fundamental_reason": "Good PE ratio"}
        result = service._convert_fundamental_assessment(value)
        assert result == "Good PE ratio"

    def test_convert_fundamental_assessment_dict_no_reason(self, db_session):
        """Test fundamental assessment conversion from dict without reason"""
        service = AnalysisDeduplicationService(db_session)
        value = {"pe": 15.0, "pb": 2.0}
        result = service._convert_fundamental_assessment(value)
        assert result.startswith("{")
        assert len(result) <= 64

    def test_convert_fundamental_assessment_string(self, db_session):
        """Test fundamental assessment conversion from string"""
        service = AnalysisDeduplicationService(db_session)
        value = "Good fundamentals"
        result = service._convert_fundamental_assessment(value)
        assert result == "Good fundamentals"

    def test_convert_fundamental_assessment_truncate(self, db_session):
        """Test fundamental assessment truncation to 64 chars"""
        service = AnalysisDeduplicationService(db_session)
        value = "A" * 100
        result = service._convert_fundamental_assessment(value)
        assert len(result) == 64
        assert result.endswith("...")

    def test_create_signal_from_data_basic(self, db_session):
        """Test creating signal from basic data"""
        service = AnalysisDeduplicationService(db_session)
        data = {
            "symbol": "RELIANCE",
            "rsi10": 25.5,
            "ema9": 2500.0,
            "ema200": 2400.0,
            "distance_to_ema9": 5.0,
            "clean_chart": True,
            "monthly_support_dist": 2.5,
            "confidence": 0.85,
            "verdict": "buy",
        }
        signal = service._create_signal_from_data(data)
        assert signal is not None
        assert signal.symbol == "RELIANCE"
        assert signal.rsi10 == 25.5
        assert signal.ema9 == 2500.0
        assert signal.ema200 == 2400.0
        assert signal.distance_to_ema9 == 5.0
        assert signal.clean_chart is True
        assert signal.monthly_support_dist == 2.5
        assert signal.confidence == 0.85
        assert signal.verdict == "buy"

    def test_create_signal_from_data_boolean_strings(self, db_session):
        """Test creating signal with string boolean values"""
        service = AnalysisDeduplicationService(db_session)
        data = {
            "symbol": "RELIANCE",
            "clean_chart": "True",
            "fundamental_ok": "False",
            "vol_ok": "true",
            "vol_strong": "False",
            "is_above_ema200": "True",
        }
        signal = service._create_signal_from_data(data)
        assert signal.clean_chart is True
        assert signal.fundamental_ok is False
        assert signal.vol_ok is True
        assert signal.vol_strong is False
        assert signal.is_above_ema200 is True

    def test_create_signal_from_data_ticker_with_ns(self, db_session):
        """Test creating signal from ticker with .NS suffix"""
        service = AnalysisDeduplicationService(db_session)
        data = {"ticker": "RELIANCE.NS", "rsi10": 25.5}
        signal = service._create_signal_from_data(data)
        assert signal is not None
        assert signal.symbol == "RELIANCE"

    def test_create_signal_from_data_no_symbol(self, db_session):
        """Test creating signal without symbol returns None"""
        service = AnalysisDeduplicationService(db_session)
        data = {"rsi10": 25.5}
        signal = service._create_signal_from_data(data)
        assert signal is None

    def test_update_signal_from_data(self, db_session):
        """Test updating existing signal from data"""
        service = AnalysisDeduplicationService(db_session)
        # Create existing signal
        existing = Signals(
            symbol="RELIANCE",
            rsi10=20.0,
            ema9=2500.0,
            verdict="watch",
            ts=ist_now(),
        )
        db_session.add(existing)
        db_session.commit()

        # Update with new data
        data = {
            "rsi10": 25.5,
            "ema9": 2550.0,
            "ema200": 2400.0,
            "distance_to_ema9": 5.0,
            "verdict": "buy",
            "clean_chart": "True",
        }
        service._update_signal_from_data(existing, data)

        assert existing.rsi10 == 25.5
        assert existing.ema9 == 2550.0
        assert existing.ema200 == 2400.0
        assert existing.distance_to_ema9 == 5.0
        assert existing.verdict == "buy"
        assert existing.clean_chart is True

    def test_deduplicate_and_update_signals_new_signal(self, db_session):
        """Test deduplication with new signal"""
        service = AnalysisDeduplicationService(db_session)
        # Monday 8:00 AM - should allow update
        with freeze_time("2025-01-13 08:00:00+05:30"):
            new_signals = [
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "ema9": 2500.0,
                    "verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals)
            assert result["inserted"] == 1
            assert result["updated"] == 0
            assert result["skipped"] == 0

            # Verify signal was created
            signal = db_session.query(Signals).filter_by(symbol="RELIANCE").first()
            assert signal is not None
            assert signal.rsi10 == 25.5
            assert signal.ema9 == 2500.0

    def test_deduplicate_and_update_signals_update_existing(self, db_session):
        """Test deduplication with existing signal"""
        service = AnalysisDeduplicationService(db_session)
        # Monday 8:00 AM - should allow update
        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create existing signal in the same trading day window
            window_start, _ = service.get_current_trading_day_window()
            existing = Signals(
                symbol="RELIANCE",
                rsi10=20.0,
                ema9=2500.0,
                verdict="watch",
                ts=window_start,
            )
            db_session.add(existing)
            db_session.commit()

            new_signals = [
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "ema9": 2550.0,
                    "verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals)
            assert result["inserted"] == 0
            assert result["updated"] == 1
            assert result["skipped"] == 0

            # Verify signal was updated
            db_session.refresh(existing)
            assert existing.rsi10 == 25.5
            assert existing.ema9 == 2550.0
            assert existing.verdict == "buy"

    def test_deduplicate_and_update_signals_skip_time_check(self, db_session):
        """Test deduplication with skip_time_check=True"""
        service = AnalysisDeduplicationService(db_session)
        # Monday 10:00 AM - normally blocked, but skip_time_check=True
        with freeze_time("2025-01-13 10:00:00+05:30"):
            new_signals = [
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)
            assert result["inserted"] == 1

    def test_deduplicate_and_update_signals_blocked_by_time(self, db_session):
        """Test deduplication blocked during trading hours"""
        service = AnalysisDeduplicationService(db_session)
        # Monday 10:00 AM - should be blocked
        with freeze_time("2025-01-13 10:00:00+05:30"):
            new_signals = [
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals)
            assert result["inserted"] == 0
            assert result["updated"] == 0
            assert result["skipped"] == 1

    def test_deduplicate_and_update_signals_no_symbol(self, db_session):
        """Test deduplication skips signals without symbol"""
        service = AnalysisDeduplicationService(db_session)
        # Monday 8:00 AM - should allow update
        with freeze_time("2025-01-13 08:00:00+05:30"):
            new_signals = [
                {"rsi10": 25.5, "verdict": "buy"},  # No symbol
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "verdict": "buy",
                },
            ]
            result = service.deduplicate_and_update_signals(new_signals)
            assert result["inserted"] == 1
            assert result["skipped"] == 1
