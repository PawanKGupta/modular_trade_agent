"""Repository for PriceCache management (Phase 0.6 + OHLCV interval support)."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import and_, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from src.infrastructure.db.dialect import is_postgresql
from src.infrastructure.db.models import CorporateAction, OhlcvSymbolMeta, PriceCache
from src.infrastructure.db.timezone_utils import ist_now_naive
from src.infrastructure.utils.holiday_calendar import iter_trading_days

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = "1d"
DEFAULT_PRICE_BASIS = "unadjusted"


class PriceCacheRepository:
    """Repository for managing price cache records."""

    def __init__(self, db: Session):
        self.db = db

    def get(
        self,
        symbol: str,
        bar_date: date,
        interval: str = DEFAULT_INTERVAL,
    ) -> PriceCache | None:
        """Get cached price for a symbol, date, and interval."""
        stmt = select(PriceCache).where(
            and_(
                PriceCache.symbol == symbol,
                PriceCache.date == bar_date,
                PriceCache.interval == interval,
            )
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create_or_update(
        self,
        symbol: str,
        bar_date: date,
        close: float,
        open: float | None = None,
        high: float | None = None,
        low: float | None = None,
        volume: int | None = None,
        source: str = "yfinance",
        interval: str = DEFAULT_INTERVAL,
        price_basis: str = DEFAULT_PRICE_BASIS,
        *,
        commit: bool = True,
    ) -> PriceCache:
        """Create or update a price cache record."""
        existing = self.get(symbol, bar_date, interval=interval)

        if existing:
            existing.open = open
            existing.high = high
            existing.low = low
            existing.close = close
            existing.volume = volume
            existing.source = source
            existing.price_basis = price_basis
            existing.cached_at = ist_now_naive()
            if commit:
                self.db.commit()
                self.db.refresh(existing)
            return existing

        cache = PriceCache(
            symbol=symbol,
            date=bar_date,
            interval=interval,
            price_basis=price_basis,
            open=open,
            high=high,
            low=low,
            close=close,
            volume=volume,
            source=source,
        )
        self.db.add(cache)
        if commit:
            self.db.commit()
            self.db.refresh(cache)
        return cache

    def upsert_many(
        self,
        rows: list[dict],
        *,
        commit: bool = True,
    ) -> int:
        """
        Batch upsert OHLCV rows.

        Each row dict: symbol, date, open, high, low, close, volume, optional interval,
        price_basis, source.
        """
        if not rows:
            return 0

        now = ist_now_naive()
        payload = []
        for row in rows:
            payload.append(
                {
                    "symbol": row["symbol"],
                    "date": row["date"],
                    "interval": row.get("interval", DEFAULT_INTERVAL),
                    "price_basis": row.get("price_basis", DEFAULT_PRICE_BASIS),
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row["close"],
                    "volume": row.get("volume"),
                    "source": row.get("source", "yfinance"),
                    "cached_at": now,
                }
            )

        if is_postgresql(self.db):
            stmt = pg_insert(PriceCache).values(payload)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "date", "interval"],
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                    "source": stmt.excluded.source,
                    "price_basis": stmt.excluded.price_basis,
                    "cached_at": stmt.excluded.cached_at,
                },
            )
            result = self.db.execute(stmt)
            if commit:
                self.db.commit()
            return result.rowcount or len(payload)

        stmt = sqlite_insert(PriceCache).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "date", "interval"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "source": stmt.excluded.source,
                "price_basis": stmt.excluded.price_basis,
                "cached_at": stmt.excluded.cached_at,
            },
        )
        result = self.db.execute(stmt)
        if commit:
            self.db.commit()
        return result.rowcount or len(payload)

    def get_bulk(
        self, symbols: list[str], bar_date: date, interval: str = DEFAULT_INTERVAL
    ) -> dict[str, PriceCache]:
        """Get cached prices for multiple symbols on a specific date."""
        stmt = select(PriceCache).where(
            and_(
                PriceCache.symbol.in_(symbols),
                PriceCache.date == bar_date,
                PriceCache.interval == interval,
            )
        )
        results = self.db.execute(stmt).scalars().all()
        return {cache.symbol: cache for cache in results}

    def get_range(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        interval: str = DEFAULT_INTERVAL,
    ) -> list[PriceCache]:
        """Get cached prices for a symbol within a date range."""
        stmt = (
            select(PriceCache)
            .where(
                and_(
                    PriceCache.symbol == symbol,
                    PriceCache.interval == interval,
                    PriceCache.date >= start_date,
                    PriceCache.date <= end_date,
                )
            )
            .order_by(PriceCache.date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_missing_trading_dates(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        interval: str = DEFAULT_INTERVAL,
    ) -> list[date]:
        """Trading days in range that are absent from cache for symbol/interval."""
        cached_dates = {
            row[0]
            for row in self.db.execute(
                select(PriceCache.date).where(
                    and_(
                        PriceCache.symbol == symbol,
                        PriceCache.interval == interval,
                        PriceCache.date >= start_date,
                        PriceCache.date <= end_date,
                    )
                )
            ).all()
        }
        return [d for d in iter_trading_days(start_date, end_date) if d not in cached_dates]

    def get_missing_dates(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[date]:
        """Backward-compatible alias: daily interval, trading days only."""
        return self.get_missing_trading_dates(symbol, start_date, end_date, DEFAULT_INTERVAL)

    def delete_range(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        interval: str = DEFAULT_INTERVAL,
    ) -> int:
        """Delete cached rows for symbol in date range."""
        stmt = delete(PriceCache).where(
            and_(
                PriceCache.symbol == symbol,
                PriceCache.interval == interval,
                PriceCache.date >= start_date,
                PriceCache.date <= end_date,
            )
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount or 0

    def invalidate_old(self, days: int = 365) -> int:
        """Remove cache entries older than specified days."""
        cutoff_date = date.today() - timedelta(days=days)
        stmt = delete(PriceCache).where(PriceCache.date < cutoff_date)
        result = self.db.execute(stmt)
        self.db.commit()
        deleted_count = result.rowcount or 0
        logger.info("Invalidated %s price cache entries older than %s days", deleted_count, days)
        return deleted_count

    def invalidate_symbol(self, symbol: str, interval: str | None = None) -> int:
        """Remove cache entries for a symbol (all intervals if interval is None)."""
        if interval is None:
            stmt = delete(PriceCache).where(PriceCache.symbol == symbol)
        else:
            stmt = delete(PriceCache).where(
                and_(PriceCache.symbol == symbol, PriceCache.interval == interval)
            )
        result = self.db.execute(stmt)
        self.db.commit()
        deleted_count = result.rowcount or 0
        logger.info(
            "Invalidated %s price cache entries for symbol %s interval=%s",
            deleted_count,
            symbol,
            interval or "all",
        )
        return deleted_count

    def refresh_symbol_meta(self, symbol: str, interval: str = DEFAULT_INTERVAL) -> OhlcvSymbolMeta:
        """Recompute ohlcv_symbol_meta from price_cache rows."""
        agg = self.db.execute(
            select(
                func.min(PriceCache.date),
                func.max(PriceCache.date),
                func.count(PriceCache.id),
            ).where(and_(PriceCache.symbol == symbol, PriceCache.interval == interval))
        ).one()

        first_date, last_date, row_count = agg
        existing = self.db.execute(
            select(OhlcvSymbolMeta).where(
                and_(OhlcvSymbolMeta.symbol == symbol, OhlcvSymbolMeta.interval == interval)
            )
        ).scalar_one_or_none()

        if existing:
            existing.first_date = first_date
            existing.last_date = last_date
            existing.row_count = int(row_count or 0)
            existing.updated_at = ist_now_naive()
            meta = existing
        else:
            meta = OhlcvSymbolMeta(
                symbol=symbol,
                interval=interval,
                first_date=first_date,
                last_date=last_date,
                row_count=int(row_count or 0),
            )
            self.db.add(meta)

        self.db.commit()
        self.db.refresh(meta)
        return meta

    def get_symbol_meta(
        self, symbol: str, interval: str = DEFAULT_INTERVAL
    ) -> OhlcvSymbolMeta | None:
        """Return cached meta row for symbol/interval."""
        return self.db.execute(
            select(OhlcvSymbolMeta).where(
                and_(OhlcvSymbolMeta.symbol == symbol, OhlcvSymbolMeta.interval == interval)
            )
        ).scalar_one_or_none()

    def upsert_corporate_action(
        self,
        symbol: str,
        ex_date: date,
        ratio: float,
        action_type: str = "split",
        source: str = "yfinance",
    ) -> CorporateAction:
        """Insert or update a corporate action row."""
        existing = self.db.execute(
            select(CorporateAction).where(
                and_(
                    CorporateAction.symbol == symbol,
                    CorporateAction.ex_date == ex_date,
                    CorporateAction.action_type == action_type,
                )
            )
        ).scalar_one_or_none()
        if existing:
            existing.ratio = ratio
            existing.source = source
            existing.fetched_at = ist_now_naive()
            row = existing
        else:
            row = CorporateAction(
                symbol=symbol,
                ex_date=ex_date,
                ratio=ratio,
                action_type=action_type,
                source=source,
            )
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_corporate_actions(
        self, symbol: str, start_date: date | None = None, end_date: date | None = None
    ) -> list[CorporateAction]:
        """List corporate actions for a symbol, optionally filtered by ex_date range."""
        conditions = [CorporateAction.symbol == symbol]
        if start_date is not None:
            conditions.append(CorporateAction.ex_date >= start_date)
        if end_date is not None:
            conditions.append(CorporateAction.ex_date <= end_date)
        stmt = select(CorporateAction).where(and_(*conditions)).order_by(CorporateAction.ex_date)
        return list(self.db.execute(stmt).scalars().all())
