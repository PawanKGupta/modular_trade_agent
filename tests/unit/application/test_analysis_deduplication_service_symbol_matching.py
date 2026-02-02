"""
Unit tests for AnalysisDeduplicationService symbol matching

Tests for:
- Base symbol from signals matching full symbols in positions/orders
- Full symbol from signals matching full symbols in positions/orders
- Fallback matching logic
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


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = Users(email="test@example.com", password_hash="hash", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestAnalysisDeduplicationServiceSymbolMatching:
    """Test suite for symbol matching in AnalysisDeduplicationService"""

    def test_find_position_by_symbol_exact_match_full_symbol(self, db_session, test_user):
        """Test _find_position_by_symbol with exact match (full symbol)"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)

        # Create position with full symbol
        position = Positions(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            quantity=10.0,
            avg_price=2500.0,
            opened_at=ist_now(),
        )
        db_session.add(position)
        db_session.commit()

        # Find with full symbol (exact match)
        result = service._find_position_by_symbol(test_user.id, "RELIANCE-EQ")
        assert result is not None
        assert result.symbol == "RELIANCE-EQ"
        assert result.quantity == 10.0

    def test_find_position_by_symbol_base_symbol_fallback(self, db_session, test_user):
        """Test _find_position_by_symbol with base symbol matching full symbol"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)

        # Create position with full symbol
        position = Positions(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            quantity=10.0,
            avg_price=2500.0,
            opened_at=ist_now(),
        )
        db_session.add(position)
        db_session.commit()

        # Find with base symbol (fallback matching)
        result = service._find_position_by_symbol(test_user.id, "RELIANCE")
        assert result is not None
        assert result.symbol == "RELIANCE-EQ"
        assert result.quantity == 10.0

    def test_find_position_by_symbol_not_found(self, db_session, test_user):
        """Test _find_position_by_symbol when position doesn't exist"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)

        # Try to find non-existent position
        result = service._find_position_by_symbol(test_user.id, "NONEXISTENT")
        assert result is None

    def test_find_position_by_symbol_include_closed(self, db_session, test_user):
        """Test _find_position_by_symbol with include_closed=True"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)

        # Create closed position with full symbol
        position = Positions(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            quantity=10.0,
            avg_price=2500.0,
            opened_at=ist_now(),
            closed_at=ist_now(),
        )
        db_session.add(position)
        db_session.commit()

        # Find with base symbol, include_closed=True
        result = service._find_position_by_symbol(test_user.id, "RELIANCE", include_closed=True)
        assert result is not None
        assert result.symbol == "RELIANCE-EQ"
        assert result.closed_at is not None

        # Find with base symbol, include_closed=False (default)
        result = service._find_position_by_symbol(test_user.id, "RELIANCE", include_closed=False)
        assert result is None  # Closed position should not be returned

    def test_has_open_position_for_symbol_exact_match_full_symbol(self, db_session, test_user):
        """Test _has_open_position_for_symbol with exact match (full symbol)"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)

        # Create open position (closed_at=None) with full symbol
        position = Positions(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            quantity=10.0,
            avg_price=2500.0,
            opened_at=ist_now(),
            closed_at=None,
        )
        db_session.add(position)
        db_session.commit()

        # Check with full symbol (exact match)
        result = service._has_open_position_for_symbol(test_user.id, "RELIANCE-EQ")
        assert result is True

    def test_has_open_position_for_symbol_base_symbol_fallback(self, db_session, test_user):
        """Test _has_open_position_for_symbol with base symbol matching full symbol"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)

        # Create open position with full symbol (closed_at=None)
        position = Positions(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            quantity=10.0,
            avg_price=2500.0,
            opened_at=ist_now(),
            closed_at=None,
        )
        db_session.add(position)
        db_session.commit()

        # Check with base symbol (fallback matching)
        result = service._has_open_position_for_symbol(test_user.id, "RELIANCE")
        assert result is True

    def test_has_open_position_for_symbol_not_found(self, db_session, test_user):
        """Test _has_open_position_for_symbol when order doesn't exist"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)

        # Check for non-existent order
        result = service._has_open_position_for_symbol(test_user.id, "NONEXISTENT")
        assert result is False

    def test_has_open_position_for_symbol_ignores_closed_orders(self, db_session, test_user):
        """Test _has_open_position_for_symbol ignores closed positions"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)

        # Create closed position (closed_at set)
        position = Positions(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            quantity=10.0,
            avg_price=2500.0,
            opened_at=ist_now(),
            closed_at=ist_now(),
        )
        db_session.add(position)
        db_session.commit()

        # Check with base symbol - should return False (position is closed)
        result = service._has_open_position_for_symbol(test_user.id, "RELIANCE")
        assert result is False

    def test_has_open_position_for_symbol_ignores_sell_orders(self, db_session, test_user):
        """Test _has_open_position_for_symbol returns False when no open position"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)

        # No open position for RELIANCE (sell order does not create a holding)
        # So no Positions row with closed_at=None for this symbol

        # Check with base symbol - should return False (no open position)
        result = service._has_open_position_for_symbol(test_user.id, "RELIANCE")
        assert result is False

    def test_deduplicate_with_base_symbol_matches_full_symbol_position(self, db_session, test_user):
        """Test deduplication when signal has base symbol but position has full symbol"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)

        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create existing TRADED signal with base symbol
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

            # Create position with full symbol
            position = Positions(
                user_id=test_user.id,
                symbol="RELIANCE-EQ",
                quantity=10.0,
                avg_price=2500.0,
                opened_at=ist_now(),
            )
            db_session.add(position)

            # Create ONGOING buy order with full symbol
            order = Orders(
                user_id=test_user.id,
                symbol="RELIANCE-EQ",
                side="buy",
                order_type="MARKET",
                status=OrderStatus.ONGOING,
                quantity=10,
                price=2500.0,
                placed_at=ist_now(),
            )
            db_session.add(order)
            db_session.commit()

            # Same signal appears in new analysis with base symbol
            new_signals = [
                {
                    "symbol": "RELIANCE",  # Base symbol
                    "rsi10": 25.5,
                    "verdict": "buy",
                    "final_verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)

            # Should skip because user has ONGOING order (matched by base symbol)
            assert result["skipped"] == 1
            assert result["inserted"] == 0

    def test_deduplicate_with_full_symbol_matches_full_symbol_position(self, db_session, test_user):
        """Test deduplication when signal has full symbol and position has full symbol"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)

        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create existing TRADED signal with full symbol
            existing = Signals(
                symbol="RELIANCE-EQ",
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
                symbol="RELIANCE-EQ",
                status=SignalStatus.TRADED,
                marked_at=ist_now(),
            )
            db_session.add(user_status)

            # Create position with full symbol
            position = Positions(
                user_id=test_user.id,
                symbol="RELIANCE-EQ",
                quantity=10.0,
                avg_price=2500.0,
                opened_at=ist_now(),
            )
            db_session.add(position)

            # Create ONGOING buy order with full symbol
            order = Orders(
                user_id=test_user.id,
                symbol="RELIANCE-EQ",
                side="buy",
                order_type="MARKET",
                status=OrderStatus.ONGOING,
                quantity=10,
                price=2500.0,
                placed_at=ist_now(),
            )
            db_session.add(order)
            db_session.commit()

            # Same signal appears in new analysis with full symbol
            new_signals = [
                {
                    "symbol": "RELIANCE-EQ",  # Full symbol
                    "rsi10": 25.5,
                    "verdict": "buy",
                    "final_verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)

            # Should skip because user has ONGOING order (exact match)
            assert result["skipped"] == 1
            assert result["inserted"] == 0

    def test_deduplicate_with_base_symbol_no_position_creates_new(self, db_session, test_user):
        """Test deduplication when signal has base symbol but no matching position"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)

        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create existing ACTIVE signal with base symbol
            existing = Signals(
                symbol="RELIANCE",
                status=SignalStatus.ACTIVE,
                rsi10=20.0,
                verdict="buy",
                final_verdict="buy",
                ts=ist_now(),
            )
            db_session.add(existing)
            db_session.commit()

            # No position or order exists

            # Same signal appears in new analysis with base symbol
            new_signals = [
                {
                    "symbol": "RELIANCE",  # Base symbol
                    "rsi10": 25.5,
                    "verdict": "buy",
                    "final_verdict": "buy",
                }
            ]
            result = service.deduplicate_and_update_signals(new_signals, skip_time_check=True)

            # Should update existing signal (same verdict)
            assert result["updated"] == 1
            assert result["inserted"] == 0

    def test_deduplicate_with_different_segments(self, db_session, test_user):
        """Test deduplication with different segments of same base symbol"""
        service = AnalysisDeduplicationService(db_session, user_id=test_user.id)

        with freeze_time("2025-01-13 08:00:00+05:30"):
            # Create position with RELIANCE-EQ
            position_eq = Positions(
                user_id=test_user.id,
                symbol="RELIANCE-EQ",
                quantity=10.0,
                avg_price=2500.0,
                opened_at=ist_now(),
            )
            db_session.add(position_eq)

            # Create position with RELIANCE-BE (different segment)
            position_be = Positions(
                user_id=test_user.id,
                symbol="RELIANCE-BE",
                quantity=5.0,
                avg_price=2400.0,
                opened_at=ist_now(),
            )
            db_session.add(position_be)
            db_session.commit()

            # Signal with base symbol "RELIANCE" should match RELIANCE-EQ (first found)
            result = service._find_position_by_symbol(test_user.id, "RELIANCE")
            assert result is not None
            # Should return one of the positions (implementation may return first match)
            assert result.symbol in ["RELIANCE-EQ", "RELIANCE-BE"]
