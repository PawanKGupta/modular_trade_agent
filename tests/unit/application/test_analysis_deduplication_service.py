"""
Unit tests for AnalysisDeduplicationService

Tests for:
- should_update_signals() time-based logic
- Boolean conversion
- Field mapping and normalization
- Signal creation and update
- Smart expiration logic
- Per-user TRADED status handling
"""

import pytest
from freezegun import freeze_time

from src.application.services.analysis_deduplication_service import (
    AnalysisDeduplicationService,
)
from src.infrastructure.db.models import (
    Orders,
    OrderStatus,
    Positions,
    Signals,
    SignalStatus,
    Users,
    UserSignalStatus,
)
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
            assert "expired" in result  # New field in result

            # Verify signal was created
            signal = db_session.query(Signals).filter_by(symbol="RELIANCE").first()
            assert signal is not None
            assert signal.rsi10 == 25.5
            assert signal.ema9 == 2500.0

    def test_deduplicate_and_update_signals_update_existing(self, db_session):
        """Test deduplication with existing signal - same verdict (both buy) should update"""
        service = AnalysisDeduplicationService(db_session)
        # Monday 8:00 AM - should allow update
        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create existing signal with buy verdict
            window_start, _ = service.get_current_trading_day_window()
            existing = Signals(
                symbol="RELIANCE",
                rsi10=20.0,
                ema9=2500.0,
                verdict="buy",
                final_verdict="buy",
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
                    "final_verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)
            assert result["inserted"] == 0
            assert result["updated"] == 1
            assert result["skipped"] == 0
            assert "expired" in result  # New field in result

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
            assert "expired" in result  # New field in result

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


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = Users(email="test@example.com", password_hash="hash", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestSmartExpirationLogic:
    """Test smart expiration logic for signal deduplication"""

    def test_active_signal_reappears_should_update(self, db_session):
        """Test that ACTIVE signal reappearing in new analysis updates instead of expiring"""
        service = AnalysisDeduplicationService(db_session)
        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create existing ACTIVE signal
            existing = Signals(
                symbol="RELIANCE",
                status=SignalStatus.ACTIVE,
                rsi10=20.0,
                ema9=2500.0,
                verdict="buy",
                final_verdict="buy",
                ts=ist_now(),
            )
            db_session.add(existing)
            db_session.commit()

            # Same signal appears in new analysis
            new_signals = [
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "ema9": 2550.0,
                    "verdict": "buy",
                    "final_verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)

            assert result["updated"] == 1
            assert result["inserted"] == 0
            assert result["expired"] == 0

            # Verify signal was updated, not expired
            db_session.refresh(existing)
            assert existing.status == SignalStatus.ACTIVE
            assert existing.rsi10 == 25.5
            assert existing.ema9 == 2550.0

    def test_active_signal_verdict_changed_should_expire(self, db_session):
        """Test that ACTIVE signal with changed verdict expires old and creates new"""
        service = AnalysisDeduplicationService(db_session)
        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create existing ACTIVE signal with "watch" verdict
            existing = Signals(
                symbol="RELIANCE",
                status=SignalStatus.ACTIVE,
                rsi10=20.0,
                verdict="watch",
                final_verdict="watch",
                ts=ist_now(),
            )
            db_session.add(existing)
            db_session.commit()

            # New analysis shows "buy" verdict
            new_signals = [
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "verdict": "buy",
                    "final_verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)

            assert result["expired"] == 1
            assert result["inserted"] == 1
            assert result["updated"] == 0

            # Verify old signal was expired
            db_session.refresh(existing)
            assert existing.status == SignalStatus.EXPIRED

            # Verify new signal was created
            new_signal = (
                db_session.query(Signals)
                .filter_by(symbol="RELIANCE", status=SignalStatus.ACTIVE)
                .first()
            )
            assert new_signal is not None
            assert new_signal.verdict == "buy"

    def test_rejected_signal_reappears_should_create_new(self, db_session):
        """Test that REJECTED signal reappearing creates new signal"""
        service = AnalysisDeduplicationService(db_session)
        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create existing REJECTED signal
            existing = Signals(
                symbol="RELIANCE",
                status=SignalStatus.REJECTED,
                rsi10=20.0,
                verdict="buy",
                final_verdict="buy",
                ts=ist_now(),
            )
            db_session.add(existing)
            db_session.commit()

            # Same signal appears in new analysis
            new_signals = [
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "verdict": "buy",
                    "final_verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)

            assert result["inserted"] == 1
            assert result["updated"] == 0
            assert result["expired"] == 0

            # Verify new signal was created (old remains REJECTED)
            signals = db_session.query(Signals).filter_by(symbol="RELIANCE").all()
            assert len(signals) == 2
            assert any(s.status == SignalStatus.REJECTED for s in signals)
            assert any(s.status == SignalStatus.ACTIVE for s in signals)

    def test_expired_signal_reappears_should_create_new(self, db_session):
        """Test that EXPIRED signal reappearing creates new signal"""
        service = AnalysisDeduplicationService(db_session)
        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create existing EXPIRED signal
            existing = Signals(
                symbol="RELIANCE",
                status=SignalStatus.EXPIRED,
                rsi10=20.0,
                verdict="buy",
                final_verdict="buy",
                ts=ist_now(),
            )
            db_session.add(existing)
            db_session.commit()

            # Same signal appears in new analysis
            new_signals = [
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "verdict": "buy",
                    "final_verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)

            assert result["inserted"] == 1
            assert result["updated"] == 0
            assert result["expired"] == 0

            # Verify new signal was created
            new_signal = (
                db_session.query(Signals)
                .filter_by(symbol="RELIANCE", status=SignalStatus.ACTIVE)
                .first()
            )
            assert new_signal is not None

    def test_traded_signal_user_has_ongoing_order_should_skip(self, db_session, test_user):
        """Test that TRADED signal with user having ONGOING order skips creating new signal"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)
        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create existing TRADED signal
            existing = Signals(
                symbol="RELIANCE",
                status=SignalStatus.TRADED,
                rsi10=20.0,
                verdict="buy",
                final_verdict="buy",
                ts=ist_now(),
            )
            db_session.add(existing)
            db_session.commit()

            # Create user status TRADED
            user_status = UserSignalStatus(
                user_id=test_user.id,
                signal_id=existing.id,
                symbol="RELIANCE",
                status=SignalStatus.TRADED,
                marked_at=ist_now(),
            )
            db_session.add(user_status)

            # Create ONGOING buy order
            order = Orders(
                user_id=test_user.id,
                symbol="RELIANCE",
                side="buy",
                order_type="MARKET",
                status=OrderStatus.ONGOING,
                quantity=10,
                price=2500.0,
                placed_at=ist_now(),
            )
            db_session.add(order)
            db_session.commit()

            # Same signal appears in new analysis
            new_signals = [
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "verdict": "buy",
                    "final_verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)

            assert result["skipped"] == 1
            assert result["inserted"] == 0

    def test_traded_signal_user_no_order_should_create_new(self, db_session, test_user):
        """Test that TRADED signal with user having no order creates new signal"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)
        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create existing TRADED signal
            existing = Signals(
                symbol="RELIANCE",
                status=SignalStatus.TRADED,
                rsi10=20.0,
                verdict="buy",
                final_verdict="buy",
                ts=ist_now(),
            )
            db_session.add(existing)
            db_session.commit()

            # Same signal appears in new analysis (user has no order)
            new_signals = [
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "verdict": "buy",
                    "final_verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)

            assert result["inserted"] == 1
            assert result["skipped"] == 0

    def test_traded_signal_user_failed_order_should_create_new(self, db_session, test_user):
        """Test that TRADED signal with user having FAILED order creates new signal"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)
        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create existing TRADED signal
            existing = Signals(
                symbol="RELIANCE",
                status=SignalStatus.TRADED,
                rsi10=20.0,
                verdict="buy",
                final_verdict="buy",
                ts=ist_now(),
            )
            db_session.add(existing)
            db_session.commit()

            # Create user status TRADED
            user_status = UserSignalStatus(
                user_id=test_user.id,
                signal_id=existing.id,
                symbol="RELIANCE",
                status=SignalStatus.TRADED,
                marked_at=ist_now(),
            )
            db_session.add(user_status)

            # Create FAILED buy order
            order = Orders(
                user_id=test_user.id,
                symbol="RELIANCE",
                side="buy",
                order_type="MARKET",
                status=OrderStatus.FAILED,
                quantity=10,
                price=2500.0,
                placed_at=ist_now(),
            )
            db_session.add(order)
            db_session.commit()

            # Same signal appears in new analysis
            new_signals = [
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "verdict": "buy",
                    "final_verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)

            assert result["inserted"] == 1
            assert result["skipped"] == 0

    def test_traded_signal_user_closed_position_should_create_new(self, db_session, test_user):
        """Test that TRADED signal with user having closed position creates new signal"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)
        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create existing TRADED signal
            existing = Signals(
                symbol="RELIANCE",
                status=SignalStatus.TRADED,
                rsi10=20.0,
                verdict="buy",
                final_verdict="buy",
                ts=ist_now(),
            )
            db_session.add(existing)
            db_session.commit()

            # Create user status TRADED
            user_status = UserSignalStatus(
                user_id=test_user.id,
                signal_id=existing.id,
                symbol="RELIANCE",
                status=SignalStatus.TRADED,
                marked_at=ist_now(),
            )
            db_session.add(user_status)

            # Create ONGOING buy order
            order = Orders(
                user_id=test_user.id,
                symbol="RELIANCE",
                side="buy",
                order_type="MARKET",
                status=OrderStatus.ONGOING,
                quantity=10,
                price=2500.0,
                placed_at=ist_now(),
            )
            db_session.add(order)

            # Create closed position
            position = Positions(
                user_id=test_user.id,
                symbol="RELIANCE",
                quantity=0.0,
                avg_price=2500.0,
                opened_at=ist_now(),
                closed_at=ist_now(),  # Position is closed
            )
            db_session.add(position)
            db_session.commit()

            # Same signal appears in new analysis
            new_signals = [
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "verdict": "buy",
                    "final_verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)

            assert result["inserted"] == 1
            assert result["skipped"] == 0

    def test_active_signal_user_traded_ongoing_should_update_base(self, db_session, test_user):
        """Test that ACTIVE signal with user TRADED and ONGOING order updates base signal"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)
        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create existing ACTIVE signal
            existing = Signals(
                symbol="RELIANCE",
                status=SignalStatus.ACTIVE,
                rsi10=20.0,
                ema9=2500.0,
                verdict="buy",
                final_verdict="buy",
                ts=ist_now(),
            )
            db_session.add(existing)
            db_session.commit()

            # Create user status TRADED
            user_status = UserSignalStatus(
                user_id=test_user.id,
                signal_id=existing.id,
                symbol="RELIANCE",
                status=SignalStatus.TRADED,
                marked_at=ist_now(),
            )
            db_session.add(user_status)

            # Create ONGOING buy order
            order = Orders(
                user_id=test_user.id,
                symbol="RELIANCE",
                side="buy",
                order_type="MARKET",
                status=OrderStatus.ONGOING,
                quantity=10,
                price=2500.0,
                placed_at=ist_now(),
            )
            db_session.add(order)
            db_session.commit()

            # Same signal appears in new analysis
            new_signals = [
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "ema9": 2550.0,
                    "verdict": "buy",
                    "final_verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)

            # Should update base signal (for other users) but skip for this user
            assert result["updated"] == 1
            assert result["skipped"] == 0  # Not skipped, just updated

            # Verify base signal was updated
            db_session.refresh(existing)
            assert existing.rsi10 == 25.5
            assert existing.ema9 == 2550.0

    def test_signals_not_in_new_analysis_should_expire(self, db_session):
        """Test that signals not appearing in new analysis are expired"""
        service = AnalysisDeduplicationService(db_session)
        with freeze_time("2025-01-13 08:00:00+05:30"):
            from datetime import timedelta

            # Create existing ACTIVE signals with older timestamps (so they can be expired)
            # Use naive datetime to match SQLite storage format
            now = ist_now()
            old_time = now - timedelta(hours=1)  # 1 hour ago
            # Convert to naive for database storage (SQLite stores as naive)
            old_time_naive = old_time.replace(tzinfo=None) if old_time.tzinfo else old_time

            signal1 = Signals(
                symbol="RELIANCE",
                status=SignalStatus.ACTIVE,
                rsi10=20.0,
                verdict="buy",
                final_verdict="buy",
                ts=old_time_naive,
            )
            signal2 = Signals(
                symbol="TCS",
                status=SignalStatus.ACTIVE,
                rsi10=25.0,
                verdict="buy",
                final_verdict="buy",
                ts=old_time_naive,
            )
            db_session.add_all([signal1, signal2])
            db_session.commit()

            # Verify signals are ACTIVE before processing
            db_session.refresh(signal2)
            assert signal2.status == SignalStatus.ACTIVE, "TCS should be ACTIVE before processing"

            # Verify TCS timestamp is old
            assert signal2.ts < ist_now().replace(
                tzinfo=None
            ), f"TCS timestamp {signal2.ts} should be less than current time"

            # New analysis only has RELIANCE (TCS is missing)
            new_signals = [
                {
                    "symbol": "RELIANCE",
                    "rsi10": 25.5,
                    "verdict": "buy",
                    "final_verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)

            assert result["updated"] == 1  # RELIANCE updated
            assert (
                result["expired"] >= 1
            ), f"Expected at least 1 expired signal, got {result['expired']}. Updated: {result['updated']}, Inserted: {result['inserted']}, Skipped: {result['skipped']}"  # TCS expired (and possibly others)

            # Verify TCS was expired
            db_session.refresh(signal2)
            assert (
                signal2.status == SignalStatus.EXPIRED
            ), f"TCS status is {signal2.status}, expected EXPIRED. TCS timestamp: {signal2.ts}"

            # Verify RELIANCE was updated, not expired
            db_session.refresh(signal1)
            assert signal1.status == SignalStatus.ACTIVE
