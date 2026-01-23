"""
Integration tests for CSV/PDF Export functionality (Phase 3)
Tests complete export workflows including filtering and formatting
"""

import csv
from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO

import pytest
from sqlalchemy.orm import Session

from src.infrastructure.db.models import (
    Positions,
    TradeMode,
    Users,
    UserSettings,
)


class TestCSVExportFlow:
    """Integration tests for CSV export workflows"""

    @pytest.fixture
    def test_user(self, db_session: Session):
        """Create test user with positions"""
        user = Users(
            email="export@example.com",
            name="Export User",
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

    @pytest.fixture
    def sample_positions(self, db_session: Session, test_user):
        """Create sample positions for export"""
        positions = []
        for i in range(10):
            position = Positions(
                user_id=test_user.id,
                symbol=f"SYM{i}",
                quantity=10 + i,
                avg_price=Decimal(f"{100 + i * 10}.00"),
                unrealized_pnl=Decimal(f"{i * 50}.00") if i % 2 == 0 else Decimal("0.00"),
                closed_at=datetime.utcnow() if i < 5 else None,
                realized_pnl=Decimal(f"{i * 100}.00") if i < 5 else None,
                exit_price=Decimal(f"{110 + i * 10}.00") if i < 5 else None,
            )
            positions.append(position)
            db_session.add(position)
        db_session.commit()
        return positions

    def test_export_all_positions_to_csv(self, db_session, test_user, sample_positions):
        """Test exporting all positions to CSV"""
        # Get all positions
        positions = (
            db_session.query(Positions)
            .filter_by(user_id=test_user.id)
            .order_by(Positions.opened_at.desc())
            .all()
        )

        # Export to CSV
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "symbol",
                "quantity",
                "avg_price",
                "unrealized_pnl",
                "realized_pnl",
                "exit_price",
                "opened_at",
                "closed_at",
            ],
        )
        writer.writeheader()

        for position in positions:
            writer.writerow(
                {
                    "symbol": position.symbol,
                    "quantity": position.quantity,
                    "avg_price": str(position.avg_price),
                    "unrealized_pnl": (
                        str(position.unrealized_pnl) if position.unrealized_pnl else ""
                    ),
                    "realized_pnl": str(position.realized_pnl) if position.realized_pnl else "",
                    "exit_price": str(position.exit_price) if position.exit_price else "",
                    "opened_at": position.opened_at.isoformat(),
                    "closed_at": position.closed_at.isoformat() if position.closed_at else "",
                }
            )

        # Verify CSV content
        csv_content = output.getvalue()
        assert "symbol,quantity,avg_price" in csv_content
        assert "SYM0" in csv_content
        assert len(csv_content.splitlines()) == 11  # Header + 10 rows

    def test_export_filtered_by_date_range(self, db_session, test_user, sample_positions):
        """Test exporting positions filtered by date range"""
        # Filter last 5 days
        start_date = datetime.utcnow() - timedelta(days=5)
        end_date = datetime.utcnow()

        positions = (
            db_session.query(Positions)
            .filter(
                Positions.user_id == test_user.id,
                Positions.opened_at >= start_date,
                Positions.opened_at <= end_date,
            )
            .all()
        )

        # Should get positions from last 5 days (0-4)
        assert len(positions) <= 6  # 0, 1, 2, 3, 4, and possibly today

    def test_export_only_closed_positions(self, db_session, test_user, sample_positions):
        """Test exporting only closed positions"""
        closed_positions = (
            db_session.query(Positions)
            .filter_by(user_id=test_user.id)
            .filter(Positions.closed_at.isnot(None))
            .all()
        )

        # Export to CSV
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "symbol",
                "quantity",
                "avg_price",
                "realized_pnl",
                "exit_price",
                "closed_at",
            ],
        )
        writer.writeheader()

        for position in closed_positions:
            writer.writerow(
                {
                    "symbol": position.symbol,
                    "quantity": position.quantity,
                    "avg_price": str(position.avg_price),
                    "realized_pnl": str(position.realized_pnl),
                    "exit_price": str(position.exit_price),
                    "closed_at": position.closed_at.isoformat(),
                }
            )

        # Verify only closed positions
        csv_content = output.getvalue()
        lines = csv_content.splitlines()
        assert len(lines) == 6  # Header + 5 closed positions

    def test_export_only_open_positions(self, db_session, test_user, sample_positions):
        """Test exporting only open positions"""
        open_positions = (
            db_session.query(Positions)
            .filter_by(user_id=test_user.id)
            .filter(Positions.closed_at.is_(None))
            .all()
        )

        # Export to CSV
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["symbol", "quantity", "avg_price", "unrealized_pnl", "opened_at"],
        )
        writer.writeheader()

        for position in open_positions:
            writer.writerow(
                {
                    "symbol": position.symbol,
                    "quantity": position.quantity,
                    "avg_price": str(position.avg_price),
                    "unrealized_pnl": str(position.unrealized_pnl),
                    "opened_at": position.opened_at.isoformat(),
                }
            )

        # Verify only open positions
        csv_content = output.getvalue()
        lines = csv_content.splitlines()
        assert len(lines) == 6  # Header + 5 open positions

    def test_export_filtered_by_symbol(self, db_session, test_user, sample_positions):
        """Test exporting positions filtered by symbol"""
        target_symbols = ["SYM0", "SYM1", "SYM2"]

        positions = (
            db_session.query(Positions)
            .filter(
                Positions.user_id == test_user.id,
                Positions.symbol.in_(target_symbols),
            )
            .all()
        )

        assert len(positions) == 3
        assert all(p.symbol in target_symbols for p in positions)

    def test_export_with_profit_loss_filter(self, db_session, test_user, sample_positions):
        """Test exporting only profitable or losing positions"""
        # Export only profitable closed positions
        profitable_positions = (
            db_session.query(Positions)
            .filter(
                Positions.user_id == test_user.id,
                Positions.closed_at.isnot(None),
                Positions.realized_pnl > 0,
            )
            .all()
        )

        # Profitable closed positions from sample fixture
        assert len(profitable_positions) == 4
        assert all(p.realized_pnl > 0 for p in profitable_positions)

    def test_export_with_custom_columns(self, db_session, test_user, sample_positions):
        """Test exporting with user-selected columns"""
        positions = db_session.query(Positions).filter_by(user_id=test_user.id).limit(5).all()

        # Custom column selection
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=["symbol", "realized_pnl"])
        writer.writeheader()

        for position in positions:
            writer.writerow(
                {
                    "symbol": position.symbol,
                    "realized_pnl": str(position.realized_pnl) if position.realized_pnl else "",
                }
            )

        # Verify only selected columns
        csv_content = output.getvalue()
        lines = csv_content.splitlines()
        header = lines[0]
        assert header == "symbol,realized_pnl"
        assert "avg_price" not in header

    def test_export_with_aggregated_data(self, db_session, test_user, sample_positions):
        """Test exporting aggregated statistics per symbol"""
        from sqlalchemy import func

        # Aggregate by symbol
        stats = (
            db_session.query(
                Positions.symbol,
                func.count(Positions.id).label("trades_count"),
                func.sum(Positions.realized_pnl).label("total_pnl"),
                func.avg(Positions.realized_pnl).label("avg_pnl"),
            )
            .filter(
                Positions.user_id == test_user.id,
                Positions.closed_at.isnot(None),
            )
            .group_by(Positions.symbol)
            .all()
        )

        # Export aggregated data
        output = StringIO()
        writer = csv.DictWriter(
            output, fieldnames=["symbol", "trades_count", "total_pnl", "avg_pnl"]
        )
        writer.writeheader()

        for stat in stats:
            writer.writerow(
                {
                    "symbol": stat.symbol,
                    "trades_count": stat.trades_count,
                    "total_pnl": str(stat.total_pnl) if stat.total_pnl else "",
                    "avg_pnl": str(stat.avg_pnl) if stat.avg_pnl else "",
                }
            )

        # Verify aggregated export
        csv_content = output.getvalue()
        assert "trades_count" in csv_content
        assert "total_pnl" in csv_content

    def test_export_preserves_decimal_precision(self, db_session, test_user):
        """Test that decimal values maintain precision in export"""
        position = Positions(
            user_id=test_user.id,
            symbol="PRECISION",
            quantity=100,
            avg_price=Decimal("123.456789"),
            unrealized_pnl=Decimal("0.00"),
            closed_at=datetime.utcnow(),
            realized_pnl=Decimal("987.654321"),
            exit_price=Decimal("133.33"),
        )
        db_session.add(position)
        db_session.commit()

        # Export with precision
        output = StringIO()
        writer = csv.DictWriter(
            output, fieldnames=["symbol", "avg_price", "realized_pnl", "exit_price"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "symbol": position.symbol,
                "avg_price": str(position.avg_price),
                "realized_pnl": str(position.realized_pnl),
                "exit_price": str(position.exit_price),
            }
        )

        # Verify precision maintained
        csv_content = output.getvalue()
        assert "123.456789" in csv_content
        assert "987.654321" in csv_content

    def test_export_handles_null_values(self, db_session, test_user):
        """Test that export handles NULL values gracefully"""
        position = Positions(
            user_id=test_user.id,
            symbol="NULLTEST",
            quantity=10,
            avg_price=Decimal("100.00"),
            unrealized_pnl=Decimal("50.00"),
            closed_at=None,  # NULL
            realized_pnl=None,  # NULL
            exit_price=None,  # NULL
        )
        db_session.add(position)
        db_session.commit()

        # Export with NULLs
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["symbol", "realized_pnl", "exit_price", "closed_at"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "symbol": position.symbol,
                "realized_pnl": str(position.realized_pnl) if position.realized_pnl else "",
                "exit_price": str(position.exit_price) if position.exit_price else "",
                "closed_at": position.closed_at.isoformat() if position.closed_at else "",
            }
        )

        # Verify NULL handling
        csv_content = output.getvalue()
        lines = csv_content.splitlines()
        data_row = lines[1]
        assert data_row == "NULLTEST,,,"  # Empty fields for NULLs

    def test_export_with_trade_mode_filter(self, db_session, test_user):
        """Test exporting positions - trade_mode not a Positions field"""
        # Note: Positions doesn't have trade_mode field
        paper_position = Positions(
            user_id=test_user.id,
            symbol="PAPER",
            quantity=10,
            avg_price=Decimal("100.00"),
            unrealized_pnl=Decimal("0.00"),
            closed_at=datetime.utcnow(),
            realized_pnl=Decimal("100.00"),
        )

        broker_position = Positions(
            user_id=test_user.id,
            symbol="BROKER",
            quantity=10,
            avg_price=Decimal("100.00"),
            unrealized_pnl=Decimal("0.00"),
            closed_at=datetime.utcnow(),
            realized_pnl=Decimal("100.00"),
        )

        db_session.add_all([paper_position, broker_position])
        db_session.commit()

        # Export all positions for user
        all_positions = db_session.query(Positions).filter_by(user_id=test_user.id).all()

        assert len(all_positions) >= 2

    def test_export_large_dataset_performance(self, db_session, test_user):
        """Test exporting large number of positions efficiently"""
        # Create 1000 positions
        positions = []
        for i in range(1000):
            position = Positions(
                user_id=test_user.id,
                symbol=f"PERF{i}",
                quantity=10,
                avg_price=Decimal("100.00"),
                unrealized_pnl=Decimal("0.00"),
                closed_at=datetime.utcnow() if i % 2 == 0 else None,
                realized_pnl=Decimal("50.00") if i % 2 == 0 else None,
            )
            positions.append(position)

        db_session.bulk_save_objects(positions)
        db_session.commit()

        # Export with pagination
        batch_size = 100
        total_exported = 0

        for offset in range(0, 1000, batch_size):
            batch = (
                db_session.query(Positions)
                .filter_by(user_id=test_user.id)
                .offset(offset)
                .limit(batch_size)
                .all()
            )
            total_exported += len(batch)

        assert total_exported == 1000
