"""Repository for PriceCache management (Phase 0.6 + OHLCV interval support)."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import and_, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from config.settings import (
    OHLCV_CACHE_MIN_COVERAGE_PCT,
    OHLCV_CACHE_TAIL_OVERLAP_TRADING_DAYS,
    OHLCV_LISTING_START_GAP_MAX_COVERAGE_PCT,
    OHLCV_LISTING_START_GAP_MIN_MISSING,
    OHLCV_LISTING_START_GAP_WINDOW_TRADING_DAYS,
)
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
# Intraday intervals are not stored in price_cache (Date column, one row per day).
MINUTE_INTERVAL = "1m"
DEFAULT_PRICE_BASIS = "unadjusted"
DEFAULT_WEEKLY_TAIL_WEEKS = 3
# Yahoo weekly bar dates may fall a few days from ISO week-ending trading day.
WEEKLY_BAR_DATE_TOLERANCE_DAYS = 4


def _iso_week_key(bar_date: date) -> tuple[int, int]:
    return bar_date.isocalendar()[:2]


def listing_aware_coverage_start(
    requested_start: date,
    end_date: date,
    cached_dates: set[date],
    *,
    meta_first_date: date | None = None,
) -> date:
    """
    Effective start for coverage denominators: max(requested_start, first available bar).

    Pre-listing trading days are excluded from expected-bar counts so young listings
    are not treated as permanently incomplete versus a multi-year lookback window.
    """
    if end_date < requested_start:
        return requested_start

    first_bar: date | None = None
    if cached_dates:
        in_window = [d for d in cached_dates if requested_start <= d <= end_date]
        if in_window:
            first_bar = min(in_window)
    if first_bar is None and meta_first_date is not None and meta_first_date <= end_date:
        first_bar = max(requested_start, meta_first_date)

    if first_bar is None:
        return requested_start
    return max(requested_start, first_bar)


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

    def _listing_aware_start(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        interval: str,
        cached_dates: set[date],
    ) -> date:
        meta = self.get_symbol_meta(symbol, interval=interval)
        meta_first = meta.first_date if meta else None
        return listing_aware_coverage_start(
            start_date,
            end_date,
            cached_dates,
            meta_first_date=meta_first,
        )

    def _coverage_pct_for_cached(
        self,
        cached_dates: set[date],
        effective_start: date,
        end_date: date,
        interval: str,
    ) -> float:
        """Hit rate over expected bars from effective_start through end_date."""
        expected = self._expected_bar_dates(effective_start, end_date, interval)
        if not expected:
            return 100.0
        if interval == WEEKLY_INTERVAL:
            hits = sum(1 for d in expected if week_has_cached_bar(cached_dates, d))
        else:
            hits = sum(1 for d in expected if d in cached_dates)
        return 100.0 * hits / len(expected)

    def get_coverage_pct(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        interval: str = DEFAULT_INTERVAL,
    ) -> float:
        """Percent of expected bars present in cache (listing-aware, interval-aware)."""
        cached_dates = self._cached_dates_in_range(symbol, start_date, end_date, interval)
        if not cached_dates:
            return 0.0
        effective_start = self._listing_aware_start(
            symbol, start_date, end_date, interval, cached_dates
        )
        return self._coverage_pct_for_cached(cached_dates, effective_start, end_date, interval)

    def listing_aware_effective_start(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        interval: str,
    ) -> date:
        """Effective coverage start for symbol/window (uses cached bars in range)."""
        cached_dates = self._cached_dates_in_range(symbol, start_date, end_date, interval)
        if not cached_dates:
            return start_date
        return self._listing_aware_start(symbol, start_date, end_date, interval, cached_dates)

    def missing_before_first_cached_bar(
        self,
        symbol: str,
        cached_dates: set[date],
        requested_start: date,
        end_date: date,
        interval: str,
        *,
        window_trading_days: int | None = None,
    ) -> list[date]:
        """
        Trading days after listing anchor and before the earliest cached bar.

        Uses ``ohlcv_symbol_meta.first_date`` when set so a 5y requested window does not
        treat pre-listing calendar days as refill triggers.
        """
        if interval != DEFAULT_INTERVAL or not cached_dates:
            return []
        window_n = (
            window_trading_days
            if window_trading_days is not None
            else OHLCV_LISTING_START_GAP_WINDOW_TRADING_DAYS
        )
        first_cached = min(cached_dates)
        meta = self.get_symbol_meta(symbol, interval=interval)
        listing_anchor = requested_start
        if meta and meta.first_date:
            listing_anchor = max(requested_start, meta.first_date)
        if first_cached <= listing_anchor:
            return []
        listing_window = self._expected_bar_dates(listing_anchor, end_date, interval)
        if not listing_window:
            return []
        start_window = listing_window[:window_n]
        return [d for d in start_window if d < first_cached]

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

        effective_start = self._listing_aware_start(
            symbol, start_date, end_date, interval, cached_dates
        )
        expected = self._expected_bar_dates(effective_start, end_date, interval)
        if not expected:
            return []

        coverage_pct = self._coverage_pct_for_cached(
            cached_dates, effective_start, end_date, interval
        )

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

        if interval == DEFAULT_INTERVAL:
            calendar_coverage = self._coverage_pct_for_cached(
                cached_dates, start_date, end_date, interval
            )
            start_gaps = self.missing_before_first_cached_bar(
                symbol, cached_dates, start_date, end_date, interval
            )
            listing_ok = coverage_pct >= min_cov
            calendar_mid_band = (
                min_cov <= calendar_coverage < OHLCV_LISTING_START_GAP_MAX_COVERAGE_PCT
            )
            if len(start_gaps) >= OHLCV_LISTING_START_GAP_MIN_MISSING and (
                calendar_mid_band or listing_ok
            ):
                return [start_date]

        return missing_tail

    def get_missing_trading_dates(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        interval: str = DEFAULT_INTERVAL,
    ) -> list[date]:
        """Expected bar dates in range absent from cache (listing-aware, interval-aware)."""
        cached_dates = self._cached_dates_in_range(symbol, start_date, end_date, interval)
        if not cached_dates:
            return self._expected_bar_dates(start_date, end_date, interval)
        effective_start = self._listing_aware_start(
            symbol, start_date, end_date, interval, cached_dates
        )
        expected = self._expected_bar_dates(effective_start, end_date, interval)
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
        intervals = [DEFAULT_INTERVAL, WEEKLY_INTERVAL] if interval is None else [interval]
        for iv in intervals:
            self.reset_symbol_meta(symbol, iv)
        return deleted_count

    def reset_symbol_meta(self, symbol: str, interval: str = DEFAULT_INTERVAL) -> OhlcvSymbolMeta:
        """
        Clear cache summary and validation fields after invalidate or empty cache.

        Keeps the meta row but resets counts and ``fetch_status`` to ``unknown``.
        """
        meta = self.get_symbol_meta(symbol, interval=interval)
        if meta is None:
            meta = OhlcvSymbolMeta(symbol=symbol, interval=interval, row_count=0)
            self.db.add(meta)
        meta.first_date = None
        meta.last_date = None
        meta.row_count = 0
        meta.fetch_status = "unknown"
        meta.coverage_pct = None
        meta.last_validation_message = None
        meta.last_fetch_at = None
        meta.updated_at = ist_now_naive()
        self.db.commit()
        self.db.refresh(meta)
        return meta

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

    def record_fetch_validation(
        self,
        symbol: str,
        interval: str,
        *,
        fetch_status: str,
        coverage_pct: float | None,
        message: str,
    ) -> OhlcvSymbolMeta:
        """Persist Yahoo ingest validation outcome on ohlcv_symbol_meta."""
        meta = self.get_symbol_meta(symbol, interval=interval)
        if meta is None:
            meta = OhlcvSymbolMeta(symbol=symbol, interval=interval, row_count=0)
            self.db.add(meta)
        meta.fetch_status = fetch_status
        meta.coverage_pct = coverage_pct
        meta.last_validation_message = message[:2000] if message else None
        meta.last_fetch_at = ist_now_naive()
        meta.updated_at = ist_now_naive()
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
