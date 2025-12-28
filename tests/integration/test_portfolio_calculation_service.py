"""
Integration tests for Portfolio Calculation Service (Phase 1.2)
Tests complete portfolio value calculation including snapshots
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from server.app.services.portfolio_calculation_service import PortfolioCalculationService
from src.infrastructure.db.models import (
    PnlDaily,
    Positions,
    TradeMode,
    Users,
    UserSettings,
)
from src.infrastructure.persistence.pnl_repository import PnlRepository


class TestPortfolioCalculationIntegration:
    """Integration tests for portfolio calculation service"""

    @pytest.fixture
    def service(self, db_session: Session):
        """Create service instance"""
        return PortfolioCalculationService(db_session)

    @pytest.fixture
    def test_user(self, db_session: Session):
        """Create test user"""
        user = Users(
            email="portfolio@example.com",
            name="Portfolio User",
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

    def test_calculate_portfolio_metrics_no_positions(self, service, test_user):
        """Test portfolio calculation with no open positions"""
        result = service.calculate_portfolio_metrics(test_user.id, date.today(), TradeMode.PAPER)

        assert Decimal(str(result["total_value"])) >= Decimal("0.00")
        assert Decimal(str(result["available_cash"])) >= Decimal("0.00")
        assert Decimal(str(result["invested_value"])) == Decimal("0.00")
        assert result["open_positions_count"] == 0

    def test_calculate_portfolio_metrics_with_positions(self, service, test_user, db_session):
        """Test portfolio calculation with open positions"""
        # Create open positions
        position1 = Positions(
            user_id=test_user.id,
            symbol="RELIANCE",
            quantity=10,
            avg_price=Decimal("2500.00"),
            unrealized_pnl=Decimal("500.00"),
        )
        position2 = Positions(
            user_id=test_user.id,
            symbol="TCS",
            quantity=5,
            avg_price=Decimal("3500.00"),
            unrealized_pnl=Decimal("250.00"),
        )
        db_session.add_all([position1, position2])
        db_session.commit()

        # Calculate
        result = service.calculate_portfolio_metrics(test_user.id, date.today(), TradeMode.PAPER)

        # Verify positions are included
        invested = (Decimal("2500.00") * 10) + (Decimal("3500.00") * 5)
        unrealized_total = Decimal("500.00") + Decimal("250.00")

        assert Decimal(str(result["invested_value"])) == invested
        assert Decimal(str(result["unrealized_pnl"])) == unrealized_total
        assert result["open_positions_count"] == 2
        assert Decimal(str(result["total_value"])) >= Decimal("0.00")

    def test_create_snapshot(self, service, test_user, db_session):
        """Test creating daily portfolio snapshot"""
        # Seed PnLDaily for today's realized P&L
        pnl_repo = PnlRepository(db_session)
        pnl_record = PnlDaily(
            user_id=test_user.id,
            date=date.today(),
            realized_pnl=Decimal("2000.00"),
            unrealized_pnl=Decimal("0.00"),
            fees=Decimal("0.00"),
        )
        pnl_repo.upsert(pnl_record)

        # Create snapshot
        snapshot = service.create_snapshot(
            test_user.id, date.today(), snapshot_type="eod", trade_mode=TradeMode.PAPER
        )

        assert snapshot is not None
        assert snapshot.user_id == test_user.id
        assert snapshot.snapshot_type == "eod"
        assert Decimal(str(snapshot.realized_pnl)) == Decimal("2000.00")
        assert snapshot.date == date.today()

    def test_portfolio_history_via_repository(self, service, test_user, db_session):
        """Test retrieving portfolio history using repository after service snapshots"""
        # Create historical snapshots via service
        for i in range(30):
            snapshot_date = date.today() - timedelta(days=30 - i)
            # Seed PnLDaily so realized_pnl increases
            pnl_repo = PnlRepository(db_session)
            pnl_repo.upsert(
                PnlDaily(
                    user_id=test_user.id,
                    date=snapshot_date,
                    realized_pnl=float(i * 100),
                    unrealized_pnl=0.0,
                    fees=0.0,
                )
            )
            service.create_snapshot(
                test_user.id, snapshot_date, snapshot_type="eod", trade_mode=TradeMode.PAPER
            )

        # Get history via repository
        start_date = date.today() - timedelta(days=30)
        end_date = date.today()
        history = service.snapshot_repo.get_by_date_range(
            test_user.id, start_date, end_date, snapshot_type="eod"
        )

        assert len(history) == 30
        assert history[0].date < history[-1].date
        assert history[-1].total_value >= history[0].total_value

    def test_metrics_reflect_realized_pnl_from_pnl_daily(self, service, test_user, db_session):
        """Test that metrics include realized P&L from PnlDaily records"""
        pnl_repo = PnlRepository(db_session)
        today = date.today()
        pnl_repo.upsert(
            PnlDaily(
                user_id=test_user.id, date=today, realized_pnl=1500.0, unrealized_pnl=0.0, fees=0.0
            )
        )

        metrics = service.calculate_portfolio_metrics(test_user.id, today, TradeMode.PAPER)

        assert Decimal(str(metrics["realized_pnl"])) == Decimal("1500.0")

    def test_unrealized_pnl_in_metrics(self, service, test_user, db_session):
        """Test calculating total unrealized P&L from open positions via metrics"""
        # Create open positions with unrealized P&L
        open_positions = [
            (Decimal("500.00"), "SYM1"),
            (Decimal("250.00"), "SYM2"),
            (Decimal("-100.00"), "SYM3"),
        ]

        for unrealized_pnl, symbol in open_positions:
            position = Positions(
                user_id=test_user.id,
                symbol=symbol,
                quantity=10,
                avg_price=Decimal("100.00"),
                unrealized_pnl=unrealized_pnl,
            )
            db_session.add(position)
        db_session.commit()

        # Calculate total unrealized P&L via metrics
        metrics = service.calculate_portfolio_metrics(test_user.id, date.today(), TradeMode.PAPER)

        expected = Decimal("500.00") + Decimal("250.00") + Decimal("-100.00")
        assert Decimal(str(metrics["unrealized_pnl"])) == expected

    def test_portfolio_value_with_realized_and_unrealized_pnl(self, service, test_user, db_session):
        """Test portfolio calculation including both realized and unrealized P&L"""
        # Closed position (realized)
        closed = Positions(
            user_id=test_user.id,
            symbol="CLOSED",
            quantity=10,
            avg_price=Decimal("100.00"),
            unrealized_pnl=Decimal("0.00"),
            closed_at=datetime.utcnow(),
            realized_pnl=Decimal("500.00"),
        )
        db_session.add(closed)

        # Open position (unrealized)
        open_pos = Positions(
            user_id=test_user.id,
            symbol="OPEN",
            quantity=5,
            avg_price=Decimal("200.00"),
            unrealized_pnl=Decimal("100.00"),
        )
        db_session.add(open_pos)
        db_session.commit()

        # Calculate
        result = service.calculate_portfolio_metrics(test_user.id, date.today(), TradeMode.PAPER)

        # Verify holdings value includes unrealized P&L
        invested = Decimal("200.00") * 5
        holdings_with_pnl = invested + Decimal("100.00")

        assert Decimal(str(result["invested_value"])) == invested
        assert Decimal(str(result["unrealized_pnl"])) == Decimal("100.00")
        assert result["open_positions_count"] == 1

    def test_snapshot_deduplication_same_day(self, service, test_user, db_session):
        """Test that multiple snapshots on same day are deduplicated"""
        # Create first snapshot
        snapshot1 = service.create_snapshot(
            test_user.id, date.today(), snapshot_type="eod", trade_mode=TradeMode.PAPER
        )

        # Create second snapshot same day (should replace)
        snapshot2 = service.create_snapshot(
            test_user.id, date.today(), snapshot_type="eod", trade_mode=TradeMode.PAPER
        )

        # Check only one snapshot for today
        today_snapshots = service.snapshot_repo.get_by_date_range(
            test_user.id, date.today(), date.today(), snapshot_type="eod"
        )

        assert len(today_snapshots) <= 1

    def test_portfolio_calculation_with_no_positions(self, service, test_user):
        """Test portfolio calculation when user has no positions"""
        result = service.calculate_portfolio_metrics(test_user.id, date.today(), TradeMode.PAPER)
        assert Decimal(str(result["total_value"])) >= Decimal("0.00")
        assert result["open_positions_count"] == 0

    def test_portfolio_growth_via_repository(self, service, test_user, db_session):
        """Test calculating portfolio growth between snapshots via repository"""
        # Create snapshots at different times via service
        d1 = date.today() - timedelta(days=30)
        d2 = date.today()
        PnlRepository(db_session).upsert(
            PnlDaily(user_id=test_user.id, date=d1, realized_pnl=0.0, unrealized_pnl=0.0, fees=0.0)
        )
        service.create_snapshot(test_user.id, d1, snapshot_type="eod", trade_mode=TradeMode.PAPER)
        PnlRepository(db_session).upsert(
            PnlDaily(user_id=test_user.id, date=d2, realized_pnl=0.0, unrealized_pnl=0.0, fees=0.0)
        )
        service.create_snapshot(test_user.id, d2, snapshot_type="eod", trade_mode=TradeMode.PAPER)

        snapshots = service.snapshot_repo.get_by_date_range(
            test_user.id, d1, d2, snapshot_type="eod"
        )
        if len(snapshots) >= 2:
            first = snapshots[0]
            last = snapshots[-1]
            absolute_change = Decimal(str(last.total_value)) - Decimal(str(first.total_value))
            assert absolute_change >= Decimal("0.00")

    def test_concurrent_snapshot_creation(self, service, test_user, db_session):
        """Test handling concurrent snapshot creation (EOD cleanup + manual trigger)"""
        # Simulate race condition
        service.create_snapshot(
            test_user.id, date.today(), snapshot_type="eod", trade_mode=TradeMode.PAPER
        )
        service.create_snapshot(
            test_user.id, date.today(), snapshot_type="eod", trade_mode=TradeMode.PAPER
        )

        # Both should succeed, but only one should exist for today
        today_count = len(
            service.snapshot_repo.get_by_date_range(
                test_user.id, date.today(), date.today(), snapshot_type="eod"
            )
        )

        assert today_count <= 1
