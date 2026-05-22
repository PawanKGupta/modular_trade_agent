"""Repository for PriceCache management (Phase 0.6 + OHLCV interval support)."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import and_, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from config.settings import OHLCV_CACHE_MIN_COVERAGE_PCT, OHLCV_CACHE_TAIL_OVERLAP_TRADING_DAYS
from src.infrastructure.db.dialect import is_postgresql
from src.infrastructure.db.models import CorporateAction, OhlcvSymbolMeta, PriceCache
from src.infrastructure.db.timezone_utils import ist_now_naive
from src.infrastructure.utils.holiday_calendar import (
    iter_expected_weekly_bar_dates,
    iter_trading_days,
)

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = "1d"
WEEKLY_INTERVAL = "1wk"
DEFAULT_PRICE_BASIS = "unadjusted"
DEFAULT_WEEKLY_TAIL_WEEKS = 3
# Yahoo weekly bar dates may fall a few days from ISO week-ending trading day.
WEEKLY_BAR_DATE_TOLERANCE_DAYS = 4


def _iso_week_key(bar_date: date) -> tuple[int, int]:
    return bar_date.isocalendar()[:2]


def week_has_cached_bar(
    cached_dates: set[date],
    week_ref: date,
    *,
    tolerance_days: int = WEEKLY_BAR_DATE_TOLERANCE_DAYS,
) -> bool:
    """
    True if cache contains a weekly bar for the ISO week of ``week_ref``.

    Uses ISO week match first, then proximity to ``week_ref`` (Yahoo dating).
    """
    target = _iso_week_key(week_ref)
    if any(_iso_week_key(d) == target for d in cached_dates):
        return True
    return any(abs((d - week_ref).days) <= tolerance_days for d in cached_dates)


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

    def _cached_dates_in_range(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        interval: str,
    ) -> set[date]:
        """Dates present in price_cache for symbol/interval within range."""
        return {
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

    def _expected_bar_dates(
        self,
        start_date: date,
        end_date: date,
        interval: str,
    ) -> list[date]:
        if interval == WEEKLY_INTERVAL:
            return list(iter_expected_weekly_bar_dates(start_date, end_date))
        return list(iter_trading_days(start_date, end_date))

    def get_coverage_pct(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        interval: str = DEFAULT_INTERVAL,
    ) -> float:
        """Percent of expected bars in range present in cache (interval-aware)."""
        expected = self._expected_bar_dates(start_date, end_date, interval)
        if not expected:
            return 100.0
        cached_dates = self._cached_dates_in_range(symbol, start_date, end_date, interval)
        if interval == WEEKLY_INTERVAL:
            hits = sum(1 for d in expected if week_has_cached_bar(cached_dates, d))
            return 100.0 * hits / len(expected)
        hits = sum(1 for d in expected if d in cached_dates)
        return 100.0 * hits / len(expected)

    def get_dates_needing_gap_fill(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        interval: str = DEFAULT_INTERVAL,
        *,
        tail_trading_days: int | None = None,
        min_coverage_pct: float | None = None,
        weekly_tail_weeks: int = DEFAULT_WEEKLY_TAIL_WEEKS,
    ) -> list[date]:
        """
        Bar dates that should trigger a Yahoo gap-fill (read-through cache).

        Daily (``1d``): refill when coverage is below threshold or the tail window
        lacks bars (Yahoo often omits exchange holidays — interior gaps are ignored
        when coverage is adequate).

        Weekly (``1wk``): ISO week coverage plus tail weeks matched by week bucket
        (not exact bar date — Yahoo week stamps differ slightly).
        """
        tail_n = (
            tail_trading_days
            if tail_trading_days is not None
            else OHLCV_CACHE_TAIL_OVERLAP_TRADING_DAYS
        )
        min_cov = min_coverage_pct if min_coverage_pct is not None else OHLCV_CACHE_MIN_COVERAGE_PCT

        cached_dates = self._cached_dates_in_range(symbol, start_date, end_date, interval)
        if not cached_dates:
            return [start_date]

        expected = self._expected_bar_dates(start_date, end_date, interval)
        if not expected:
            return []

        if interval == WEEKLY_INTERVAL:
            coverage_pct = (
                100.0
                * sum(1 for d in expected if week_has_cached_bar(cached_dates, d))
                / len(expected)
            )
        else:
            coverage_pct = 100.0 * sum(1 for d in expected if d in cached_dates) / len(expected)

        if interval == WEEKLY_INTERVAL:
            tail_expected = (
                expected[-weekly_tail_weeks:] if len(expected) > weekly_tail_weeks else expected
            )
            missing_tail = [d for d in tail_expected if not week_has_cached_bar(cached_dates, d)]
        else:
            tail_expected = expected[-tail_n:] if len(expected) > tail_n else expected
            missing_tail = [d for d in tail_expected if d not in cached_dates]

        if coverage_pct < min_cov:
            return missing_tail if missing_tail else [start_date]
        return missing_tail

    def get_missing_trading_dates(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        interval: str = DEFAULT_INTERVAL,
    ) -> list[date]:
        """Expected bar dates in range absent from cache (interval-aware)."""
        cached_dates = self._cached_dates_in_range(symbol, start_date, end_date, interval)
        expected = self._expected_bar_dates(start_date, end_date, interval)
        if interval == WEEKLY_INTERVAL:
            return [d for d in expected if not week_has_cached_bar(cached_dates, d)]
        return [d for d in expected if d not in cached_dates]

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
