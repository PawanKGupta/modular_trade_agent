"""Repository for Targets management (Phase 0.4)"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Targets
from src.infrastructure.db.timezone_utils import ist_now

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class TargetsRepository:
    """Repository for managing sell order targets"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, target: Targets) -> Targets:
        """Create a new target"""
        self.db.add(target)
        self.db.commit()
        self.db.refresh(target)
        return target

    def get_active_by_user(self, user_id: int) -> list[Targets]:
        """Get all active targets for a user"""
        stmt = (
            select(Targets)
            .where(Targets.user_id == user_id, Targets.is_active == True)  # noqa: E712
            .order_by(Targets.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_position(self, position_id: int) -> Targets | None:
        """Get target for a specific position"""
        stmt = select(Targets).where(
            Targets.position_id == position_id, Targets.is_active == True  # noqa: E712
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_symbol(self, user_id: int, symbol: str, active_only: bool = True) -> Targets | None:
        """Get target for a specific symbol"""
        stmt = select(Targets).where(Targets.user_id == user_id, Targets.symbol == symbol)
        if active_only:
            stmt = stmt.where(Targets.is_active == True)  # noqa: E712
        stmt = stmt.order_by(Targets.created_at.desc()).limit(1)
        return self.db.execute(stmt).scalar_one_or_none()

    def update_target_price(self, target_id: int, new_price: float) -> Targets | None:
        """Update target price for a target"""
        target = self.db.get(Targets, target_id)
        if not target:
            return None

        target.target_price = new_price
        target.updated_at = ist_now()
        self.db.commit()
        self.db.refresh(target)
        return target

    def mark_achieved(self, target_id: int, achieved_at: datetime | None = None) -> Targets | None:
        """Mark a target as achieved"""
        target = self.db.get(Targets, target_id)
        if not target:
            return None

        target.is_active = False
        target.achieved_at = achieved_at or ist_now()
        target.updated_at = ist_now()
        self.db.commit()
        self.db.refresh(target)
        return target

    def deactivate(self, target_id: int) -> Targets | None:
        """Deactivate a target (without marking as achieved)"""
        target = self.db.get(Targets, target_id)
        if not target:
            return None

        target.is_active = False
        target.updated_at = ist_now()
        self.db.commit()
        self.db.refresh(target)
        return target

    def upsert_by_symbol(
        self,
        user_id: int,
        symbol: str,
        target_data: dict,
        trade_mode,
    ) -> Targets:
        """
        Upsert (insert or update) a target by symbol.

        Args:
            user_id: User ID
            symbol: Trading symbol
            target_data: Dictionary with target fields:
                - target_price, entry_price, quantity
                - position_id (optional)
                - current_price (optional)
                - distance_to_target (optional)
                - target_type (default: 'ema9')
            trade_mode: TradeMode enum value

        Returns:
            Created or updated Targets
        """
        # Check if active target exists for this symbol
        existing = self.get_by_symbol(user_id, symbol, active_only=True)

        if existing:
            # Update existing target
            existing.target_price = target_data.get("target_price", existing.target_price)
            existing.entry_price = target_data.get("entry_price", existing.entry_price)
            existing.quantity = target_data.get("quantity", existing.quantity)
            if "position_id" in target_data:
                existing.position_id = target_data["position_id"]
            if "current_price" in target_data:
                existing.current_price = target_data["current_price"]
            if "distance_to_target" in target_data:
                existing.distance_to_target = target_data["distance_to_target"]
            if "distance_to_target_absolute" in target_data:
                existing.distance_to_target_absolute = target_data["distance_to_target_absolute"]
            existing.updated_at = ist_now()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            # Create new target
            target = Targets(
                user_id=user_id,
                symbol=symbol,
                position_id=target_data.get("position_id"),
                target_price=target_data.get("target_price", 0.0),
                entry_price=target_data.get("entry_price", 0.0),
                current_price=target_data.get("current_price"),
                quantity=target_data.get("quantity", 0.0),
                distance_to_target=target_data.get("distance_to_target"),
                distance_to_target_absolute=target_data.get("distance_to_target_absolute"),
                target_type=target_data.get("target_type", "ema9"),
                is_active=True,
                trade_mode=trade_mode,
                created_at=ist_now(),
                updated_at=ist_now(),
            )
            return self.create(target)

