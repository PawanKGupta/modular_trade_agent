from __future__ import annotations

import builtins
import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.infrastructure.db.models import (
    Orders,
    OrderStatus,
    Positions,
    Signals,
    SignalStatus,
    TradeMode,
)
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.fills_repository import FillsRepository
from src.infrastructure.persistence.settings_repository import SettingsRepository
from src.infrastructure.persistence.signals_repository import SignalsRepository

# Optional imports (may not be available in all environments)
try:
    from modules.kotak_neo_auto_trader.utils.trading_day_utils import (
        get_next_trading_day_close,
    )
except ImportError:
    # Fallback if module not available
    get_next_trading_day_close = None  # type: ignore

try:
    from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol
except ImportError:
    extract_base_symbol = None  # type: ignore

# Import logger for duplicate detection logging
try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class OrdersRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, order_id: int) -> Orders | None:
        return self.db.get(Orders, order_id)

    def list(  # noqa: PLR0912, PLR0915
        self,
        user_id: int,
        status: OrderStatus | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[builtins.list[Orders], int]:
        """
        List orders with optional pagination support.

        Args:
            user_id: User ID to filter orders
            status: Optional status filter
            limit: Optional limit for pagination
            offset: Offset for pagination (default: 0)

        Returns:
            Tuple of (orders list, total count)
        """
        # Always use raw SQL fallback to avoid enum validation issues
        # This ensures compatibility with database schema regardless of SQLAlchemy metadata cache

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
        # Handle updated_at as optional for backward compatibility (until migration runs)
        if "updated_at" in orders_columns:
            optional_columns.append("updated_at")
        if "order_id" in orders_columns:
            optional_columns.append("order_id")
        if "broker_order_id" in orders_columns:
            optional_columns.append("broker_order_id")
        if "metadata" in orders_columns:
            optional_columns.append("metadata")
        if "entry_type" in orders_columns:
            optional_columns.append("entry_type")
        # Order monitoring fields
        if "first_failed_at" in orders_columns:
            optional_columns.append("first_failed_at")
        if "last_retry_attempt" in orders_columns:
            optional_columns.append("last_retry_attempt")
        if "retry_count" in orders_columns:
            optional_columns.append("retry_count")
        if "reason" in orders_columns:
            optional_columns.append("reason")
        if "last_status_check" in orders_columns:
            optional_columns.append("last_status_check")
        if "execution_price" in orders_columns:
            optional_columns.append("execution_price")
        if "execution_qty" in orders_columns:
            optional_columns.append("execution_qty")
        if "execution_time" in orders_columns:
            optional_columns.append("execution_time")
        # Phase 0.1: Trade mode column
        if "trade_mode" in orders_columns:
            optional_columns.append("trade_mode")

        all_columns = base_columns + optional_columns

        # Build base WHERE clause
        where_clause = "WHERE user_id = :user_id"
        params = {"user_id": user_id}
        if status:
            where_clause += " AND status = :status"
            # Use enum value (lowercase) to match database
            params["status"] = status.value.lower()

        # Get total count before applying pagination
        # `where_clause` is built from static strings; values are bound via `params`.
        count_query = f"SELECT COUNT(*) FROM orders {where_clause}"  # noqa: S608
        total_count = self.db.execute(text(count_query), params).scalar() or 0

        # Build SELECT query with pagination.
        # Columns are derived from DB introspection; values are bound via `params`.
        query = "\n".join(
            [
                "SELECT " + ", ".join(all_columns),
                "FROM orders",
                where_clause,
                "ORDER BY placed_at DESC",
            ]
        )  # noqa: S608

        # Apply pagination if limit is provided
        if limit is not None:
            query += " LIMIT :limit OFFSET :offset"
            params["limit"] = int(limit)
            params["offset"] = max(0, int(offset))

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
                "updated_at": parse_datetime(
                    row_dict.get("updated_at") or row_dict.get("placed_at")
                ),  # Fallback to placed_at if updated_at not present (for existing records)
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
                    try:
                        metadata_val = json.loads(metadata_val)
                    except Exception:
                        metadata_val = None
                order_kwargs["order_metadata"] = metadata_val
            if "entry_type" in orders_columns:
                order_kwargs["entry_type"] = row_dict.get("entry_type")
            # Order monitoring fields
            if "first_failed_at" in orders_columns:
                order_kwargs["first_failed_at"] = parse_datetime(row_dict.get("first_failed_at"))
            if "last_retry_attempt" in orders_columns:
                order_kwargs["last_retry_attempt"] = parse_datetime(
                    row_dict.get("last_retry_attempt")
                )
            if "retry_count" in orders_columns:
                order_kwargs["retry_count"] = row_dict.get("retry_count") or 0
            if "reason" in orders_columns:
                order_kwargs["reason"] = row_dict.get("reason")
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
            if "updated_at" in orders_columns:
                order_kwargs["updated_at"] = parse_datetime(
                    row_dict.get("updated_at") or row_dict.get("placed_at")
                )
            # Phase 0.1: Add trade_mode if column exists
            if "trade_mode" in orders_columns:
                trade_mode_str = row_dict.get("trade_mode")
                if trade_mode_str:
                    try:
                        order_kwargs["trade_mode"] = TradeMode(trade_mode_str.lower())
                    except (ValueError, AttributeError):
                        # Fallback to default if invalid value
                        order_kwargs["trade_mode"] = TradeMode.PAPER
                else:
                    order_kwargs["trade_mode"] = TradeMode.PAPER

            order = Orders(**order_kwargs)
            orders.append(order)
        return orders, total_count

    def create_amo(  # noqa: PLR0912, PLR0913, PLR0915
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
        entry_type: str | None = None,
        order_metadata: dict | None = None,
        reason: str | None = None,
        trade_mode: TradeMode | None = None,
    ) -> Orders:
        # Check for existing active order to prevent duplicates
        # First check by exact symbol match (most common case - same symbol format)
        # Then check by base symbol (fallback for different formats like SALSTEEL-BE vs SALSTEEL)
        if side == "buy":
            existing_orders, _ = self.list(user_id)
            symbol_upper = symbol.upper().strip()

            for existing_order in existing_orders:
                if existing_order.side != "buy":
                    continue
                if existing_order.status not in [OrderStatus.PENDING, OrderStatus.ONGOING]:
                    continue

                existing_symbol_upper = existing_order.symbol.upper().strip()

                # Only exact match (full symbols are different instruments)
                if existing_symbol_upper == symbol_upper:
                    logger.warning(
                        "Duplicate order prevented: Active buy order already exists "
                        "with symbol '%s'. "
                        "Existing order: %s (id: %s, status: %s). Returning existing order.",
                        symbol,
                        existing_order.symbol,
                        existing_order.id,
                        existing_order.status,
                    )
                    return existing_order

        # Check for existing active SELL order by base symbol (for logging / return existing)
        if side == "sell":
            try:
                if extract_base_symbol is None:
                    raise ImportError("extract_base_symbol not available")
                existing_orders, _ = self.list(user_id)
                symbol_base = extract_base_symbol(symbol).upper().strip()

                for existing_order in existing_orders:
                    if existing_order.side != "sell":
                        continue
                    if existing_order.status not in [OrderStatus.PENDING, OrderStatus.ONGOING]:
                        continue

                    existing_symbol_base = (
                        extract_base_symbol(existing_order.symbol).upper().strip()
                    )

                    # Check by base symbol (e.g., "INDIAGLYCO" matches "INDIAGLYCO-EQ"
                    # and "INDIAGLYCO-BE")
                    if existing_symbol_base == symbol_base:
                        logger.warning(
                            "Duplicate sell order prevented: Active sell order already exists "
                            "for base symbol '%s'. "
                            "Existing order: %s (id: %s, status: %s). Requested order: %s. "
                            "Returning existing order.",
                            symbol_base,
                            existing_order.symbol,
                            existing_order.id,
                            existing_order.status,
                            symbol,
                        )
                        return existing_order
            except Exception as e:
                # Non-critical: if symbol extraction fails, log and continue
                # Better to place order than to block due to utility function failure
                logger.debug("Could not check for duplicate sell orders: %s", e)

        # Phase 0.1: Get trade_mode from UserSettings if not provided
        if trade_mode is None:
            settings_repo = SettingsRepository(self.db)
            user_settings = settings_repo.get_by_user_id(user_id)
            if user_settings and user_settings.trade_mode:
                trade_mode = user_settings.trade_mode
            else:
                # Default to PAPER if no settings exist
                trade_mode = TradeMode.PAPER

        now = ist_now()
        # Compute base_symbol for DB-level uniqueness and normalization
        try:
            if extract_base_symbol is None:
                raise ImportError("extract_base_symbol not available")
            base_symbol_val = extract_base_symbol(symbol).upper().strip()
        except Exception:
            base_symbol_val = symbol.upper().split("-")[0].strip()

        # For sell: use INSERT ... ON CONFLICT to cancel any row in uq_orders_user_base_symbol_active
        # that we cannot see (e.g. different transaction/snapshot). When we conflict, DO UPDATE
        # sets that row to cancelled. If we don't conflict we insert a probe row — delete it after.
        if side == "sell":
            try:
                now_ist = now
                trade_mode_val = (
                    trade_mode.value if hasattr(trade_mode, "value") else (trade_mode or "paper")
                )
                probe_id = f"__cancel_probe_{order_id}__"
                # index_predicate must match partial index: status IN ('pending','ongoing') AND side = 'sell'
                # Include retry_count (NOT NULL, default 0) to satisfy table constraints.
                stmt_upsert = text(
                    """
                    INSERT INTO orders (
                        user_id, symbol, base_symbol, side, order_type, quantity, price,
                        status, placed_at, updated_at, order_id, broker_order_id, reason, trade_mode, retry_count
                    ) VALUES (
                        :user_id, :symbol, :base_symbol, 'sell', :order_type, 0, 0,
                        'pending', :placed_at, :updated_at, :probe_id, :probe_id,
                        'Probe to cancel existing', :trade_mode, 0
                    )
                    ON CONFLICT (user_id, base_symbol) WHERE (status IN ('pending', 'ongoing') AND side = 'sell')
                    DO UPDATE SET
                        status = 'cancelled',
                        closed_at = EXCLUDED.placed_at,
                        updated_at = EXCLUDED.updated_at,
                        reason = 'Replaced by new sell order (ON CONFLICT)'
                    """
                )
                self.db.execute(
                    stmt_upsert,
                    {
                        "user_id": user_id,
                        "symbol": symbol,
                        "base_symbol": base_symbol_val,
                        "order_type": order_type,
                        "placed_at": now_ist,
                        "updated_at": now_ist,
                        "probe_id": probe_id,
                        "trade_mode": trade_mode_val,
                    },
                )
                self.db.flush()
                # If probe did not conflict, we inserted a dummy row; remove it so our real INSERT can succeed.
                del_probe = text(
                    "DELETE FROM orders WHERE user_id = :user_id AND base_symbol = :base_symbol AND order_id = :probe_id"
                )
                self.db.execute(
                    del_probe,
                    {"user_id": user_id, "base_symbol": base_symbol_val, "probe_id": probe_id},
                )
                self.db.flush()
                logger.debug(
                    "[create_amo] ON CONFLICT probe ran for (user_id=%s, base_symbol=%s)",
                    user_id,
                    base_symbol_val,
                )
            except Exception as probe_e:
                logger.warning("[create_amo] ON CONFLICT probe failed: %s", probe_e)
                self.db.rollback()

        logger.debug(
            "[create_amo] Inserting order (user_id=%s, symbol=%s, base_symbol=%s, side=%s, order_id=%s)",
            user_id,
            symbol,
            base_symbol_val,
            side,
            order_id,
        )
        order = Orders(
            user_id=user_id,
            symbol=symbol,  # Keep actual symbol format from broker (e.g., SALSTEEL-BE)
            base_symbol=base_symbol_val,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status=OrderStatus.PENDING,  # Changed from AMO
            placed_at=now,
            updated_at=now,  # Set initial updated_at same as placed_at
            order_id=order_id,
            entry_type=entry_type,
            order_metadata=order_metadata,
            broker_order_id=broker_order_id,
            reason=reason or "Order placed - waiting for market open",
            trade_mode=trade_mode,  # Phase 0.1: Add trade_mode
        )
        self.db.add(order)
        try:
            self.db.commit()
            self.db.refresh(order)
            return order
        except IntegrityError as ie:
            # Likely violated uq_orders_user_base_symbol_active (active sell per user+base_symbol).
            self.db.rollback()
            logger.warning(
                "[create_amo] IntegrityError on insert (user_id=%s, base_symbol=%s): %s — retrying with ON CONFLICT probe",
                user_id,
                base_symbol_val,
                ie,
            )
            if side == "sell":
                try:
                    # Retry: run ON CONFLICT probe again to cancel blocking row, then insert.
                    now_ist = ist_now()
                    trade_mode_val = (
                        trade_mode.value
                        if hasattr(trade_mode, "value")
                        else (trade_mode or "paper")
                    )
                    probe_id = f"__cancel_probe_{order_id}__"
                    stmt_upsert = text(
                        """
                        INSERT INTO orders (
                            user_id, symbol, base_symbol, side, order_type, quantity, price,
                            status, placed_at, updated_at, order_id, broker_order_id, reason, trade_mode, retry_count
                        ) VALUES (
                            :user_id, :symbol, :base_symbol, 'sell', :order_type, 0, 0,
                            'pending', :placed_at, :updated_at, :probe_id, :probe_id,
                            'Probe to cancel existing', :trade_mode, 0
                        )
                        ON CONFLICT (user_id, base_symbol) WHERE (status IN ('pending', 'ongoing') AND side = 'sell')
                        DO UPDATE SET
                            status = 'cancelled',
                            closed_at = EXCLUDED.placed_at,
                            updated_at = EXCLUDED.updated_at,
                            reason = 'Replaced by new sell order (ON CONFLICT)'
                        """
                    )
                    self.db.execute(
                        stmt_upsert,
                        {
                            "user_id": user_id,
                            "symbol": symbol,
                            "base_symbol": base_symbol_val,
                            "order_type": order_type,
                            "placed_at": now_ist,
                            "updated_at": now_ist,
                            "probe_id": probe_id,
                            "trade_mode": trade_mode_val,
                        },
                    )
                    self.db.flush()
                    del_probe = text(
                        "DELETE FROM orders WHERE user_id = :user_id AND base_symbol = :base_symbol AND order_id = :probe_id"
                    )
                    self.db.execute(
                        del_probe,
                        {"user_id": user_id, "base_symbol": base_symbol_val, "probe_id": probe_id},
                    )
                    self.db.flush()
                    order = Orders(
                        user_id=user_id,
                        symbol=symbol,
                        base_symbol=base_symbol_val,
                        side=side,
                        order_type=order_type,
                        quantity=quantity,
                        price=price,
                        status=OrderStatus.PENDING,
                        placed_at=ist_now(),
                        updated_at=ist_now(),
                        order_id=order_id,
                        entry_type=entry_type,
                        order_metadata=order_metadata,
                        broker_order_id=broker_order_id,
                        reason=reason or "Order placed - waiting for market open",
                        trade_mode=trade_mode or TradeMode.PAPER,
                    )
                    self.db.add(order)
                    self.db.commit()
                    self.db.refresh(order)
                    return order
                except IntegrityError:
                    self.db.rollback()
            stmt = (
                select(Orders)
                .where(
                    Orders.user_id == user_id,
                    Orders.base_symbol == base_symbol_val,
                    Orders.side == "sell",
                    Orders.status.in_([OrderStatus.PENDING, OrderStatus.ONGOING]),
                )
                .limit(1)
            )
            existing = self.db.execute(stmt).scalar_one_or_none()
            if existing:
                logger.warning(
                    "Duplicate sell prevented by DB constraint: returning existing order %s",
                    existing.id,
                )
                return existing
            raise

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

    def has_successful_buy_order(self, user_id: int, symbol: str) -> bool:
        """
        Check if user has a successful buy order for a symbol.

        A successful order is one that was executed:
        - side = 'buy'
        - status in (ONGOING, CLOSED) - meaning it was executed

        Returns:
            True if user has a successful buy order, False otherwise
        """
        stmt = (
            select(Orders)
            .where(
                Orders.user_id == user_id,
                Orders.symbol == symbol,
                Orders.side == "buy",
                Orders.status.in_([OrderStatus.ONGOING, OrderStatus.CLOSED]),
            )
            .limit(1)
        )
        result = self.db.execute(stmt).scalar_one_or_none()
        return result is not None

    def has_active_buy_order_by_base_symbol(
        self, user_id: int, symbol: str, statuses: list[OrderStatus] | None = None
    ) -> bool:
        """
        Check if user has an active buy order for a symbol (comparing by base symbol).

        This prevents duplicate orders when same stock is represented with different
        symbol formats (e.g., SALSTEEL-BE vs SALSTEEL).

        Args:
            user_id: User ID
            symbol: Symbol to check (can be SALSTEEL-BE, SALSTEEL, etc.)
            statuses: List of statuses to check (default: PENDING, ONGOING)

        Returns:
            True if active buy order exists for the base symbol, False otherwise
        """
        if statuses is None:
            statuses = [OrderStatus.PENDING, OrderStatus.ONGOING]

        # Extract base symbol (remove segment suffixes)
        base_symbol = symbol.upper().split("-")[0].strip()

        # Get all buy orders for user
        all_orders, _ = self.list(user_id)

        for order in all_orders:
            if order.side != "buy" or order.status not in statuses:
                continue

            # Extract base symbol from existing order
            order_base_symbol = order.symbol.upper().split("-")[0].strip()

            # Compare base symbols
            if order_base_symbol == base_symbol:
                return True

        return False

    def has_ongoing_buy_order(self, user_id: int, symbol: str) -> bool:
        """
        Check if user has an open position for a symbol (user still holds the stock).

        Uses Positions table (closed_at IS NULL) as the source of truth for "position
        ongoing". Order status is no longer used for this; filled orders are CLOSED.

        Returns:
            True if user has an open position for the symbol, False otherwise
        """
        stmt = (
            select(Positions)
            .where(
                Positions.user_id == user_id,
                Positions.symbol == symbol,
                Positions.closed_at.is_(None),
            )
            .limit(1)
        )
        result = self.db.execute(stmt).scalar_one_or_none()
        return result is not None

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

    def update(self, order: Orders, auto_commit: bool = True, **fields) -> Orders:
        """
        Update an order with the given fields.

        Handles detached orders by merging them into the current session.
        This is necessary when orders are loaded in different sessions or threads.

        Only updates the fields explicitly passed, avoiding accidental updates
        to datetime fields that might be strings from raw SQL queries.

        Args:
            order: Order to update
            auto_commit: If True, commit immediately. If False, caller handles commit
                (for transactions).
            **fields: Fields to update on the order
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

        # Always update updated_at timestamp when order is modified
        order.updated_at = ist_now()

        if auto_commit:
            self.db.commit()
            self.db.refresh(order)  # Only refresh after commit to get database state
        # When auto_commit=False, don't refresh - changes are only in session
        return order

    def cancel(self, order: Orders, auto_commit: bool = True) -> None:
        """Cancel an order (mark as cancelled without fills)

        Args:
            order: Order to cancel
            auto_commit: If True, commit immediately. If False, caller handles commit
                (for transactions).
        """
        # Mark as cancelled (not closed - closed is for successfully executed + sold trades)
        order.status = OrderStatus.CANCELLED
        order.closed_at = ist_now()
        if auto_commit:
            self.db.commit()

    def mark_failed(
        self,
        order: Orders,
        failure_reason: str,
        retry_pending: bool = False,  # Keep for backward compatibility, but not used
    ) -> Orders:
        """Mark an order as failed with reason

        Note: retry_pending parameter is ignored - all FAILED orders are retriable
        until expiry. Use get_retriable_failed_orders() to filter by expiry.
        """
        order.status = OrderStatus.FAILED  # Always FAILED (no RETRY_PENDING)
        order.reason = failure_reason  # Use unified reason field
        if not order.first_failed_at:
            order.first_failed_at = ist_now()
        order.last_retry_attempt = ist_now()
        # Increment retry_count for monitoring (no max retry limit enforced)
        order.retry_count = (order.retry_count or 0) + 1
        # Note: retry_pending parameter is ignored - all FAILED orders are retriable

        # Mark signal as FAILED if it's a buy order
        if order.side == "buy":
            self._mark_signal_as_failed(order)

        return self.update(order)

    def mark_rejected(self, order: Orders, rejection_reason: str) -> Orders:
        """Mark an order as rejected by broker

        Note: REJECTED status is now mapped to FAILED with reason field.
        Stores detailed rejection reason in rejection_reason field for analysis.
        """
        order.status = OrderStatus.FAILED  # Changed from REJECTED
        order.reason = f"Broker rejected: {rejection_reason}"  # Use unified reason field
        order.rejection_reason = rejection_reason  # Store detailed reason (Phase 1)
        order.last_status_check = ist_now()
        # Set first_failed_at if not already set (for retry logic)
        if not order.first_failed_at:
            order.first_failed_at = ist_now()

        # Mark signal as FAILED if it's a buy order
        if order.side == "buy":
            self._mark_signal_as_failed(order)

        return self.update(order)

    def mark_cancelled(
        self,
        order: Orders,
        cancelled_reason: str | None = None,
        auto_commit: bool = True,
    ) -> Orders:
        """Mark an order as cancelled"""
        order.status = OrderStatus.CANCELLED
        order.reason = cancelled_reason or "Cancelled"  # Use unified reason field
        order.closed_at = ist_now()
        order.last_status_check = ist_now()

        # Mark signal as FAILED if it's a buy order
        if order.side == "buy":
            self._mark_signal_as_failed(order)

        return self.update(order, auto_commit=auto_commit)

    def cancel_active_sell_for_symbol(
        self,
        user_id: int,
        symbol: str,
        reason: str = "Replaced by new sell order",
        auto_commit: bool = True,
    ) -> Orders | None:
        """
        Find all active (pending/ongoing) sell orders for user+base_symbol and mark them
        cancelled. Use before inserting a new sell to satisfy uq_orders_user_base_symbol_active.
        When auto_commit=False, caller must flush/commit so the UPDATE is visible before INSERT.
        Returns the first order cancelled, or None if none found.
        """
        try:
            if extract_base_symbol is None:
                raise ImportError("extract_base_symbol not available")
            base_symbol_val = extract_base_symbol(symbol).upper().strip()
        except Exception:
            base_symbol_val = symbol.upper().split("-")[0].strip()

        first_cancelled = None
        cancel_count = 0
        while True:
            # Match base_symbol case-insensitively so we find rows even if DB has different case
            stmt = (
                select(Orders)
                .where(
                    Orders.user_id == user_id,
                    func.upper(Orders.base_symbol) == base_symbol_val,
                    Orders.side == "sell",
                    Orders.status.in_([OrderStatus.PENDING, OrderStatus.ONGOING]),
                )
                .limit(1)
            )
            order = self.db.execute(stmt).scalar_one_or_none()
            if not order:
                break
            if first_cancelled is None:
                first_cancelled = order
            logger.info(
                "[cancel_active_sell_for_symbol] Cancelling order id=%s (user_id=%s, base_symbol=%s, symbol=%s, status=%s)",
                order.id,
                user_id,
                getattr(order, "base_symbol", None),
                getattr(order, "symbol", None),
                getattr(order, "status", None),
            )
            self.mark_cancelled(order, reason, auto_commit=auto_commit)
            cancel_count += 1
            # Flush so the UPDATE is visible before next SELECT and before caller's create_amo
            if not auto_commit:
                self.db.flush()
        if cancel_count == 0:
            logger.info(
                "[cancel_active_sell_for_symbol] No active sell found for (user_id=%s, symbol=%s, base_symbol_val=%s)",
                user_id,
                symbol,
                base_symbol_val,
            )
        else:
            logger.info(
                "[cancel_active_sell_for_symbol] Cancelled %s order(s) for (user_id=%s, base_symbol=%s)",
                cancel_count,
                user_id,
                base_symbol_val,
            )
        return first_cancelled

    def mark_executed(  # noqa: PLR0913
        self,
        order: Orders,
        execution_price: float,
        execution_qty: float | None = None,
        charges: float = 0.0,
        broker_fill_id: str | None = None,
        auto_commit: bool = True,
        create_fill_record: bool = True,
    ) -> Orders:
        """Mark an order as executed with execution details

        Supports partial fills: each call creates a Fill record, then aggregates
        all fills to update order.execution_price and order.execution_qty.

        Args:
            order: Order to mark as executed
            execution_price: Price at which this fill executed
            execution_qty: Quantity executed in this fill (defaults to order quantity)
            charges: Brokerage + taxes for this fill
            broker_fill_id: Broker's unique fill ID for deduplication
            auto_commit: If True, commit immediately. If False, caller handles commit
                (for transactions).
            create_fill_record: If True, create Fill record (default). Set False for
                legacy single-fill behavior.
        """
        fill_qty = execution_qty or order.quantity

        # Create Fill record for this execution
        if create_fill_record:
            try:
                fills_repo = FillsRepository(self.db)

                # Check for duplicate fill by broker_fill_id
                if broker_fill_id and fills_repo.get_by_broker_fill_id(broker_fill_id):
                    logger.info(f"Duplicate fill {broker_fill_id} for order {order.id}, skipping")
                    return order

                # Create fill record
                fills_repo.create(
                    order_id=order.id,
                    user_id=order.user_id,
                    quantity=fill_qty,
                    price=execution_price,
                    charges=charges,
                    broker_fill_id=broker_fill_id,
                    auto_commit=False,  # Will commit with order update
                )

                # Aggregate all fills to get total execution stats
                fill_summary = fills_repo.get_fill_summary(order.id)
                order.execution_qty = fill_summary["total_qty"]
                order.execution_price = fill_summary["avg_price"]  # Weighted average

            except Exception as e:
                # Fall back to legacy behavior if fills table doesn't exist or other error
                logger.debug(
                    f"Fill record creation failed for order {order.id}, using legacy behavior: {e}"
                )
                order.execution_price = execution_price
                order.execution_qty = fill_qty
        else:
            # Legacy behavior: single fill, no Fill record
            order.execution_price = execution_price
            order.execution_qty = fill_qty

        # Update order status and timestamps.
        # Mark as CLOSED when filled so (user_id, base_symbol) is freed for the unique
        # index uq_orders_user_base_symbol_active; "position ongoing" is tracked in Positions.
        order.status = OrderStatus.CLOSED
        order.execution_time = ist_now()
        order.filled_at = ist_now()
        order.last_status_check = ist_now()
        order.reason = f"Order executed at Rs {order.execution_price:.2f}"

        updated_order = self.update(order, auto_commit=auto_commit)

        # Phase 2.1: Late fill detection - check if signal is EXPIRED when order fills
        if order.side == "buy":
            self._mark_signal_as_traded_with_late_fill_detection(order)

        return updated_order

    def update_status_check(self, order: Orders) -> Orders:
        """Update the last status check timestamp"""
        order.last_status_check = ist_now()
        return self.update(order)

    def _mark_signal_as_traded_with_late_fill_detection(self, order: Orders) -> None:
        """
        Helper method to mark signal as TRADED when order executes.
        Detects late fills (when signal is EXPIRED) and marks with appropriate reason.

        Only marks if:
        - Order is a buy order
        - Signal exists for this symbol

        Args:
            order: The order that was executed
        """
        if order.side != "buy":
            return  # Only handle buy orders

        try:
            signals_repo = SignalsRepository(self.db, user_id=order.user_id)

            # Extract base symbol (remove -EQ, -BE suffixes)
            base_symbol = order.symbol.split("-")[0] if "-" in order.symbol else order.symbol
            base_symbol = base_symbol.upper()

            # Find the latest signal for this symbol
            signal = self.db.execute(
                select(Signals)
                .where(Signals.symbol == base_symbol)
                .order_by(Signals.ts.desc())
                .limit(1)
            ).scalar_one_or_none()

            if not signal:
                return  # No signal found

            # Check current signal status (base status or user status)
            user_status = signals_repo.get_user_signal_status(signal.id, order.user_id)

            # If no user status override, use base signal status
            if user_status is None:
                user_status = signal.status

            # Determine if this is a late fill (signal is EXPIRED)
            is_late_fill = user_status == SignalStatus.EXPIRED

            # Mark signal as TRADED with appropriate reason
            reason = "late_fill" if is_late_fill else "order_placed"

            # Try multiple symbol variants to handle stored symbols with/without suffixes
            candidates = [base_symbol]
            upper_symbol = order.symbol.upper()
            if upper_symbol not in candidates:
                candidates.append(upper_symbol)
            # Add NSE-style ticker if missing
            ticker_variant = f"{base_symbol}.NS" if not base_symbol.endswith(".NS") else base_symbol
            if ticker_variant not in candidates:
                candidates.append(ticker_variant)

            marked = False
            for candidate in candidates:
                try:
                    if signals_repo.mark_as_traded(candidate, user_id=order.user_id, reason=reason):
                        if is_late_fill:
                            logger.info(
                                f"Late fill detected: Order {order.id} executed for EXPIRED signal "
                                f"{candidate} (user {order.user_id})"
                            )
                        marked = True
                        break
                except Exception as inner_mark_error:
                    logger.debug(
                        f"Mark-as-traded attempt failed for {candidate}: {inner_mark_error}"
                    )

            if not marked:
                logger.debug(
                    f"Could not mark signal as TRADED for any variant: {candidates} "
                    f"(order {order.id})"
                )

        except Exception as e:
            # Don't fail order update if signal marking fails
            logger.warning(f"Failed to mark signal as TRADED for order {order.id}: {e}")

    def _mark_signal_as_failed(self, order: Orders) -> None:
        """
        Helper method to mark signal as FAILED when order fails.

        Only marks if:
        - Order is a buy order
        - Signal exists and is TRADED for this user
        - All buy orders for this symbol have failed (edge case handling)

        Args:
            order: The order that failed
        """
        if order.side != "buy":
            return  # Only handle buy orders

        try:
            signals_repo = SignalsRepository(self.db, user_id=order.user_id)

            # Extract base symbol (remove -EQ, -BE suffixes)
            base_symbol = order.symbol.split("-")[0] if "-" in order.symbol else order.symbol
            base_symbol = base_symbol.upper()

            # Find the latest signal for this symbol
            signal = self.db.execute(
                select(Signals)
                .where(Signals.symbol == base_symbol)
                .order_by(Signals.ts.desc())
                .limit(1)
            ).scalar_one_or_none()

            if not signal:
                return  # No signal found

            # Check if user has TRADED status for this signal
            user_status = signals_repo.get_user_signal_status(signal.id, order.user_id)
            if user_status != SignalStatus.TRADED:
                return  # Signal is not TRADED, don't mark as FAILED

            # Edge case: Check if there are other successful orders for this symbol
            # Only mark as FAILED if ALL buy orders have failed
            other_orders, _ = self.list(order.user_id)
            symbol_orders = [
                o
                for o in other_orders
                if o.side == "buy"
                and (o.symbol.split("-")[0] if "-" in o.symbol else o.symbol).upper() == base_symbol
                and o.id != order.id  # Exclude current order
            ]

            # Check if any other order is successful (ONGOING or PENDING)
            has_successful_order = any(
                o.status in [OrderStatus.ONGOING, OrderStatus.PENDING] for o in symbol_orders
            )

            if has_successful_order:
                # Another order is still processing, keep as TRADED
                return

            # All orders failed or no other orders - mark signal as FAILED
            signals_repo.mark_as_failed(signal.id, order.user_id)

        except Exception as e:
            # Don't fail order update if signal marking fails
            logger.warning(f"Failed to mark signal as FAILED for order {order.id}: {e}")

    def get_pending_amo_orders(self, user_id: int) -> list[Orders]:
        """Get all pending AMO buy orders that need status checking

        Note: Previously returned AMO + PENDING_EXECUTION, now returns PENDING only.
        CRITICAL: Only returns buy orders to prevent sell orders from being tracked as buy orders.
        """
        orders, _ = self.list(
            user_id,
            status=OrderStatus.PENDING,  # Merged: AMO + PENDING_EXECUTION
        )
        # CRITICAL FIX: Filter to only buy orders
        # AMO orders are always buy orders, but we need to prevent sell orders
        # with PENDING status from being incorrectly loaded as buy orders
        return [o for o in orders if o.side == "buy"]

    def get_failed_orders(self, user_id: int) -> list[Orders]:
        """Get all failed orders

        Note: Previously returned RETRY_PENDING + FAILED, now returns FAILED only.
        For retriable orders (with expiry filter), use get_retriable_failed_orders().
        """
        orders, _ = self.list(
            user_id,
            status=OrderStatus.FAILED,  # Merged: FAILED + RETRY_PENDING + REJECTED
        )
        return orders

    def get_retriable_failed_orders(self, user_id: int) -> list[Orders]:
        """
        Get FAILED orders that are eligible for retry.
        Applies expiry filter - excludes expired orders.

        Orders expire at next trading day market close (3:30 PM IST).
        Expired orders are automatically marked as CANCELLED.

        Returns:
            List of FAILED orders that haven't expired yet
        """
        if get_next_trading_day_close is None:
            # Module not available, return all failed orders without expiry filter
            all_failed, _ = self.list(user_id, status=OrderStatus.FAILED)
            return all_failed

        # Get all FAILED orders
        all_failed, _ = self.list(user_id, status=OrderStatus.FAILED)

        # Apply expiry filter
        retriable_orders = []
        now = ist_now()

        for order in all_failed:
            if not order.first_failed_at:
                # No expiry date - include (shouldn't happen, but handle gracefully)
                retriable_orders.append(order)
                continue

            # Calculate next trading day market close
            next_trading_day_close = get_next_trading_day_close(order.first_failed_at)

            # Check if expired
            if now > next_trading_day_close:
                # Order expired - mark as CANCELLED
                self.mark_cancelled(
                    order,
                    f"Order expired - past next trading day market close "
                    f"({next_trading_day_close.strftime('%Y-%m-%d %H:%M')})",
                )
                continue

            # Order hasn't expired - eligible for retry
            retriable_orders.append(order)

        return retriable_orders

    def get_order_status_distribution(self, user_id: int) -> dict[str, int]:
        """
        Get distribution of orders by status for monitoring metrics.

        Phase 11: Monitoring metrics for order status distribution.

        Args:
            user_id: User ID to filter orders

        Returns:
            Dict mapping status to count: {'amo': 5, 'ongoing': 10, 'closed': 20, ...}
        """
        # Query to count orders by status
        query = text(
            """
            SELECT status, COUNT(*) as count
            FROM orders
            WHERE user_id = :user_id
            GROUP BY status
            ORDER BY count DESC
        """
        )

        results = self.db.execute(query, {"user_id": user_id}).fetchall()

        # Convert to dict
        distribution = {}
        for row in results:
            status = row[0]  # status value
            count = row[1]  # count
            distribution[status] = count

        return distribution

    def get_order_statistics(self, user_id: int) -> dict[str, Any]:
        """
        Get comprehensive order statistics for monitoring.

        Phase 11: Monitoring metrics for order management.

        Args:
            user_id: User ID to filter orders

        Returns:
            Dict with statistics:
            {
                'total_orders': int,
                'status_distribution': dict,
                'pending_execution': int,
                'failed_orders': int,
                'retry_pending': int,
                'rejected_orders': int,
                'cancelled_orders': int,
                'executed_orders': int,
                'closed_orders': int,
            }
        """
        # Get total count
        total_query = text(
            """
            SELECT COUNT(*) as total
            FROM orders
            WHERE user_id = :user_id
        """
        )
        total_result = self.db.execute(total_query, {"user_id": user_id}).fetchone()
        total_orders = total_result[0] if total_result else 0

        # Get status distribution
        status_distribution = self.get_order_status_distribution(user_id)

        # Get specific counts
        stats = {
            "total_orders": total_orders,
            "status_distribution": status_distribution,
            "pending_execution": status_distribution.get("pending_execution", 0),
            "failed_orders": status_distribution.get("failed", 0),
            "retry_pending": status_distribution.get("retry_pending", 0),
            "rejected_orders": status_distribution.get("rejected", 0),
            "cancelled_orders": status_distribution.get("cancelled", 0),
            "executed_orders": status_distribution.get("closed", 0),  # Executed orders are CLOSED
            "closed_orders": status_distribution.get("closed", 0),
            "amo_orders": status_distribution.get("amo", 0),
        }

        return stats
