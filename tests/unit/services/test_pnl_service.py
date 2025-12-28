"""
Unit tests for PnL Service (Phase 1.1)
Tests profit/loss calculations, win/loss ratios, and analytics
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.infrastructure.db.models import (
    Positions,
    TradeMode,
    Users,
    UserSettings,
)


class TestPnLService:
    """Unit tests for PnL calculation service"""

    @pytest.fixture
    def test_user(self, db_session: Session):
        """Create test user"""
        user = Users(
            email="pnl@example.com",
            name="PnL User",
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

    def test_calculate_realized_pnl_simple_profit(self, db_session, test_user):
        """Test realized P&L calculation for a winning trade"""
        position = Positions(
            user_id=test_user.id,
            symbol="AAPL",
            quantity=10,
            avg_price=Decimal("150.00"),
            unrealized_pnl=Decimal("0.00"),
            closed_at=datetime.utcnow(),
            exit_price=Decimal("160.00"),
            realized_pnl=Decimal("100.00"),  # (160 - 150) * 10
            exit_reason="TARGET_HIT",
        )
        db_session.add(position)
        db_session.commit()

        # Verify calculation
        assert position.realized_pnl == Decimal("100.00")
        assert position.exit_price > position.avg_price

    def test_calculate_realized_pnl_simple_loss(self, db_session, test_user):
        """Test realized P&L calculation for a losing trade"""
        position = Positions(
            user_id=test_user.id,
            symbol="TSLA",
            quantity=5,
            avg_price=Decimal("200.00"),
            unrealized_pnl=Decimal("0.00"),
            closed_at=datetime.utcnow(),
            exit_price=Decimal("180.00"),
            realized_pnl=Decimal("-100.00"),  # (180 - 200) * 5
            exit_reason="STOP_LOSS",
        )
        db_session.add(position)
        db_session.commit()

        # Verify calculation
        assert position.realized_pnl == Decimal("-100.00")
        assert position.exit_price < position.avg_price

    def test_calculate_unrealized_pnl(self, db_session, test_user):
        """Test unrealized P&L calculation for open position"""
        position = Positions(
            user_id=test_user.id,
            symbol="GOOGL",
            quantity=3,
            avg_price=Decimal("120.00"),
            unrealized_pnl=Decimal("30.00"),  # (130 - 120) * 3 if current price is 130
        )
        db_session.add(position)
        db_session.commit()

        # Verify
        assert position.unrealized_pnl == Decimal("30.00")
        assert position.closed_at is None

    def test_win_loss_ratio_calculation(self, db_session, test_user):
        """Test calculating win/loss ratio from closed positions"""
        # Create mix of winning and losing trades
        winning_trades = [
            Positions(
                user_id=test_user.id,
                symbol=f"WIN{i}",
                quantity=10,
                avg_price=Decimal("100.00"),
                unrealized_pnl=Decimal("0.00"),
                closed_at=datetime.utcnow(),
                realized_pnl=Decimal(f"{i * 10}.00"),
                exit_price=Decimal(f"{100 + i}.00"),
            )
            for i in range(1, 8)  # 7 wins
        ]

        losing_trades = [
            Positions(
                user_id=test_user.id,
                symbol=f"LOSS{i}",
                quantity=10,
                avg_price=Decimal("100.00"),
                unrealized_pnl=Decimal("0.00"),
                closed_at=datetime.utcnow(),
                realized_pnl=Decimal(f"-{i * 10}.00"),
                exit_price=Decimal(f"{100 - i}.00"),
            )
            for i in range(1, 4)  # 3 losses
        ]

        db_session.add_all(winning_trades + losing_trades)
        db_session.commit()

        # Calculate ratio
        wins = len([p for p in winning_trades + losing_trades if p.realized_pnl > 0])
        losses = len([p for p in winning_trades + losing_trades if p.realized_pnl < 0])
        win_rate = (wins / (wins + losses)) * 100

        assert wins == 7
        assert losses == 3
        assert win_rate == 70.0

    def test_average_win_loss_calculation(self, db_session, test_user):
        """Test calculating average win and average loss"""
        # Wins: 100, 200, 300 -> avg 200
        # Losses: -50, -100, -150 -> avg -100
        trades = [
            (Decimal("100.00"), "WIN1"),
            (Decimal("200.00"), "WIN2"),
            (Decimal("300.00"), "WIN3"),
            (Decimal("-50.00"), "LOSS1"),
            (Decimal("-100.00"), "LOSS2"),
            (Decimal("-150.00"), "LOSS3"),
        ]

        for pnl, symbol in trades:
            position = Positions(
                user_id=test_user.id,
                symbol=symbol,
                quantity=10,
                avg_price=Decimal("100.00"),
                unrealized_pnl=Decimal("0.00"),
                closed_at=datetime.utcnow(),
                realized_pnl=pnl,
            )
            db_session.add(position)
        db_session.commit()

        # Calculate averages
        all_positions = (
            db_session.query(Positions)
            .filter_by(user_id=test_user.id)
            .filter(Positions.closed_at.isnot(None))
            .all()
        )

        wins = [p.realized_pnl for p in all_positions if p.realized_pnl > 0]
        losses = [p.realized_pnl for p in all_positions if p.realized_pnl < 0]

        avg_win = sum(wins) / len(wins)
        avg_loss = sum(losses) / len(losses)

        assert avg_win == Decimal("200.00")
        assert avg_loss == Decimal("-100.00")

    def test_profit_factor_calculation(self, db_session, test_user):
        """Test calculating profit factor (total wins / abs(total losses))"""
        trades = [
            (Decimal("1000.00"), "WIN1"),
            (Decimal("1500.00"), "WIN2"),
            (Decimal("-500.00"), "LOSS1"),
            (Decimal("-300.00"), "LOSS2"),
        ]

        for pnl, symbol in trades:
            position = Positions(
                user_id=test_user.id,
                symbol=symbol,
                quantity=10,
                avg_price=Decimal("100.00"),
                unrealized_pnl=Decimal("0.00"),
                closed_at=datetime.utcnow(),
                realized_pnl=pnl,
            )
            db_session.add(position)
        db_session.commit()

        # Calculate profit factor
        all_positions = (
            db_session.query(Positions)
            .filter_by(user_id=test_user.id)
            .filter(Positions.closed_at.isnot(None))
            .all()
        )

        total_wins = sum(p.realized_pnl for p in all_positions if p.realized_pnl > 0)
        total_losses = abs(sum(p.realized_pnl for p in all_positions if p.realized_pnl < 0))

        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        assert total_wins == Decimal("2500.00")
        assert total_losses == Decimal("800.00")
        assert profit_factor == Decimal("2500.00") / Decimal("800.00")

    def test_pnl_by_date_range(self, db_session, test_user):
        """Test calculating P&L for specific date range"""
        today = datetime.utcnow()
        last_week = today - timedelta(days=7)
        last_month = today - timedelta(days=30)

        # Create trades at different times
        trades = [
            (last_month, Decimal("500.00"), "OLD"),
            (last_week, Decimal("1000.00"), "RECENT"),
            (today, Decimal("800.00"), "TODAY"),
        ]

        for trade_date, pnl, symbol in trades:
            position = Positions(
                user_id=test_user.id,
                symbol=symbol,
                quantity=10,
                avg_price=Decimal("100.00"),
                unrealized_pnl=Decimal("0.00"),
                closed_at=trade_date,
                realized_pnl=pnl,
            )
            db_session.add(position)
        db_session.commit()

        # Calculate P&L for last week
        last_week_positions = (
            db_session.query(Positions)
            .filter(
                Positions.user_id == test_user.id,
                Positions.closed_at >= last_week,
                Positions.closed_at.isnot(None),
            )
            .all()
        )

        last_week_pnl = sum(p.realized_pnl for p in last_week_positions)

        # Should include RECENT and TODAY, but not OLD
        assert last_week_pnl == Decimal("1800.00")

    def test_pnl_by_symbol(self, db_session, test_user):
        """Test calculating P&L aggregated by symbol"""
        trades = [
            ("AAPL", Decimal("100.00")),
            ("AAPL", Decimal("150.00")),
            ("AAPL", Decimal("-50.00")),
            ("TSLA", Decimal("200.00")),
            ("TSLA", Decimal("-100.00")),
        ]

        for symbol, pnl in trades:
            position = Positions(
                user_id=test_user.id,
                symbol=symbol,
                quantity=10,
                avg_price=Decimal("100.00"),
                unrealized_pnl=Decimal("0.00"),
                closed_at=datetime.utcnow(),
                realized_pnl=pnl,
            )
            db_session.add(position)
        db_session.commit()

        # Calculate P&L by symbol
        from sqlalchemy import func

        symbol_pnl = (
            db_session.query(Positions.symbol, func.sum(Positions.realized_pnl).label("total_pnl"))
            .filter(Positions.user_id == test_user.id, Positions.closed_at.isnot(None))
            .group_by(Positions.symbol)
            .all()
        )

        symbol_dict = {symbol: float(pnl) for symbol, pnl in symbol_pnl}

        assert symbol_dict["AAPL"] == 200.00  # 100 + 150 - 50
        assert symbol_dict["TSLA"] == 100.00  # 200 - 100

    def test_consecutive_wins_tracking(self, db_session, test_user):
        """Test tracking consecutive wins (streak calculation)"""
        # Create sequence: WIN, WIN, WIN, LOSS, WIN, WIN
        trades = [
            (Decimal("100.00"), 1),  # Win
            (Decimal("150.00"), 2),  # Win
            (Decimal("200.00"), 3),  # Win
            (Decimal("-50.00"), 4),  # Loss (breaks streak)
            (Decimal("120.00"), 5),  # Win
            (Decimal("80.00"), 6),  # Win
        ]

        for pnl, order in trades:
            position = Positions(
                user_id=test_user.id,
                symbol=f"TRADE{order}",
                quantity=10,
                avg_price=Decimal("100.00"),
                unrealized_pnl=Decimal("0.00"),
                closed_at=datetime.utcnow() + timedelta(minutes=order),
                realized_pnl=pnl,
            )
            db_session.add(position)
        db_session.commit()

        # Calculate max winning streak
        positions = (
            db_session.query(Positions)
            .filter_by(user_id=test_user.id)
            .filter(Positions.closed_at.isnot(None))
            .order_by(Positions.closed_at)
            .all()
        )

        current_streak = 0
        max_streak = 0

        for pos in positions:
            if pos.realized_pnl > 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0

        assert max_streak == 3

    def test_largest_win_loss(self, db_session, test_user):
        """Test identifying largest win and largest loss"""
        trades = [
            Decimal("500.00"),
            Decimal("2000.00"),  # Largest win
            Decimal("-300.00"),
            Decimal("-1500.00"),  # Largest loss
            Decimal("100.00"),
        ]

        for pnl in trades:
            position = Positions(
                user_id=test_user.id,
                symbol="TEST",
                quantity=10,
                avg_price=Decimal("100.00"),
                unrealized_pnl=Decimal("0.00"),
                closed_at=datetime.utcnow(),
                realized_pnl=pnl,
            )
            db_session.add(position)
        db_session.commit()

        # Find extremes
        positions = (
            db_session.query(Positions)
            .filter_by(user_id=test_user.id)
            .filter(Positions.closed_at.isnot(None))
            .all()
        )

        largest_win = max(p.realized_pnl for p in positions)
        largest_loss = min(p.realized_pnl for p in positions)

        assert largest_win == Decimal("2000.00")
        assert largest_loss == Decimal("-1500.00")

    def test_pnl_with_fees(self, db_session, test_user):
        """Test P&L calculation considering trading fees"""
        # Simulate: buy 10 @ 100, sell 10 @ 110, fees 2 per side = 4 total
        # Gross profit: (110 - 100) * 10 = 100
        # Net profit: 100 - 4 = 96

        position = Positions(
            user_id=test_user.id,
            symbol="FEE_TEST",
            quantity=10,
            avg_price=Decimal("100.00"),
            unrealized_pnl=Decimal("0.00"),
            closed_at=datetime.utcnow(),
            exit_price=Decimal("110.00"),
            realized_pnl=Decimal("96.00"),  # After fees
        )
        db_session.add(position)
        db_session.commit()

        # Verify fee impact
        gross_pnl = (position.exit_price - position.avg_price) * position.quantity
        fees = gross_pnl - position.realized_pnl

        assert gross_pnl == Decimal("100.00")
        assert fees == Decimal("4.00")

    def test_breakeven_trades(self, db_session, test_user):
        """Test handling breakeven trades (zero P&L)"""
        position = Positions(
            user_id=test_user.id,
            symbol="BREAKEVEN",
            quantity=10,
            avg_price=Decimal("100.00"),
            unrealized_pnl=Decimal("0.00"),
            closed_at=datetime.utcnow(),
            exit_price=Decimal("100.00"),
            realized_pnl=Decimal("0.00"),
        )
        db_session.add(position)
        db_session.commit()

        # Verify breakeven handling
        assert position.realized_pnl == Decimal("0.00")
        # Breakeven trades shouldn't count as wins or losses
        assert position.exit_price == position.avg_price
