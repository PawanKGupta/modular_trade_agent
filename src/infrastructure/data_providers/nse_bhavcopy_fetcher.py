"""
NSE UDiFF daily bhavcopy fetcher (capital market EOD ``_F_0000`` files).

Downloads one zip per calendar day, caches CSV on disk, parses tradeable equity OHLCV rows.
"""

from __future__ import annotations

import io
import time
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import urllib.error
import urllib.request

from config.settings import (
    NSE_BHAVCOPY_CACHE_DIR,
    NSE_BHAVCOPY_EQUITY_SERIES,
    NSE_BHAVCOPY_REQUEST_DELAY_S,
    NSE_BHAVCOPY_REQUEST_TIMEOUT_S,
    NSE_BHAVCOPY_USE_DISK_CACHE,
)
from utils.logger import logger

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nseindia.com/",
    "Accept": "*/*",
}

SYM_COL = "TckrSymb"
SERIES_COL = "SctySrs"
DATE_COL_PRIMARY = "TradDt"
DATE_COL_FALLBACK = "BizDt"
OPEN_COL = "OpnPric"
HIGH_COL = "HghPric"
LOW_COL = "LwPric"
CLOSE_COL = "ClsPric"
VOLUME_COL = "TtlTradgVol"

# When duplicate ``TckrSymb`` rows exist (rare), prefer regular EQ listing.
NSE_EQUITY_SERIES_PREFERENCE = ("EQ", "BE", "BL", "BZ")


def _normalize_series(value: Any) -> str:
    return str(value or "").strip().upper()


def _is_allowed_equity_series(series: Any) -> bool:
    return _normalize_series(series) in NSE_BHAVCOPY_EQUITY_SERIES


@dataclass(frozen=True)
class NseEquityBar:
    """Single tradeable equity bar from NSE bhavcopy (EQ/BE/BL/BZ series)."""

    tckr_symb: str
    trade_date: date
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: int | None


def bhavcopy_url(trade_date: date) -> str:
    """UDiFF final bhavcopy URL for a calendar date."""
    ymd = trade_date.strftime("%Y%m%d")
    return (
        f"https://nsearchives.nseindia.com/content/cm/"
        f"BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip"
    )


