"""Repository for PriceCache management (Phase 0.6)"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select, and_, delete
from sqlalchemy.orm import Session

from src.infrastructure.db.models import PriceCache

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class PriceCacheRepository:
    """Repository for managing price cache records"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, symbol: str, date: date) -> PriceCache | None:
        """Get cached price for a symbol and date"""
        stmt = select(PriceCache).where(
            and_(PriceCache.symbol == symbol, PriceCache.date == date)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create_or_update(
        self,
        symbol: str,
        date: date,
        open: float | None = None,
        high: float | None = None,
        low: float | None = None,
        close: float,
        volume: int | None = None,
        source: str = "yfinance",
    ) -> PriceCache:
        """Create or update a price cache record"""
        existing = self.get(symbol, date)

        if existing:
            # Update existing record
            existing.open = open
            existing.high = high
            existing.low = low
            existing.close = close
            existing.volume = volume
            existing.source = source
            existing.cached_at = datetime.now()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            # Create new record
            cache = PriceCache(
                symbol=symbol,
                date=date,
                open=open,
                high=high,
                low=low,
                close=close,
                volume=volume,
                source=source,
            )
            self.db.add(cache)
            self.db.commit()
            self.db.refresh(cache)
            return cache

    def get_bulk(self, symbols: list[str], date: date) -> dict[str, PriceCache]:
        """Get cached prices for multiple symbols on a specific date"""
        stmt = select(PriceCache).where(
            and_(PriceCache.symbol.in_(symbols), PriceCache.date == date)
        )
        results = self.db.execute(stmt).scalars().all()
        return {cache.symbol: cache for cache in results}

    def get_range(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[PriceCache]:
        """Get cached prices for a symbol within a date range"""
        stmt = select(PriceCache).where(
            and_(
                PriceCache.symbol == symbol,
                PriceCache.date >= start_date,
                PriceCache.date <= end_date,
            )
        ).order_by(PriceCache.date)
        return list(self.db.execute(stmt).scalars().all())

    def invalidate_old(self, days: int = 365) -> int:
        """Remove cache entries older than specified days"""
        cutoff_date = date.today() - timedelta(days=days)
        stmt = delete(PriceCache).where(PriceCache.date < cutoff_date)
        result = self.db.execute(stmt)
        self.db.commit()
        deleted_count = result.rowcount
        logger.info(f"Invalidated {deleted_count} price cache entries older than {days} days")
        return deleted_count

    def invalidate_symbol(self, symbol: str) -> int:
        """Remove all cache entries for a specific symbol"""
        stmt = delete(PriceCache).where(PriceCache.symbol == symbol)
        result = self.db.execute(stmt)
        self.db.commit()
        deleted_count = result.rowcount
        logger.info(f"Invalidated {deleted_count} price cache entries for symbol {symbol}")
        return deleted_count

    def get_missing_dates(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[date]:
        """Get list of dates missing from cache for a symbol within date range"""
        # Get all cached dates for the symbol in range
        stmt = select(PriceCache.date).where(
            and_(
                PriceCache.symbol == symbol,
                PriceCache.date >= start_date,
                PriceCache.date <= end_date,
            )
        )
        cached_dates = {row[0] for row in self.db.execute(stmt).all()}

        # Generate all dates in range
        all_dates = []
        current_date = start_date
        while current_date <= end_date:
            all_dates.append(current_date)
            current_date += timedelta(days=1)

        # Return missing dates
        return [d for d in all_dates if d not in cached_dates]

