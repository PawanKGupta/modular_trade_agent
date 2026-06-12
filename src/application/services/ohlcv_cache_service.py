"""Postgres/SQLite-backed OHLCV cache with trading-day gap-fill and tail refresh."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from config.settings import (
    OHLCV_CACHE_MIN_COVERAGE_PCT,
    OHLCV_CACHE_TAIL_OVERLAP_TRADING_DAYS,
    OHLCV_DAILY_SOURCE,
    OHLCV_ENFORCE_INDICATOR_MIN_BARS,
    OHLCV_MIN_DAILY_BARS_FOR_INDICATORS,
    OHLCV_REJECT_INVALID_FETCH,
    daily_ohlcv_uses_nse,
    daily_ohlcv_yahoo_fallback,
)
from src.application.services.ohlcv_cache_logging import log_ohlcv_cache
from src.application.services.ohlcv_fetch_validation import (
    meets_indicator_history_requirement,
    validate_cached_symbol,
    validate_yahoo_ohlcv_frame,
)
from src.application.services.ohlcv_runtime import is_ohlcv_cache_read_only
from src.infrastructure.persistence.price_cache_repository import (
    DEFAULT_INTERVAL,
    DEFAULT_PRICE_BASIS,
    MINUTE_INTERVAL,
    PriceCacheRepository,
)
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.utils.holiday_calendar import get_previous_trading_day, iter_trading_days
from utils.logger import logger

# Observability counters (reset per process; bulk job may read via get_stats)
_yahoo_fetch_count = 0
_nse_bhavcopy_days_fetched = 0


def get_ohlcv_cache_stats() -> dict[str, int]:
    """Return process-local OHLCV fetch counters via cache service."""
    return {
        "yahoo_calls": _yahoo_fetch_count,
        "nse_bhavcopy_days_fetched": _nse_bhavcopy_days_fetched,
    }


def reset_ohlcv_cache_stats() -> None:
    """Reset fetch counters (tests / bulk chunk boundaries)."""
    global _yahoo_fetch_count, _nse_bhavcopy_days_fetched  # noqa: PLW0603
    _yahoo_fetch_count = 0
    _nse_bhavcopy_days_fetched = 0


def _bump_yahoo_calls(n: int = 1) -> None:
    global _yahoo_fetch_count  # noqa: PLW0603
    _yahoo_fetch_count += n


def _bump_nse_days(n: int = 1) -> None:
    global _nse_bhavcopy_days_fetched  # noqa: PLW0603
    _nse_bhavcopy_days_fetched += n


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


NSE_BAR_SOURCE = "nse"


def _filter_daily_bars_for_source_policy(
    bars: list,
    *,
    symbol: str,
    interval: str,
) -> list:
    """
    Apply ``OHLCV_DAILY_SOURCE`` read policy for daily bars returned to indicators.

    Legacy ``yfinance`` rows often remain for dates before NSE backfill. Mixing them
    into one series skews EMA/RSI even when recent NSE closes match TradingView.
    """
    if interval != DEFAULT_INTERVAL or not daily_ohlcv_uses_nse() or not bars:
        return bars

    nse_bars = [b for b in bars if getattr(b, "source", None) == NSE_BAR_SOURCE]

    if OHLCV_DAILY_SOURCE == "nse":
        dropped = len(bars) - len(nse_bars)
        if dropped:
            log_ohlcv_cache(
                logger,
                "OHLCV source_filter %s [%s]: nse-only %s/%s bars (excluded %s yfinance)",
                symbol,
                interval,
                len(nse_bars),
                len(bars),
                dropped,
            )
        return nse_bars

    # nse_with_yahoo_fallback: keep Yahoo rows only for dates without NSE coverage
    nse_dates = {b.date for b in nse_bars}
    yf_fill = [
        b
        for b in bars
        if getattr(b, "source", None) != NSE_BAR_SOURCE and b.date not in nse_dates
    ]
    if yf_fill:
        log_ohlcv_cache(
            logger,
            "OHLCV source_filter %s [%s]: nse=%s yahoo_gap_fill=%s",
            symbol,
            interval,
            len(nse_bars),
            len(yf_fill),
        )
    combined = nse_bars + yf_fill
    combined.sort(key=lambda b: b.date)
    return combined


def _dataframe_to_upsert_rows(
    symbol: str,
    df: pd.DataFrame,
    interval: str = DEFAULT_INTERVAL,
    price_basis: str = DEFAULT_PRICE_BASIS,
    source: str = "yfinance",
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
                "source": source,
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
        if interval == MINUTE_INTERVAL:
            logger.debug(
                "OHLCV DB cache skipped for %s [%s] (intraday; use in-process/Yahoo LTP path)",
                symbol,
                interval,
            )
            return None

        end_d = _parse_end_date(end_date)
        start_d = end_d - timedelta(days=days + 5)

        from core.data_fetcher import live_current_day_scope_allowed  # noqa: PLC0415

        include_live_today = live_current_day_scope_allowed(
            end_date=end_date,
            add_current_day=add_current_day,
            interval=interval,
        )

        bars_before = self.repo.get_range(symbol, start_d, end_d, interval=interval)
        missing = self.repo.get_dates_needing_gap_fill(
            symbol,
            start_d,
            end_d,
            interval=interval,
            tail_trading_days=self.tail_overlap_trading_days,
            min_coverage_pct=OHLCV_CACHE_MIN_COVERAGE_PCT,
        )
        if interval == DEFAULT_INTERVAL and daily_ohlcv_uses_nse() and missing:
            from src.application.services.nse_bhavcopy_availability import (  # noqa: PLC0415
                filter_nse_intraday_gap_dates,
            )

            missing = filter_nse_intraday_gap_dates(missing)
        coverage = self.repo.get_coverage_pct(symbol, start_d, end_d, interval=interval)
        if missing:
            if is_ohlcv_cache_read_only():
                log_ohlcv_cache(
                    logger,
                    "OHLCV read-only skip gap_fill %s [%s]: cached=%s gaps=%s coverage=%.1f%%",
                    symbol,
                    interval,
                    len(bars_before),
                    len(missing),
                    coverage,
                )
            else:
                log_ohlcv_cache(
                    logger,
                    "OHLCV gap_fill %s [%s]: cached=%s gaps=%s coverage=%.1f%% range=%s..%s",
                    symbol,
                    interval,
                    len(bars_before),
                    len(missing),
                    coverage,
                    start_d,
                    end_d,
                )
                self.gap_fill(
                    symbol,
                    start_d,
                    end_d,
                    interval=interval,
                    days=days,
                    yf_end_date=end_date,
                    add_current_day=include_live_today,
                )
        else:
            log_ohlcv_cache(
                logger,
                "OHLCV cache_hit %s [%s]: %s bars coverage=%.1f%% (yahoo_calls=%s)",
                symbol,
                interval,
                len(bars_before),
                coverage,
                get_ohlcv_cache_stats()["yahoo_calls"],
            )
            self._maybe_revalidate_partial_meta_on_cache_hit(
                symbol, start_d, end_d, interval, coverage
            )
            if include_live_today:
                if is_ohlcv_cache_read_only():
                    log_ohlcv_cache(
                        logger,
                        "OHLCV read-only skip today_refresh %s [%s]: cached=%s coverage=%.1f%%",
                        symbol,
                        interval,
                        len(bars_before),
                        coverage,
                    )
                else:
                    self._refresh_today_bar_from_yahoo(
                        symbol,
                        end_d,
                        interval=interval,
                        days=days,
                        yf_end_date=end_date,
                    )

        bars = self.repo.get_range(symbol, start_d, end_d, interval=interval)
        if not bars:
            return None

        bars = _filter_daily_bars_for_source_policy(
            bars, symbol=symbol, interval=interval
        )
        if not bars:
            logger.warning(
                "OHLCV no bars after source filter for %s [%s] (source=%s)",
                symbol,
                interval,
                OHLCV_DAILY_SOURCE,
            )
            return None

        meta = self.repo.get_symbol_meta(symbol, interval=interval)
        if meta and meta.fetch_status == "failed":
            logger.error(
                "OHLCV cache unusable for %s [%s]: last fetch failed — %s",
                symbol,
                interval,
                meta.last_validation_message or "unknown",
            )
            return None

        effective_start = self.repo.listing_aware_effective_start(symbol, start_d, end_d, interval)
        ok_history, history_msg = meets_indicator_history_requirement(
            interval=interval,
            bars_in_window=len(bars),
            effective_start=effective_start,
            end_date=end_d,
        )
        enforce_history = (
            interval == DEFAULT_INTERVAL
            and OHLCV_ENFORCE_INDICATOR_MIN_BARS
            and days >= OHLCV_MIN_DAILY_BARS_FOR_INDICATORS
        )
        if enforce_history and not ok_history:
            logger.error(
                "OHLCV insufficient history for %s [%s]: %s",
                symbol,
                interval,
                history_msg,
            )
            return None
        if (
            interval == DEFAULT_INTERVAL
            and meta
            and meta.fetch_status == "partial"
            and not ok_history
        ):
            logger.warning(
                "OHLCV partial history for %s [%s]: %s — %s",
                symbol,
                interval,
                history_msg,
                meta.last_validation_message or "",
            )

        df = _bars_to_dataframe(bars)
        if not include_live_today and not df.empty:
            df = df[df["date"].dt.date <= end_d]
        return df

    def _nse_ingest_allowed_for_today(self) -> bool:
        """True when same-day NSE bhavcopy ingest is allowed (post-close, ≥ earliest IST)."""
        from src.application.services.nse_bhavcopy_availability import (  # noqa: PLC0415
            nse_bhavcopy_ingest_allowed_for_today,
        )

        return nse_bhavcopy_ingest_allowed_for_today()

    def _refresh_today_bar_from_yahoo(
        self,
        symbol: str,
        end_d: date,
        *,
        interval: str,
        days: int,
        yf_end_date: str | datetime | None,
    ) -> int:
        """
        On cache hit with ``add_current_day=True``, upsert today's bar from Yahoo or NSE.

        Avoids serving a stale same-day row written earlier (e.g. pre-open gap-fill).
        Skips when ``end_d`` is before IST calendar today (backtests / historical end_date).
        Caller must gate with ``live_current_day_scope_allowed`` first.
        NSE path runs only after the ingest window (``NSE_BHAVCOPY_EARLIEST_IST``); earlier
        post-close skips (no synthetic today bar).
        """
        if is_ohlcv_cache_read_only():
            return 0
        if interval != DEFAULT_INTERVAL:
            return 0
        today_ist = ist_now().date()
        if end_d != today_ist:
            return 0

        if daily_ohlcv_uses_nse() and self._nse_ingest_allowed_for_today():
            from src.application.services.nse_bhavcopy_ingest_service import (  # noqa: PLC0415
                NseBhavcopyIngestService,
            )

            ingest = NseBhavcopyIngestService(self.db)
            count = ingest.ingest_trading_day(end_d, symbols=[symbol])
            if count:
                _bump_nse_days(1)
                log_ohlcv_cache(
                    logger,
                    "OHLCV today_refresh NSE upserted for %s [%s] date=%s",
                    symbol,
                    interval,
                    end_d,
                )
            return 1 if count else 0

        if daily_ohlcv_uses_nse() and not daily_ohlcv_yahoo_fallback():
            return 0

        try:
            fetched = self._yahoo_fetch(
                symbol,
                days=min(max(days, 5), 60),
                interval=interval,
                end_date=yf_end_date,
                add_current_day=True,
            )
        except Exception as exc:
            logger.warning(
                "OHLCV today_refresh Yahoo failed for %s [%s]: %s",
                symbol,
                interval,
                exc,
            )
            return 0

        if fetched is None or fetched.empty:
            return 0

        rows = _dataframe_to_upsert_rows(symbol, fetched, interval=interval)
        today_rows = [r for r in rows if r["date"] == end_d]
        if not today_rows:
            log_ohlcv_cache(
                logger,
                "OHLCV today_refresh %s [%s]: no Yahoo bar for %s (keeping cached history)",
                symbol,
                interval,
                end_d,
            )
            return 0

        validation = validate_yahoo_ohlcv_frame(
            fetched,
            symbol=symbol,
            interval=interval,
            start_date=end_d,
            end_date=end_d,
        )
        if validation.status == "failed" and OHLCV_REJECT_INVALID_FETCH:
            logger.warning(
                "OHLCV today_refresh rejected for %s [%s]: %s",
                symbol,
                interval,
                validation.message,
            )
            return 0

        count = self.repo.upsert_many(today_rows)
        if count:
            log_ohlcv_cache(
                logger,
                "OHLCV today_refresh upserted %s row(s) for %s [%s] date=%s (yahoo_calls=%s)",
                count,
                symbol,
                interval,
                end_d,
                get_ohlcv_cache_stats()["yahoo_calls"],
            )
        return count

    def _maybe_revalidate_partial_meta_on_cache_hit(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        interval: str,
        coverage_pct: float,
    ) -> None:
        """Upgrade stale ``partial`` meta when listing-aware coverage is now adequate."""
        meta = self.repo.get_symbol_meta(symbol, interval=interval)
        if meta is None or meta.fetch_status != "partial":
            return
        if coverage_pct < OHLCV_CACHE_MIN_COVERAGE_PCT:
            return
        post = validate_cached_symbol(self.repo, symbol, start_date, end_date, interval=interval)
        if post.status == "failed":
            logger.debug(
                "OHLCV meta revalidate skipped for %s [%s]: %s",
                symbol,
                interval,
                post.message,
            )
            return
        self.repo.record_fetch_validation(
            symbol,
            interval,
            fetch_status=post.status,
            coverage_pct=post.coverage_pct,
            message=post.message,
        )
        if post.status == "ok":
            log_ohlcv_cache(
                logger,
                "OHLCV meta revalidated %s [%s]: partial -> ok (coverage=%.1f%%)",
                symbol,
                interval,
                post.coverage_pct,
            )

    def _gap_fill_nse(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        *,
        interval: str = DEFAULT_INTERVAL,
    ) -> int:
        """Gap-fill daily bars from NSE bhavcopy."""
        from src.application.services.nse_bhavcopy_ingest_service import (  # noqa: PLC0415
            NseBhavcopyIngestService,
        )

        ingest = NseBhavcopyIngestService(self.db)
        count = ingest.fill_symbol_range(symbol, start_date, end_date)
        trading_days = sum(1 for _ in iter_trading_days(start_date, end_date))
        if trading_days:
            _bump_nse_days(trading_days)
        log_ohlcv_cache(
            logger,
            "OHLCV gap_fill NSE upserted %s rows for %s [%s] (%s to %s, nse_days=%s)",
            count,
            symbol,
            interval,
            start_date,
            end_date,
            get_ohlcv_cache_stats()["nse_bhavcopy_days_fetched"],
        )
        return count

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
        Fetch missing range from NSE (daily 1d) or Yahoo and upsert into cache.

        Returns:
            Number of rows upserted.
        """
        if is_ohlcv_cache_read_only():
            logger.warning(
                "OHLCV gap_fill blocked (read-only trading context) for %s [%s] %s..%s",
                symbol,
                interval,
                start_date,
                end_date,
            )
            return 0

        if interval == MINUTE_INTERVAL:
            logger.debug(
                "gap_fill skipped for %s [%s] (intraday not stored in price_cache)",
                symbol,
                interval,
            )
            return 0

        if interval == DEFAULT_INTERVAL and daily_ohlcv_uses_nse():
            nse_count = self._gap_fill_nse(
                symbol, start_date, end_date, interval=interval
            )
            if nse_count > 0 or not daily_ohlcv_yahoo_fallback():
                return nse_count
            logger.warning(
                "OHLCV gap_fill NSE returned 0 for %s [%s]; falling back to Yahoo",
                symbol,
                interval,
            )

        lookback = days if days is not None else (end_date - start_date).days + 30
        try:
            fetched = self._yahoo_fetch(
                symbol,
                days=lookback,
                interval=interval,
                end_date=yf_end_date,
                add_current_day=add_current_day,
            )
        except Exception as exc:
            self.repo.record_fetch_validation(
                symbol,
                interval,
                fetch_status="failed",
                coverage_pct=None,
                message=f"Yahoo API error: {exc}",
            )
            logger.error("gap_fill Yahoo API failed for %s [%s]: %s", symbol, interval, exc)
            return 0

        validation = validate_yahoo_ohlcv_frame(
            fetched,
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
        )
        if validation.status == "failed" and OHLCV_REJECT_INVALID_FETCH:
            self.repo.record_fetch_validation(
                symbol,
                interval,
                fetch_status="failed",
                coverage_pct=validation.coverage_pct,
                message=validation.message,
            )
            logger.error("gap_fill rejected for %s [%s]: %s", symbol, interval, validation.message)
            return 0

        rows = _dataframe_to_upsert_rows(symbol, fetched, interval=interval)
        filtered = [r for r in rows if start_date <= r["date"] <= end_date]
        if not filtered:
            self.repo.record_fetch_validation(
                symbol,
                interval,
                fetch_status="failed",
                coverage_pct=0.0,
                message="Yahoo returned no rows in requested window",
            )
            return 0

        count = self.repo.upsert_many(filtered)
        self.repo.refresh_symbol_meta(symbol, interval=interval)
        post = validate_cached_symbol(self.repo, symbol, start_date, end_date, interval=interval)
        self.repo.record_fetch_validation(
            symbol,
            interval,
            fetch_status=post.status,
            coverage_pct=post.coverage_pct,
            message=post.message,
        )
        log_ohlcv_cache(
            logger,
            "OHLCV gap_fill upserted %s rows for %s [%s] (%s to %s, yahoo_calls=%s)",
            count,
            symbol,
            interval,
            start_date,
            end_date,
            get_ohlcv_cache_stats()["yahoo_calls"],
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

        if interval == DEFAULT_INTERVAL and daily_ohlcv_uses_nse():
            return self._gap_fill_nse(symbol, start_d, end_d, interval=interval)

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
        """Delete cached bars and reset symbol meta (delegates to repository)."""
        return self.repo.invalidate_symbol(symbol, interval=interval)

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
