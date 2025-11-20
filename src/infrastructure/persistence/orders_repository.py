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
        # Order monitoring fields
        if "failure_reason" in orders_columns:
            optional_columns.append("failure_reason")
        if "first_failed_at" in orders_columns:
            optional_columns.append("first_failed_at")
        if "last_retry_attempt" in orders_columns:
            optional_columns.append("last_retry_attempt")
        if "retry_count" in orders_columns:
            optional_columns.append("retry_count")
        if "rejection_reason" in orders_columns:
            optional_columns.append("rejection_reason")
        if "cancelled_reason" in orders_columns:
            optional_columns.append("cancelled_reason")
        if "last_status_check" in orders_columns:
            optional_columns.append("last_status_check")
        if "execution_price" in orders_columns:
            optional_columns.append("execution_price")
        if "execution_qty" in orders_columns:
            optional_columns.append("execution_qty")
        if "execution_time" in orders_columns:
            optional_columns.append("execution_time")

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
                    except Exception:
                        metadata_val = None
                order_kwargs["order_metadata"] = metadata_val
            # Order monitoring fields
            if "failure_reason" in orders_columns:
                order_kwargs["failure_reason"] = row_dict.get("failure_reason")
            if "first_failed_at" in orders_columns:
                order_kwargs["first_failed_at"] = parse_datetime(row_dict.get("first_failed_at"))
            if "last_retry_attempt" in orders_columns:
                order_kwargs["last_retry_attempt"] = parse_datetime(
                    row_dict.get("last_retry_attempt")
                )
            if "retry_count" in orders_columns:
                order_kwargs["retry_count"] = row_dict.get("retry_count") or 0
            if "rejection_reason" in orders_columns:
                order_kwargs["rejection_reason"] = row_dict.get("rejection_reason")
            if "cancelled_reason" in orders_columns:
                order_kwargs["cancelled_reason"] = row_dict.get("cancelled_reason")
            if "last_status_check" in orders_columns:
                order_kwargs["last_status_check"] = parse_datetime(
                    row_dict.get("last_status_check")
                )
            if "execution_price" in orders_columns:
                order_kwargs["execution_price"] = row_dict.get("execution_price")
            if "execution_qty" in orders_columns:
                order_kwargs["execution_qty"] = row_dict.get("execution_qty")
            if "execution_time" in orders_columns:
                order_kwargs["execution_time"] = parse_datetime(row_dict.get("execution_time"))

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

    def mark_failed(
        self,
        order: Orders,
        failure_reason: str,
        retry_pending: bool = False,
    ) -> Orders:
        """Mark an order as failed with reason"""
        order.status = OrderStatus.RETRY_PENDING if retry_pending else OrderStatus.FAILED
        order.failure_reason = failure_reason
        if not order.first_failed_at:
            order.first_failed_at = ist_now()
        order.last_retry_attempt = ist_now()
        if retry_pending:
            order.retry_count = (order.retry_count or 0) + 1
        return self.update(order)

    def mark_rejected(self, order: Orders, rejection_reason: str) -> Orders:
        """Mark an order as rejected by broker"""
        order.status = OrderStatus.REJECTED
        order.rejection_reason = rejection_reason
        order.last_status_check = ist_now()
        return self.update(order)

    def mark_cancelled(self, order: Orders, cancelled_reason: str | None = None) -> Orders:
        """Mark an order as cancelled"""
        order.status = OrderStatus.CLOSED
        order.cancelled_reason = cancelled_reason or "Cancelled"
        order.closed_at = ist_now()
        order.last_status_check = ist_now()
        return self.update(order)

    def mark_executed(
        self,
        order: Orders,
        execution_price: float,
        execution_qty: float | None = None,
    ) -> Orders:
        """Mark an order as executed with execution details"""
        order.status = OrderStatus.ONGOING
        order.execution_price = execution_price
        order.execution_qty = execution_qty or order.quantity
        order.execution_time = ist_now()
        order.filled_at = ist_now()
        order.last_status_check = ist_now()
        return self.update(order)

    def update_status_check(self, order: Orders) -> Orders:
        """Update the last status check timestamp"""
        order.last_status_check = ist_now()
        return self.update(order)

    def get_pending_amo_orders(self, user_id: int) -> list[Orders]:
        """Get all pending AMO buy orders that need status checking"""
        return self.list(
            user_id,
            status=OrderStatus.AMO,
        ) + self.list(
            user_id,
            status=OrderStatus.PENDING_EXECUTION,
        )

    def get_failed_orders(self, user_id: int) -> list[Orders]:
        """Get all failed orders that are retryable"""
        return self.list(
            user_id,
            status=OrderStatus.RETRY_PENDING,
        ) + self.list(
            user_id,
            status=OrderStatus.FAILED,
        )
