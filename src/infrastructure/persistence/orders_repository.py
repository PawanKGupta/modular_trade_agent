from __future__ import annotations

import builtins
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Orders, OrderStatus
from src.infrastructure.db.timezone_utils import ist_now


class OrdersRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, order_id: int) -> Orders | None:
        return self.db.get(Orders, order_id)

    def list(self, user_id: int, status: OrderStatus | None = None) -> builtins.list[Orders]:
        # Always use raw SQL fallback to avoid enum validation issues
        # This ensures compatibility with database schema regardless of SQLAlchemy metadata cache
        from sqlalchemy import inspect, text

        # Check which columns actually exist in the database
        inspector = inspect(self.db.bind)
        orders_columns = [col["name"] for col in inspector.get_columns("orders")]

        # Build SELECT query dynamically based on available columns
        base_columns = [
            "id",
            "user_id",
            "symbol",
            "side",
            "order_type",
            "quantity",
            "price",
            "status",
            "avg_price",
            "placed_at",
            "filled_at",
            "closed_at",
            "orig_source",
        ]
        optional_columns = []
        if "order_id" in orders_columns:
            optional_columns.append("order_id")
        if "broker_order_id" in orders_columns:
            optional_columns.append("broker_order_id")
        if "metadata" in orders_columns:
            optional_columns.append("metadata")

        all_columns = base_columns + optional_columns
        query = f"""
            SELECT {", ".join(all_columns)}
            FROM orders
            WHERE user_id = :user_id
        """
        params = {"user_id": user_id}
        if status:
            query += " AND status = :status"
            # Use enum value (lowercase) to match database
            params["status"] = status.value.lower()
        query += " ORDER BY placed_at DESC"

        results = self.db.execute(text(query), params).fetchall()

        # Helper function to convert string datetime to datetime object
        def parse_datetime(dt_value):
            """Convert string datetime to datetime object if needed"""
            if dt_value is None or isinstance(dt_value, datetime):
                return dt_value
            if not isinstance(dt_value, str):
                return dt_value
            # Try ISO format first (handles timezone-aware strings)
            try:
                return datetime.fromisoformat(dt_value.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
            # Try common SQLite formats (naive datetimes)
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(dt_value, fmt)
                except (ValueError, AttributeError):
                    continue
            return None

        # Reconstruct Orders objects with all columns including new ones
        orders = []
        for row in results:
            # Row is a Row object - access by index or use _mapping
            row_dict = dict(row._mapping) if hasattr(row, "_mapping") else {}
            # If _mapping doesn't work, access by index
            if not row_dict:
                row_dict = {all_columns[i]: row[i] for i in range(min(len(row), len(all_columns)))}

            # Convert status string to OrderStatus enum
            status_str = row_dict.get("status", "amo")
            try:
                status_enum = OrderStatus(status_str.lower())
            except (ValueError, AttributeError):
                status_upper = status_str.upper()
                status_enum = getattr(OrderStatus, status_upper, OrderStatus.AMO)

            # Build Orders object with only fields that exist
            order_kwargs = {
                "id": row_dict["id"],
                "user_id": row_dict["user_id"],
                "symbol": row_dict["symbol"],
                "side": row_dict["side"],
                "order_type": row_dict["order_type"],
                "quantity": row_dict["quantity"],
                "price": row_dict.get("price"),
                "status": status_enum,
                "avg_price": row_dict.get("avg_price"),
                "placed_at": parse_datetime(row_dict["placed_at"]),
                "filled_at": parse_datetime(row_dict.get("filled_at")),
                "closed_at": parse_datetime(row_dict.get("closed_at")),
                "orig_source": row_dict.get("orig_source"),
            }
            # Only add optional fields if they exist in the database
            if "order_id" in orders_columns:
                order_kwargs["order_id"] = row_dict.get("order_id")
            if "broker_order_id" in orders_columns:
                order_kwargs["broker_order_id"] = row_dict.get("broker_order_id")
            if "metadata" in orders_columns:
                # Handle JSON metadata - might be string or dict
                metadata_val = row_dict.get("metadata")
                if isinstance(metadata_val, str):
                    import json

                    try:
                        metadata_val = json.loads(metadata_val)
                    except:
                        metadata_val = None
                order_kwargs["order_metadata"] = metadata_val

            order = Orders(**order_kwargs)
            orders.append(order)
        return orders

    def create_amo(
        self,
        *,
        user_id: int,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None,
        order_id: str | None = None,
        broker_order_id: str | None = None,
    ) -> Orders:
        order = Orders(
            user_id=user_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status=OrderStatus.AMO,
            placed_at=ist_now(),
            order_id=order_id,
            broker_order_id=broker_order_id,
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def get_by_broker_order_id(self, user_id: int, broker_order_id: str) -> Orders | None:
        """Get order by broker-specific order ID"""
        stmt = select(Orders).where(
            Orders.user_id == user_id, Orders.broker_order_id == broker_order_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_order_id(self, user_id: int, order_id: str) -> Orders | None:
        """Get order by internal order ID"""
        stmt = select(Orders).where(Orders.user_id == user_id, Orders.order_id == order_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def bulk_create(self, orders: list[dict]) -> list[Orders]:
        """Bulk create orders (for migration)"""
        created_orders = []
        for order_data in orders:
            order = Orders(**order_data)
            self.db.add(order)
            created_orders.append(order)
        self.db.commit()
        for order in created_orders:
            self.db.refresh(order)
        return created_orders

    def update(self, order: Orders, **fields) -> Orders:
        """
        Update an order with the given fields.

        Handles detached orders by merging them into the current session.
        This is necessary when orders are loaded in different sessions or threads.

        Only updates the fields explicitly passed, avoiding accidental updates
        to datetime fields that might be strings from raw SQL queries.
        """
        # Merge order into current session if it's detached
        # This handles cases where the order was loaded in a different session
        # or passed from a different thread/context
        try:
            # Check if order is in current session by trying to access its state
            if order not in self.db:
                order = self.db.merge(order)
        except Exception:
            # If check fails, merge anyway to be safe
            order = self.db.merge(order)

        # Update only the fields explicitly passed
        # This prevents accidentally updating datetime fields that might be strings
        for k, v in fields.items():
            if hasattr(order, k) and v is not None:
                setattr(order, k, v)

        self.db.commit()
        self.db.refresh(order)
        return order

    def cancel(self, order: Orders) -> None:
        # For AMO orders, cancel means remove or mark closed without fills
        order.status = OrderStatus.CLOSED
        order.closed_at = ist_now()
        self.db.commit()