def _safe_float(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _row_to_bar(row: pd.Series, *, date_col: str) -> NseEquityBar | None:
    sym = str(row[SYM_COL]).strip()
    if not sym:
        return None
    close = _safe_float(row.get(CLOSE_COL))
    if close is None:
        return None
    try:
        trade_date = pd.to_datetime(row[date_col]).date()
    except (TypeError, ValueError):
        return None
    return NseEquityBar(
        tckr_symb=sym,
        trade_date=trade_date,
        open=_safe_float(row.get(OPEN_COL)),
        high=_safe_float(row.get(HIGH_COL)),
        low=_safe_float(row.get(LOW_COL)),
        close=close,
        volume=_safe_int(row.get(VOLUME_COL)),
    )


def parse_equity_bars(df: pd.DataFrame) -> list[NseEquityBar]:
    """
    Parse tradeable equity rows from a bhavcopy DataFrame.

    Includes ``SctySrs`` in ``NSE_BHAVCOPY_EQUITY_SERIES`` (default EQ, BE, BL, BZ).

    Args:
        df: Raw CSV loaded from NSE zip.

    Returns:
        List of parsed equity bars (one per ``TckrSymb`` when duplicates exist, first wins).
    """
    if df is None or df.empty or SYM_COL not in df.columns or CLOSE_COL not in df.columns:
        return []

    date_col = DATE_COL_PRIMARY if DATE_COL_PRIMARY in df.columns else DATE_COL_FALLBACK
    if date_col not in df.columns:
        return []

    work = df
    if SERIES_COL in work.columns:
        work = work[work[SERIES_COL].map(_is_allowed_equity_series)]

    seen: set[str] = set()
    bars: list[NseEquityBar] = []
    for _, row in work.iterrows():
        sym = str(row[SYM_COL]).strip()
        if not sym or sym in seen:
            continue
        bar = _row_to_bar(row, date_col=date_col)
        if bar is None:
            continue
        seen.add(sym)
        bars.append(bar)
    return bars


def find_equity_bar(df: pd.DataFrame, tckr_symb: str) -> NseEquityBar | None:
    """Return the tradeable equity bar for ``tckr_symb`` on this bhavcopy file, if present."""
    if df is None or df.empty or SYM_COL not in df.columns or CLOSE_COL not in df.columns:
        return None

    date_col = DATE_COL_PRIMARY if DATE_COL_PRIMARY in df.columns else DATE_COL_FALLBACK
    if date_col not in df.columns:
        return None

    base = tckr_symb.strip().upper()
    rows = df[df[SYM_COL].astype(str).str.upper().eq(base)]
    if rows.empty:
        return None

    if SERIES_COL in rows.columns:
        allowed = rows[rows[SERIES_COL].map(_is_allowed_equity_series)]
        if allowed.empty:
            return None
        rows = allowed
        for pref in NSE_EQUITY_SERIES_PREFERENCE:
            if pref not in NSE_BHAVCOPY_EQUITY_SERIES:
                continue
            match = rows[rows[SERIES_COL].map(_normalize_series).eq(pref)]
            if not match.empty:
                return _row_to_bar(match.iloc[0], date_col=date_col)

    return _row_to_bar(rows.iloc[0], date_col=date_col)


class NseBhavcopyFetcher:
    """Download and cache NSE UDiFF bhavcopy files."""

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        *,
        request_delay_s: float | None = None,
        request_timeout_s: float | None = None,
    ):
        self.cache_dir = Path(cache_dir or NSE_BHAVCOPY_CACHE_DIR)
        self.request_delay_s = (
            NSE_BHAVCOPY_REQUEST_DELAY_S if request_delay_s is None else request_delay_s
        )
        self.request_timeout_s = (
            NSE_BHAVCOPY_REQUEST_TIMEOUT_S
            if request_timeout_s is None
            else request_timeout_s
        )
        self.use_disk_cache = NSE_BHAVCOPY_USE_DISK_CACHE
        self._last_request_at = 0.0

    def _cache_path(self, trade_date: date) -> Path:
        return self.cache_dir / f"bhav_{trade_date.strftime('%Y%m%d')}.csv"

    def _enforce_delay(self) -> None:
        if self.request_delay_s <= 0:
            return
        elapsed = time.time() - self._last_request_at
        if elapsed < self.request_delay_s:
            time.sleep(self.request_delay_s - elapsed)
        self._last_request_at = time.time()

    def _http_get(self, url: str, *, retry_on_403: bool = True) -> bytes | None:
        self._enforce_delay()
        req = urllib.request.Request(url, headers=NSE_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout_s) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 400):
                logger.debug("NSE bhavcopy not available for %s: HTTP %s", url, exc.code)
                return None
            if exc.code == 403 and retry_on_403:
                logger.warning("NSE bhavcopy HTTP 403, retrying once: %s", url)
                time.sleep(1.0)
                return self._http_get(url, retry_on_403=False)
            raise
        except urllib.error.URLError as exc:
            logger.warning("NSE bhavcopy network error for %s: %s", url, exc)
            return None

    def download_bhavcopy(
        self, trade_date: date, *, use_disk_cache: bool | None = None
    ) -> pd.DataFrame | None:
        """
        Load bhavcopy CSV for ``trade_date`` (optional disk cache or HTTP download).

        When disk cache is disabled, parses the NSE zip in memory and does not write CSV.

        Returns:
            DataFrame or None if file unavailable (holiday / not published).
        """
        use_disk = self.use_disk_cache if use_disk_cache is None else use_disk_cache
        cache_path = self._cache_path(trade_date)
        if use_disk and cache_path.exists():
            try:
                return pd.read_csv(cache_path)
            except Exception as exc:
                logger.warning("Corrupt NSE cache %s: %s", cache_path, exc)
                cache_path.unlink(missing_ok=True)

        url = bhavcopy_url(trade_date)
        raw = self._http_get(url)
        if raw is None:
            return None

        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            name = zf.namelist()[0]
            df = pd.read_csv(zf.open(name))

        if use_disk:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache_path, index=False)
        return df
