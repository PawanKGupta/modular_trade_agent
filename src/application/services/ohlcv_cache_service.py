"""Postgres/SQLite-backed OHLCV cache with trading-day gap-fill and tail refresh."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from config.settings import OHLCV_CACHE_TAIL_OVERLAP_TRADING_DAYS
from src.infrastructure.persistence.price_cache_repository import (
    DEFAULT_INTERVAL,
    DEFAULT_PRICE_BASIS,
    PriceCacheRepository,
)
from src.infrastructure.utils.holiday_calendar import get_previous_trading_day

logger = logging.getLogger(__name__)

# Observability counters (reset per process; bulk job may read via get_stats)
_yahoo_fetch_count = 0


def get_ohlcv_cache_stats() -> dict[str, int]:
    """Return process-local Yahoo fetch count via cache service."""
    return {"yahoo_calls": _yahoo_fetch_count}


def reset_ohlcv_cache_stats() -> None:
    """Reset Yahoo call counter (tests / bulk chunk boundaries)."""
    global _yahoo_fetch_count  # noqa: PLW0603
    _yahoo_fetch_count = 0


def _bump_yahoo_calls(n: int = 1) -> None:
    global _yahoo_fetch_count  # noqa: PLW0603
    _yahoo_fetch_count += n


def _parse_end_date(end_date: str | datetime | None) -> date:
    if end_date is None:
        return date.today()
    if isinstance(end_date, datetime):
        return end_date.date()
    if isinstance(end_date, str):
        return datetime.strptime(end_date, "%Y-%m-%d").date()
    if isinstance(end_date, date):
        return end_date
    raise ValueError("end_date must be None, str YYYY-MM-DD, date, or datetime")


def _bars_to_dataframe(bars: list) -> pd.DataFrame:
    """Convert PriceCache rows to fetch_ohlcv_yf-compatible DataFrame."""
    if not bars:
        return pd.DataFrame()
    rows = []
    for bar in bars:
        rows.append(
            {
                "date": bar.date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
        )
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def _dataframe_to_upsert_rows(
    symbol: str,
    df: pd.DataFrame,
    interval: str = DEFAULT_INTERVAL,
    price_basis: str = DEFAULT_PRICE_BASIS,
) -> list[dict]:
    """Build upsert payloads from a yfinance-style DataFrame."""
    if df is None or df.empty:
        return []

    work = df.copy()
    if "date" not in work.columns:
        if isinstance(work.index, pd.DatetimeIndex):
            work = work.reset_index()
            date_col = work.columns[0]
            work = work.rename(columns={date_col: "date"})
        else:
            return []

    work["date"] = pd.to_datetime(work["date"])
    rows: list[dict] = []
    for _, row in work.iterrows():
        bar_date = (
            row["date"].date() if hasattr(row["date"], "date") else pd.Timestamp(row["date"]).date()
        )
        close = row.get("close", row.get("Close"))
        if close is None or pd.isna(close):
            continue
        rows.append(
            {
                "symbol": symbol,
                "date": bar_date,
                "interval": interval,
                "price_basis": price_basis,
                "open": _safe_float(row.get("open", row.get("Open"))),
                "high": _safe_float(row.get("high", row.get("High"))),
                "low": _safe_float(row.get("low", row.get("Low"))),
                "close": float(close),
                "volume": _safe_int(row.get("volume", row.get("Volume"))),
                "source": "yfinance",
            }
        )
    return rows


def _safe_float(val) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


class OhlcvCacheService:
    """Read-through OHLCV cache with gap-fill and tail refresh."""

    def __init__(
        self,
        db: Session,
        fetch_func: Callable | None = None,
        *,
        tail_overlap_trading_days: int | None = None,
    ):
        self.db = db
        self.repo = PriceCacheRepository(db)
        self._fetch_func = fetch_func
        self.tail_overlap_trading_days = (
            tail_overlap_trading_days
            if tail_overlap_trading_days is not None
            else OHLCV_CACHE_TAIL_OVERLAP_TRADING_DAYS
        )

    def _yahoo_fetch(self, *args, **kwargs) -> pd.DataFrame:
        if self._fetch_func is None:
            from core.data_fetcher import fetch_ohlcv_yf_raw  # noqa: PLC0415

            fetcher = fetch_ohlcv_yf_raw
        else:
            fetcher = self._fetch_func
        _bump_yahoo_calls()
        return fetcher(*args, **kwargs)

    def get_ohlcv(
        self,
        symbol: str,
        days: int = 365,
        interval: str = DEFAULT_INTERVAL,
        end_date: str | datetime | None = None,
        add_current_day: bool = True,
    ) -> pd.DataFrame | None:
        """
        Return OHLCV for symbol, filling cache gaps from Yahoo when needed.

        Args:
            symbol: Ticker symbol.
            days: Lookback calendar days (matches fetch_ohlcv_yf).
            interval: ``1d`` or ``1wk``.
            end_date: End of range (inclusive semantics via Yahoo helper).
            add_current_day: Pass through to Yahoo fetch on gap-fill.

        Returns:
            DataFrame with lowercase OHLCV + date column, or None if unavailable.
        """
        end_d = _parse_end_date(end_date)
        start_d = end_d - timedelta(days=days + 5)

        missing = self.repo.get_missing_trading_dates(symbol, start_d, end_d, interval=interval)
        if missing:
            self.gap_fill(
                symbol,
                start_d,
                end_d,
                interval=interval,
                days=days,
                yf_end_date=end_date,
                add_current_day=add_current_day,
            )

        bars = self.repo.get_range(symbol, start_d, end_d, interval=interval)
        if not bars:
            return None

        df = _bars_to_dataframe(bars)
        if not add_current_day and not df.empty:
            df = df[df["date"].dt.date <= end_d]
        return df

    def gap_fill(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        *,
        interval: str = DEFAULT_INTERVAL,
        days: int | None = None,
        yf_end_date: str | datetime | None = None,
        add_current_day: bool = True,
    ) -> int:
        """
        Fetch missing range from Yahoo and upsert into cache.

        Returns:
            Number of rows upserted.
        """
        lookback = days if days is not None else (end_date - start_date).days + 30
        fetched = self._yahoo_fetch(
            symbol,
            days=lookback,
            interval=interval,
            end_date=yf_end_date,
            add_current_day=add_current_day,
        )
        if fetched is None or fetched.empty:
            logger.warning("gap_fill: no data for %s [%s]", symbol, interval)
            return 0

        rows = _dataframe_to_upsert_rows(symbol, fetched, interval=interval)
        filtered = [r for r in rows if start_date <= r["date"] <= end_date]
        if not filtered:
            return 0

        count = self.repo.upsert_many(filtered)
        self.repo.refresh_symbol_meta(symbol, interval=interval)
        logger.info(
            "gap_fill %s [%s]: upserted %s rows (%s to %s)",
            symbol,
            interval,
            count,
            start_date,
            end_date,
        )
        return count

    def upsert_bars(self, symbol: str, df: pd.DataFrame, interval: str = DEFAULT_INTERVAL) -> int:
        """Upsert OHLCV bars and refresh symbol meta."""
        rows = _dataframe_to_upsert_rows(symbol, df, interval=interval)
        if not rows:
            return 0
        count = self.repo.upsert_many(rows)
        self.repo.refresh_symbol_meta(symbol, interval=interval)
        return count

    def refresh_tail(
        self,
        symbol: str,
        interval: str = DEFAULT_INTERVAL,
        overlap_trading_days: int | None = None,
        *,
        end_date: str | datetime | None = None,
        add_current_day: bool = False,
    ) -> int:
        """
        Re-fetch last N trading days and upsert (Yahoo wins on overlap).

        Returns:
            Rows upserted.
        """
        overlap = overlap_trading_days or self.tail_overlap_trading_days
        end_d = _parse_end_date(end_date)
        start_d = end_d
        counted = 0
        while counted < overlap:
            start_d = get_previous_trading_day(start_d)
            counted += 1

        lookback_days = (end_d - start_d).days + 30
        fetched = self._yahoo_fetch(
            symbol,
            days=lookback_days,
            interval=interval,
            end_date=end_date,
            add_current_day=add_current_day,
        )
        if fetched is None or fetched.empty:
            return 0
        return self.upsert_bars(symbol, fetched, interval=interval)

    def invalidate_symbol(self, symbol: str, interval: str | None = None) -> int:
        """Delete cached bars for symbol (delegates to repository)."""
        deleted = self.repo.invalidate_symbol(symbol, interval=interval)
        if interval:
            meta = self.repo.get_symbol_meta(symbol, interval=interval)
            if meta:
                self.db.delete(meta)
                self.db.commit()
        else:
            for iv in ("1d", "1wk"):
                meta = self.repo.get_symbol_meta(symbol, interval=iv)
                if meta:
                    self.db.delete(meta)
            self.db.commit()
        return deleted

    def merge_cached_and_fetched(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        fetched_df: pd.DataFrame,
        interval: str = DEFAULT_INTERVAL,
    ) -> pd.DataFrame:
        """
        Merge cached and freshly fetched data; Yahoo wins on duplicate dates.

        Used for incremental tail refresh and helper compatibility.
        """
        cached = self.repo.get_range(symbol, start_date, end_date, interval=interval)
        cached_df = _bars_to_dataframe(cached)
        if cached_df.empty:
            return fetched_df

        if fetched_df is None or fetched_df.empty:
            return cached_df

        c = cached_df.set_index("date")
        f = fetched_df.copy()
        if "date" in f.columns:
            f = f.set_index("date")
        elif not isinstance(f.index, pd.DatetimeIndex):
            f.index = pd.to_datetime(f.index)

        combined = pd.concat([c, f])
        combined = combined[~combined.index.duplicated(keep="last")]
        return combined.sort_index().reset_index().rename(columns={"index": "date"})


def create_ohlcv_cache_service(
    db: Session, fetch_func: Callable | None = None
) -> OhlcvCacheService | None:
    """
    Factory: returns cache service when OHLCV_CACHE_ENABLED, else None.

    Args:
        db: SQLAlchemy session.
        fetch_func: Optional Yahoo fetch override (tests).

    Returns:
        OhlcvCacheService or None when disabled.
    """
    from config.settings import OHLCV_CACHE_ENABLED  # noqa: PLC0415

    if not OHLCV_CACHE_ENABLED:
        return None
    return OhlcvCacheService(db, fetch_func=fetch_func)
