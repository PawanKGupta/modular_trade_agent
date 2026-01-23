"""
Fills Repository - CRUD operations for order fills/executions

Handles partial order fills, aggregation, and fill history queries.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Fills
from src.infrastructure.db.timezone_utils import ist_now


class FillsRepository:
    """Repository for managing order fills"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        order_id: int,
        user_id: int | None = None,
        qty: float | None = None,
        quantity: float | None = None,
        price: float,
        charges: float = 0.0,
        ts: datetime | None = None,
        filled_at: datetime | None = None,
        broker_fill_id: str | None = None,
        auto_commit: bool = True,
    ) -> Fills:
        """
        Create a new fill record

        Args:
            order_id: Parent order ID
            user_id: User ID (denormalized for queries)
            qty/quantity: Quantity filled (accepts either parameter name)
            price: Fill price
            charges: Brokerage + taxes for this fill
            ts/filled_at: Fill timestamp (accepts either parameter name, defaults to now)
            broker_fill_id: Broker's fill ID for deduplication
            auto_commit: Commit immediately if True

        Returns:
            Created Fill object
        """
        # Accept both parameter names for backward compatibility
        fill_qty = quantity if quantity is not None else (qty if qty is not None else 0.0)
        fill_ts = filled_at if filled_at is not None else (ts if ts is not None else ist_now())

        fill_value = fill_qty * price

        fill = Fills(
            order_id=order_id,
            user_id=user_id or 0,  # Will be set properly by caller
            quantity=fill_qty,
            price=price,
            fill_value=fill_value,
            charges=charges,
            filled_at=fill_ts,
            created_at=ist_now(),
            broker_fill_id=broker_fill_id,
        )

        self.db.add(fill)
        if auto_commit:
            self.db.commit()
            self.db.refresh(fill)
        else:
            # Flush so the fill is visible to subsequent queries in the same transaction
            self.db.flush()

        return fill

    def get(self, fill_id: int) -> Fills | None:
        """Get fill by ID"""
        return self.db.get(Fills, fill_id)

    def get_by_broker_fill_id(self, broker_fill_id: str) -> Fills | None:
        """Get fill by broker fill ID (for deduplication)"""
        if not broker_fill_id:
            return None

        return self.db.query(Fills).filter(Fills.broker_fill_id == broker_fill_id).first()

    def list_by_order(self, order_id: int) -> list[Fills]:
        """List all fills for an order"""
        stmt = select(Fills).where(Fills.order_id == order_id).order_by(Fills.filled_at)
        return list(self.db.execute(stmt).scalars().all())

    def list_by_user(
        self, user_id: int, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> list[Fills]:
        """Get all fills for a user, optionally filtered by date range"""
        query = self.db.query(Fills).filter(Fills.user_id == user_id)

        if start_date:
            query = query.filter(Fills.filled_at >= start_date)
        if end_date:
            query = query.filter(Fills.filled_at <= end_date)

        return query.order_by(desc(Fills.filled_at)).all()

    def get_fill_summary(self, order_id: int) -> dict:
        """
        Aggregate fill data for an order

        Returns:
            {
                'total_qty': sum of filled quantities,
                'total_value': sum of fill values,
                'total_charges': sum of charges,
                'avg_price': weighted average price,
                'fill_count': number of fills
            }
        """
        fills = self.list_by_order(order_id)

        if not fills:
            return {
                "total_qty": 0.0,
                "total_value": 0.0,
                "total_charges": 0.0,
                "avg_price": 0.0,
                "fill_count": 0,
            }

        total_qty = sum(f.quantity for f in fills)
        total_value = sum(f.fill_value for f in fills)
        total_charges = sum(f.charges for f in fills)

        # Weighted average price
        avg_price = total_value / total_qty if total_qty > 0 else 0.0

        return {
            "total_qty": total_qty,
            "total_value": total_value,
            "total_charges": total_charges,
            "avg_price": avg_price,
            "fill_count": len(fills),
        }

    def delete_by_order(self, order_id: int, auto_commit: bool = True) -> int:
        """Delete all fills for an order. Returns count of deleted fills."""
        count = self.db.query(Fills).filter(Fills.order_id == order_id).delete()
        if auto_commit:
            self.db.commit()
        return count

    def bulk_create(self, fills: list[dict]) -> list[Fills]:
        """Bulk create fills (for migration)"""
        created_fills = []
        for fill_data in fills:
            # Ensure fill_value is calculated if not provided
            if "fill_value" not in fill_data:
                fill_data["fill_value"] = fill_data["quantity"] * fill_data["price"]

            # Ensure filled_at is set if not provided
            if "filled_at" not in fill_data:
                fill_data["filled_at"] = ist_now()

            # Ensure created_at is set if not provided
            if "created_at" not in fill_data:
                fill_data["created_at"] = ist_now()

            # Set default charges if not provided
            if "charges" not in fill_data:
                fill_data["charges"] = 0.0

            fill = Fills(**fill_data)
            self.db.add(fill)
            created_fills.append(fill)
        self.db.commit()
        for fill in created_fills:
            self.db.refresh(fill)
        return created_fills
