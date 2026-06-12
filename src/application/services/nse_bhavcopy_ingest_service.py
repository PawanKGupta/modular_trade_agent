"""Ingest NSE UDiFF bhavcopy rows into ``price_cache`` (``source=nse``)."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from config.settings import OHLCV_REJECT_INVALID_FETCH
from src.application.services.nse_bhavcopy_availability import (
    filter_nse_intraday_gap_dates,
    nse_bhavcopy_ingest_allowed_for_date,
    nse_bhavcopy_ingest_allowed_for_today,
)
from src.application.services.ohlcv_fetch_validation import validate_yahoo_ohlcv_frame
from src.infrastructure.data_providers.nse_bhavcopy_fetcher import (
    NseBhavcopyFetcher,
    NseEquityBar,
    find_equity_bar,
)
from src.infrastructure.data_providers.nse_symbol import (
    base_from_cache_ticker,
    ensure_cache_ticker,
    to_cache_ticker,
)
from src.infrastructure.persistence.price_cache_repository import (
    DEFAULT_INTERVAL,
    DEFAULT_PRICE_BASIS,
    PriceCacheRepository,
)
from utils.logger import logger

NSE_SOURCE = "nse"

# Re-export for callers/tests that imported from this module.
from src.application.services.nse_bhavcopy_availability import (  # noqa: E402
    nse_bhavcopy_eod_available,
)

__all__ = [
    "NseBhavcopyIngestService",
    "NSE_SOURCE",
    "filter_nse_intraday_gap_dates",
    "nse_bhavcopy_eod_available",
    "nse_bhavcopy_ingest_allowed_for_date",
    "nse_bhavcopy_ingest_allowed_for_today",
]


def _bar_to_upsert_row(cache_ticker: str, bar: NseEquityBar) -> dict:
    return {
        "symbol": cache_ticker,
        "date": bar.trade_date,
        "interval": DEFAULT_INTERVAL,
        "price_basis": DEFAULT_PRICE_BASIS,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "source": NSE_SOURCE,
    }


class NseBhavcopyIngestService:
    """Write NSE daily OHLCV into Postgres/SQLite ``price_cache``."""

    def __init__(
        self,
        db: Session,
        fetcher: NseBhavcopyFetcher | None = None,
    ):
        self.db = db
        self.repo = PriceCacheRepository(db)
        self.fetcher = fetcher or NseBhavcopyFetcher()

    def fill_symbol_range(self, ticker: str, start_date: date, end_date: date) -> int:
        """
        Upsert NSE bhavcopy bars for one symbol across trading days in [start, end].

        Returns:
            Number of rows upserted.
        """
        cache_ticker = ensure_cache_ticker(ticker)
        if not cache_ticker:
            logger.error("NSE ingest: invalid ticker %s", ticker)
            return 0

        base = base_from_cache_ticker(cache_ticker)
        total = 0
        missing_days = 0

        days_to_fetch = filter_nse_intraday_gap_dates(
            self.repo.get_missing_trading_dates(
                cache_ticker, start_date, end_date, interval=DEFAULT_INTERVAL
            )
        )
        if not days_to_fetch:
            logger.info(
                "NSE fill_symbol_range %s: no missing trading days in [%s, %s]; skipping bhavcopy fetch",
                cache_ticker,
                start_date,
                end_date,
            )
            self.repo.refresh_symbol_meta(cache_ticker, interval=DEFAULT_INTERVAL)
            from src.application.services.ohlcv_fetch_validation import validate_cached_symbol

            post = validate_cached_symbol(
                self.repo, cache_ticker, start_date, end_date, interval=DEFAULT_INTERVAL
            )
            self.repo.record_fetch_validation(
                cache_ticker,
                DEFAULT_INTERVAL,
                fetch_status=post.status,
                coverage_pct=post.coverage_pct,
                message=post.message,
            )
            return 0

        for trade_day in days_to_fetch:
            df = self.fetcher.download_bhavcopy(trade_day)
            if df is None or df.empty:
                missing_days += 1
                continue
            bar = find_equity_bar(df, base)
            if bar is None:
                missing_days += 1
                continue
            row = _bar_to_upsert_row(cache_ticker, bar)
            frame = _rows_to_frame([row])
            validation = validate_yahoo_ohlcv_frame(
                frame,
                symbol=cache_ticker,
                interval=DEFAULT_INTERVAL,
                start_date=trade_day,
                end_date=trade_day,
            )
            if validation.status == "failed" and OHLCV_REJECT_INVALID_FETCH:
                logger.warning(
                    "NSE ingest rejected bar for %s on %s: %s",
                    cache_ticker,
                    trade_day,
                    validation.message,
                )
                continue
            total += self.repo.upsert_many([row])

        self.repo.refresh_symbol_meta(cache_ticker, interval=DEFAULT_INTERVAL)
        from src.application.services.ohlcv_fetch_validation import validate_cached_symbol

        post = validate_cached_symbol(
            self.repo, cache_ticker, start_date, end_date, interval=DEFAULT_INTERVAL
        )
        self.repo.record_fetch_validation(
            cache_ticker,
            DEFAULT_INTERVAL,
            fetch_status=post.status,
            coverage_pct=post.coverage_pct,
            message=post.message
            if post.status != "failed"
            else f"NSE ingest: {missing_days} trading day(s) without bhavcopy row; {post.message}",
        )
        logger.info(
            "NSE fill_symbol_range %s: upserted=%s missing_days=%s status=%s",
            cache_ticker,
            total,
            missing_days,
            post.status,
        )
        return total

    def ingest_trading_day(
        self,
        trade_date: date,
        symbols: list[str] | None = None,
        *,
        all_equity: bool = False,
    ) -> int:
        """
        Ingest one bhavcopy file for ``trade_date``.

        Args:
            trade_date: Calendar date of bhavcopy file.
            symbols: Cache tickers (``*.NS``) or bases to upsert; if None and ``all_equity``,
                upsert every EQ row (use with care).
            all_equity: When True and ``symbols`` is None, ingest all EQ symbols from file.

        Returns:
            Rows upserted.
        """
        if symbols is None and not all_equity:
            raise ValueError("Provide symbols or set all_equity=True")

        if not nse_bhavcopy_ingest_allowed_for_date(trade_date):
            logger.debug(
                "NSE ingest_trading_day: skipping %s (ingest not allowed yet for calendar today)",
                trade_date,
            )
            return 0

        df = self.fetcher.download_bhavcopy(trade_date)
        if df is None or df.empty:
            logger.warning("NSE ingest_trading_day: no bhavcopy for %s", trade_date)
            return 0

        from src.infrastructure.data_providers.nse_bhavcopy_fetcher import parse_equity_bars

        if symbols is not None:
            bases = {base_from_cache_ticker(ensure_cache_ticker(s)) for s in symbols}
            bars = [b for b in parse_equity_bars(df) if b.tckr_symb.upper() in bases]
        else:
            bars = parse_equity_bars(df)

        rows = [_bar_to_upsert_row(to_cache_ticker(b.tckr_symb), b) for b in bars]
        if not rows:
            return 0
        count = self.repo.upsert_many(rows)
        tickers = {r["symbol"] for r in rows}
        for t in tickers:
            self.repo.refresh_symbol_meta(t, interval=DEFAULT_INTERVAL)
        logger.info("NSE ingest_trading_day %s: upserted %s rows for %s symbols", trade_date, count, len(tickers))
        return count


def _rows_to_frame(rows: list[dict]):
    import pandas as pd

    if not rows:
        return pd.DataFrame()
    data = []
    for r in rows:
        data.append(
            {
                "date": r["date"],
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
                "volume": r.get("volume") or 0,
            }
        )
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    return df
