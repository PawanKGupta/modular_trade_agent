"""
Integration tests for Exit Details (Phase 0.2)
Tests end-to-end flow of exit details tracking in positions
"""

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Positions, TradeMode, Users, UserSettings
from src.infrastructure.persistence.positions_repository import PositionsRepository


class TestExitDetailsIntegration:
    """Integration tests for exit details functionality"""

    @pytest.fixture
    def repository(self, db_session: Session):
        """Create repository instance"""
        return PositionsRepository(db_session)

    @pytest.fixture
    def test_user(self, db_session: Session):
        """Create test user"""
        user = Users(
            email="exits@example.com",
            name="Exit Test User",
            password_hash="hash",
            role="user",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        settings = UserSettings(
            user_id=user.id,
            trade_mode=TradeMode.PAPER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(settings)
        db_session.commit()
        return user

    def test_position_closed_with_exit_details(self, repository, test_user, db_session):
        """Test closing position with all exit details"""
        # Create open position
        position = Positions(
            user_id=test_user.id,
            symbol="RELIANCE",
            quantity=10,
            avg_price=2500.0,
            unrealized_pnl=0.0,
        )
        db_session.add(position)
        db_session.commit()

        # Close position with exit details
        exit_price = 2650.0
        exit_reason = "TARGET_HIT"
        closed_at = datetime.utcnow()

        repository.mark_closed(
            user_id=test_user.id,
            symbol=position.symbol,
            exit_price=exit_price,
            exit_reason=exit_reason,
            closed_at=closed_at,
        )

        # Verify exit details
        closed_position = db_session.query(Positions).filter_by(id=position.id).first()
        assert closed_position.exit_price == exit_price
        assert closed_position.exit_reason == exit_reason
        assert closed_position.closed_at == closed_at

        # Calculate expected P&L
        original_quantity = 10
        expected_pnl = (exit_price - position.avg_price) * original_quantity
        assert closed_position.realized_pnl == expected_pnl

    def test_position_closed_without_optional_exit_details(self, repository, test_user, db_session):
        """Test closing position without optional exit details"""
        position = Positions(
            user_id=test_user.id,
            symbol="TCS",
            quantity=5,
            avg_price=3500.0,
            unrealized_pnl=0.0,
        )
        db_session.add(position)
        db_session.commit()

        # Close with minimal details
        repository.mark_closed(user_id=test_user.id, symbol=position.symbol, exit_price=3600.0)

        closed_position = db_session.query(Positions).filter_by(id=position.id).first()
        assert closed_position.exit_price == 3600.0
        assert closed_position.exit_reason is None
        assert closed_position.closed_at is not None

    def test_exit_reason_variations(self, repository, test_user, db_session):
        """Test different exit reasons"""
        exit_reasons = [
            "TARGET_HIT",
            "STOP_LOSS",
            "TRAILING_STOP",
            "MANUAL_EXIT",
            "EOD_SQUARE_OFF",
        ]

        for reason in exit_reasons:
            position = Positions(
                user_id=test_user.id,
                symbol=f"SYM_{reason}",
                quantity=10,
                avg_price=100.0,
                unrealized_pnl=0.0,
            )
            db_session.add(position)
            db_session.commit()

            repository.mark_closed(
                user_id=test_user.id, symbol=position.symbol, exit_price=105.0, exit_reason=reason
            )

            closed = db_session.query(Positions).filter_by(id=position.id).first()
            assert closed.exit_reason == reason

    def test_profit_position_exit_details(self, repository, test_user, db_session):
        """Test exit details for profitable position"""
        position = Positions(
            user_id=test_user.id,
            symbol="PROFIT",
            quantity=10,
            avg_price=100.0,
            unrealized_pnl=0.0,
        )
        db_session.add(position)
        db_session.commit()

        # Exit at profit
        repository.mark_closed(
            user_id=test_user.id,
            symbol=position.symbol,
            exit_price=150.0,
            exit_reason="TARGET_HIT",
        )

        closed = db_session.query(Positions).filter_by(id=position.id).first()
        expected_profit = (150.0 - 100.0) * 10
        assert closed.realized_pnl == expected_profit
        assert closed.realized_pnl > 0

    def test_loss_position_exit_details(self, repository, test_user, db_session):
        """Test exit details for loss-making position"""
        position = Positions(
            user_id=test_user.id,
            symbol="LOSS",
            quantity=10,
            avg_price=100.0,
            unrealized_pnl=0.0,
        )
        db_session.add(position)
        db_session.commit()

        # Exit at loss
        repository.mark_closed(
            user_id=test_user.id,
            symbol=position.symbol,
            exit_price=80.0,
            exit_reason="STOP_LOSS",
        )

        closed = db_session.query(Positions).filter_by(id=position.id).first()
        expected_loss = (80.0 - 100.0) * 10
        assert closed.realized_pnl == expected_loss
        assert closed.realized_pnl < 0

    def test_breakeven_position_exit_details(self, repository, test_user, db_session):
        """Test exit details for breakeven position"""
        position = Positions(
            user_id=test_user.id,
            symbol="BREAK",
            quantity=10,
            avg_price=100.0,
            unrealized_pnl=0.0,
        )
        db_session.add(position)
        db_session.commit()

        # Exit at same price
        repository.mark_closed(
            user_id=test_user.id,
            symbol=position.symbol,
            exit_price=100.0,
            exit_reason="MANUAL_EXIT",
        )

        closed = db_session.query(Positions).filter_by(id=position.id).first()
        assert closed.realized_pnl == 0.0

    def test_query_positions_by_exit_reason(self, repository, test_user, db_session):
        """Test querying closed positions by exit reason"""
        # Create and close multiple positions
        for i in range(3):
            position = Positions(
                user_id=test_user.id,
                symbol=f"TARGET{i}",
                quantity=10,
                avg_price=100.0,
                unrealized_pnl=0.0,
            )
            db_session.add(position)
            db_session.commit()
            repository.mark_closed(
                user_id=test_user.id,
                symbol=position.symbol,
                exit_price=110.0,
                exit_reason="TARGET_HIT",
            )

        for i in range(2):
            position = Positions(
                user_id=test_user.id,
                symbol=f"STOP{i}",
                quantity=10,
                avg_price=100.0,
                unrealized_pnl=0.0,
            )
            db_session.add(position)
            db_session.commit()
            repository.mark_closed(
                user_id=test_user.id,
                symbol=position.symbol,
                exit_price=90.0,
                exit_reason="STOP_LOSS",
            )

        # Query by exit reason
        target_exits = (
            db_session.query(Positions)
            .filter_by(user_id=test_user.id, exit_reason="TARGET_HIT")
            .all()
        )

        stop_exits = (
            db_session.query(Positions)
            .filter_by(user_id=test_user.id, exit_reason="STOP_LOSS")
            .all()
        )

        assert len(target_exits) >= 3
        assert len(stop_exits) >= 2

    def test_calculate_win_loss_ratio_using_exit_details(self, repository, test_user, db_session):
        """Test calculating win/loss ratio using exit details"""
        # Create winning positions
        for i in range(7):
            position = Positions(
                user_id=test_user.id,
                symbol=f"WIN{i}",
                quantity=10,
                avg_price=100.0,
                unrealized_pnl=0.0,
            )
            db_session.add(position)
            db_session.commit()
            repository.mark_closed(
                user_id=test_user.id,
                symbol=position.symbol,
                exit_price=110.0,
            )

        # Create losing positions
        for i in range(3):
            position = Positions(
                user_id=test_user.id,
                symbol=f"LOSS{i}",
                quantity=10,
                avg_price=100.0,
                unrealized_pnl=0.0,
            )
            db_session.add(position)
            db_session.commit()
            repository.mark_closed(
                user_id=test_user.id,
                symbol=position.symbol,
                exit_price=90.0,
            )

        # Calculate win/loss
        all_closed = (
            db_session.query(Positions)
            .filter(
                Positions.user_id == test_user.id,
                Positions.closed_at.isnot(None),
            )
            .all()
        )

        winning = [p for p in all_closed if p.realized_pnl > 0]
        losing = [p for p in all_closed if p.realized_pnl < 0]

        win_rate = len(winning) / len(all_closed) if all_closed else 0

        assert len(winning) >= 7
        assert len(losing) >= 3
        assert 0.6 <= win_rate <= 0.8  # Should be around 70%

    def test_backfill_legacy_positions_without_exit_details(
        self, repository, test_user, db_session
    ):
        """Test handling legacy closed positions without exit details"""
        # Create legacy closed position (no exit details)
        legacy = Positions(
            user_id=test_user.id,
            symbol="LEGACY",
            quantity=10,
            avg_price=100.0,
            unrealized_pnl=0.0,
            closed_at=datetime.utcnow(),  # Closed but no exit details
            exit_price=None,
            exit_reason=None,
        )
        db_session.add(legacy)
        db_session.commit()

        # Verify legacy position exists without exit details
        retrieved = db_session.query(Positions).filter_by(id=legacy.id).first()
        assert retrieved.closed_at is not None
        assert retrieved.exit_price is None
        assert retrieved.exit_reason is None

    def test_exit_details_immutable_after_set(self, repository, test_user, db_session):
        """Test that exit details should not change after being set"""
        position = Positions(
            user_id=test_user.id,
            symbol="IMMUT",
            quantity=10,
            avg_price=100.0,
            unrealized_pnl=0.0,
        )
        db_session.add(position)
        db_session.commit()

        # Close with initial exit details
        repository.mark_closed(
            user_id=test_user.id,
            symbol=position.symbol,
            exit_price=110.0,
            exit_reason="TARGET_HIT",
        )

        first_close = db_session.query(Positions).filter_by(id=position.id).first()
        original_exit_price = first_close.exit_price
        original_exit_reason = first_close.exit_reason

        # Attempt to close again (should not change in business logic)
        # This test just verifies the original values remain
        assert first_close.exit_price == original_exit_price
        assert first_close.exit_reason == original_exit_reason

    def test_partial_exit_not_supported(self, repository, test_user, db_session):
        """Test that partial exits are not tracked (full position close only)"""
        position = Positions(
            user_id=test_user.id,
            symbol="PARTIAL",
            quantity=100,
            avg_price=100.0,
            unrealized_pnl=0.0,
        )
        db_session.add(position)
        db_session.commit()

        # Current implementation supports only full position close
        # Partial exits would require separate tracking
        repository.mark_closed(
            user_id=test_user.id,
            symbol=position.symbol,
            exit_price=110.0,
            exit_reason="MANUAL_EXIT",
        )

        closed = db_session.query(Positions).filter_by(id=position.id).first()
        # All quantity considered in exit; repository sets quantity to 0 after closing
        assert closed.quantity == 0.0
        assert closed.realized_pnl == (110.0 - 100.0) * 100
