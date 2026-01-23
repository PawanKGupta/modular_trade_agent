"""Repository for AnalyticsCache management (Phase 0.8)"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select, and_, delete
from sqlalchemy.orm import Session

from src.infrastructure.db.models import AnalyticsCache
from src.infrastructure.db.timezone_utils import ist_now

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class AnalyticsCacheRepository:
    """Repository for managing analytics cache records"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int, cache_key: str) -> AnalyticsCache | None:
        """Get cached analytics data if not expired"""
        stmt = select(AnalyticsCache).where(
            and_(
                AnalyticsCache.user_id == user_id,
                AnalyticsCache.cache_key == cache_key,
            )
        )
        cached = self.db.execute(stmt).scalar_one_or_none()

        if cached and cached.expires_at > ist_now():
            logger.debug(f"Analytics cache hit for user {user_id}, key: {cache_key}")
            return cached
        elif cached:
            # Expired, delete it
            logger.debug(f"Analytics cache expired for user {user_id}, key: {cache_key}")
            self.db.delete(cached)
            self.db.commit()
            return None

        return None

    def create_or_update(
        self,
        user_id: int,
        cache_key: str,
        cached_data: dict,
        analytics_type: str,
        ttl_hours: int = 24,
        date_range_start: datetime.date | None = None,
        date_range_end: datetime.date | None = None,
    ) -> AnalyticsCache:
        """Create or update analytics cache record"""
        # Check if exists
        existing = self.get(user_id, cache_key)

        if existing:
            # Update existing record
            existing.cached_data = cached_data
            existing.analytics_type = analytics_type
            existing.date_range_start = date_range_start
            existing.date_range_end = date_range_end
            existing.expires_at = ist_now() + timedelta(hours=ttl_hours)
            existing.calculated_at = ist_now()
            self.db.commit()
            self.db.refresh(existing)
            logger.debug(f"Updated analytics cache for user {user_id}, key: {cache_key}")
            return existing
        else:
            # Create new record
            cache = AnalyticsCache(
                user_id=user_id,
                cache_key=cache_key,
                analytics_type=analytics_type,
                date_range_start=date_range_start,
                date_range_end=date_range_end,
                cached_data=cached_data,
                expires_at=ist_now() + timedelta(hours=ttl_hours),
                calculated_at=ist_now(),
            )
            self.db.add(cache)
            self.db.commit()
            self.db.refresh(cache)
            logger.debug(f"Created analytics cache for user {user_id}, key: {cache_key}")
            return cache

    def invalidate(self, user_id: int, analytics_type: str | None = None) -> int:
        """Invalidate cache for a user, optionally filtered by analytics type"""
        stmt = delete(AnalyticsCache).where(AnalyticsCache.user_id == user_id)

        if analytics_type:
            stmt = stmt.where(AnalyticsCache.analytics_type == analytics_type)

        result = self.db.execute(stmt)
        self.db.commit()
        deleted_count = result.rowcount
        logger.info(
            f"Invalidated {deleted_count} analytics cache entries for user {user_id}"
            + (f" (type: {analytics_type})" if analytics_type else "")
        )
        return deleted_count

    def cleanup_expired(self) -> int:
        """Remove all expired cache entries"""
        now = ist_now()
        stmt = delete(AnalyticsCache).where(AnalyticsCache.expires_at < now)
        result = self.db.execute(stmt)
        self.db.commit()
        deleted_count = result.rowcount
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired analytics cache entries")
        return deleted_count

    def get_by_type(
        self, user_id: int, analytics_type: str, limit: int = 100
    ) -> list[AnalyticsCache]:
        """Get all non-expired cache entries for a user and analytics type"""
        now = ist_now()
        stmt = (
            select(AnalyticsCache)
            .where(
                and_(
                    AnalyticsCache.user_id == user_id,
                    AnalyticsCache.analytics_type == analytics_type,
                    AnalyticsCache.expires_at > now,
                )
            )
            .order_by(AnalyticsCache.calculated_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

