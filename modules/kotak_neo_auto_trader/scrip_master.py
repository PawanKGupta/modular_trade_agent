#!/usr/bin/env python3
"""
Kotak Neo Scrip Master Handler

Downloads and manages the scrip master file containing instrument tokens,
symbols, and other metadata required for accurate order placement and quotes.
"""

import json
import sys
import csv
from io import StringIO
from datetime import datetime
from pathlib import Path

import requests

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger

try:
    from . import config
except ImportError:
    pass


class KotakNeoScripMaster:
    """
    Manages Kotak Neo scrip master data for instrument lookups
    """

    EXCHANGE_SEGMENT_MAP = {
        "NSE": "nse_cm",
        "BSE": "bse_cm",
        "NFO": "nse_fo",
        "BFO": "bse_fo",
        "CDS": "cde_fo",
        "MCX": "mcx_fo",
    }

    def __init__(
        self, cache_dir: str = "data/scrip_master", exchanges: list[str] = None, auth_client=None
    ):
        """
        Initialize scrip master handler

        Args:
            cache_dir: Directory to cache scrip master files
            exchanges: List of exchanges to download (default: ['NSE'])
            auth_client: Authenticated Kotak Neo client for API access
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.exchanges = exchanges or ["NSE"]
        self.auth_client = auth_client
        self.scrip_data: dict[str, list[dict]] = {}
        self.symbol_map: dict[str, dict] = {}  # Quick lookup: symbol -> instrument data

        logger.info(f"KotakNeoScripMaster initialized for exchanges: {self.exchanges}")

    def _get_cache_path(self, exchange: str, date_str: str = None) -> Path:
        """Get cache file path for an exchange and date"""
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")
        return self.cache_dir / f"scrip_master_{exchange}_{date_str}.json"

    def _find_latest_cache_file(self, exchange: str) -> Path | None:
        """
        Find the latest available cache file for an exchange.
        Looks for files matching pattern: scrip_master_{exchange}_YYYYMMDD.json

        Returns:
            Path to latest cache file, or None if no cache files found
        """
        pattern = f"scrip_master_{exchange}_*.json"
        cache_files = list(self.cache_dir.glob(pattern))

        if not cache_files:
            return None

        # Sort by modification time (newest first)
        cache_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Return the most recent file
        latest_file = cache_files[0]
        logger.debug(f"Found latest cache file for {exchange}: {latest_file.name}")
        return latest_file

    def _is_cache_valid(self, exchange: str) -> bool:
        """Check if today's cached scrip master is valid"""
        cache_path = self._get_cache_path(exchange)

        if not cache_path.exists():
            return False

        # Check if file is from today
        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
                cache_date = data.get("download_date", "")
                if cache_date == datetime.now().strftime("%Y-%m-%d"):
                    return True
        except Exception as e:
            logger.warning(f"Error reading cache for {exchange}: {e}")

        return False

    def _cleanup_old_cache_files(self, exchange: str, keep_days: int = 5):
        """
        Clean up old cache files, keeping only the latest N days.

        Args:
            exchange: Exchange name
            keep_days: Number of days to keep (default: 5)
        """
        try:
            pattern = f"scrip_master_{exchange}_*.json"
            cache_files = list(self.cache_dir.glob(pattern))

            if len(cache_files) <= keep_days:
                return  # No cleanup needed

            # Sort by modification time (newest first)
            cache_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            # Keep the latest N files, delete the rest
            files_to_keep = cache_files[:keep_days]
            files_to_delete = cache_files[keep_days:]

            for file_to_delete in files_to_delete:
                try:
                    file_to_delete.unlink()
                    logger.debug(f"Deleted old cache file: {file_to_delete.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete old cache file {file_to_delete.name}: {e}")

            if files_to_delete:
                logger.info(
                    f"Cleaned up {len(files_to_delete)} old cache files for {exchange}, "
                    f"kept {len(files_to_keep)} latest files"
                )
        except Exception as e:
            logger.warning(f"Error cleaning up old cache files for {exchange}: {e}")

    def _download_scrip_master(self, exchange: str, auth_client=None) -> list[dict] | None:
        """
        Download scrip master file from Kotak Neo API

        Args:
            exchange: Exchange name (NSE, BSE, NFO, CDS)
            auth_client: Authenticated Kotak Neo client (optional)

        Returns:
            List of instrument dictionaries or None if failed
        """
        try:
            logger.info(f"Downloading scrip master for {exchange} via Kotak Neo API...")
            client = auth_client or self.auth_client
            if client is None or not hasattr(client, "get_scripmaster_file_paths"):
                logger.error(f"Cannot download scrip master for {exchange}: auth client required")
                logger.error(
                    "Scrip Master must be loaded from "
                    "/script-details/1.0/masterscrip/file-paths using authenticated REST client."
                )
                return None

            file_paths_resp = client.get_scripmaster_file_paths()
            file_url = self._resolve_csv_url_for_exchange(exchange, file_paths_resp)
            if not file_url:
                logger.error(f"No matching scrip master file URL found for exchange: {exchange}")
                return None

            logger.info(f"Fetching scrip master for {exchange} from: {file_url}")
            resp = requests.get(file_url, timeout=30)
            resp.raise_for_status()
            text = resp.text

            if not text.strip():
                logger.error(f"Empty scrip master content for {exchange}")
                return None

            sample = "\n".join(text.splitlines()[:20])
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",|;\t")
                delimiter = dialect.delimiter
            except Exception:
                delimiter = ","

            reader = csv.DictReader(StringIO(text), delimiter=delimiter)
            instruments = [{k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()} for row in reader]

            if not instruments:
                logger.error(f"No instruments parsed from scrip master for {exchange}")
                return None

            logger.info(f"Downloaded {len(instruments)} instruments for {exchange}")
            return instruments

        except requests.RequestException as e:
            logger.error(f"Failed to download scrip master for {exchange}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing scrip master for {exchange}: {e}")
            return None

    def _resolve_csv_url_for_exchange(self, exchange: str, payload: dict | list | None) -> str | None:
        """Resolve exchange-specific CSV URL from /masterscrip/file-paths response."""
        seg = self.EXCHANGE_SEGMENT_MAP.get(str(exchange).upper())
        if not seg:
            return None

        files_paths: list[str] = []
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, dict):
                fp = data.get("filesPaths")
                if isinstance(fp, list):
                    files_paths = [str(x) for x in fp if isinstance(x, str)]
            # support alternate/top-level shapes defensively
            if not files_paths:
                fp = payload.get("filesPaths")
                if isinstance(fp, list):
                    files_paths = [str(x) for x in fp if isinstance(x, str)]
        elif isinstance(payload, list):
            files_paths = [str(x) for x in payload if isinstance(x, str)]

        if not files_paths:
            return None

        # Prefer exact segment tokens in path; supports both *-v1.csv and .csv variants.
        seg_tokens = [f"/{seg}.csv", f"/{seg}-v1.csv", f"{seg}.csv", f"{seg}-v1.csv"]
        for url in files_paths:
            low = url.lower()
            if any(tok in low for tok in seg_tokens):
                return url
        return None

    def _save_to_cache(self, exchange: str, instruments: list[dict]) -> bool:
        """Save scrip master data to cache"""
        try:
            cache_path = self._get_cache_path(exchange)

            cache_data = {
                "exchange": exchange,
                "download_date": datetime.now().strftime("%Y-%m-%d"),
                "download_timestamp": datetime.now().isoformat(),
                "instrument_count": len(instruments),
                "instruments": instruments,
            }

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2)

            logger.info(f"Cached {len(instruments)} instruments for {exchange}")
            return True

        except Exception as e:
            logger.error(f"Error saving cache for {exchange}: {e}")
            return False

    def _load_from_cache(self, exchange: str, cache_path: Path = None) -> list[dict] | None:
        """
        Load scrip master data from cache.

        Args:
            exchange: Exchange name
            cache_path: Optional specific cache file path. If None, uses today's cache or latest available.

        Returns:
            List of instruments or None if failed
        """
        try:
            # If no specific path provided, try today's cache first, then latest available
            if cache_path is None:
                cache_path = self._get_cache_path(exchange)

                # If today's cache doesn't exist, try to find latest available
                if not cache_path.exists():
                    latest_cache = self._find_latest_cache_file(exchange)
                    if latest_cache:
                        cache_path = latest_cache
                        logger.info(
                            f"Today's cache not available for {exchange}, "
                            f"using latest available: {cache_path.name}"
                        )
                    else:
                        logger.warning(f"No cache files found for {exchange}")
                        return None

            if not cache_path.exists():
                return None

            with open(cache_path, encoding="utf-8") as f:
                cache_data = json.load(f)

            instruments = cache_data.get("instruments", [])
            cache_date = cache_data.get("download_date", "unknown")
            logger.info(
                f"Loaded {len(instruments)} instruments for {exchange} from cache "
                f"(date: {cache_date}, file: {cache_path.name})"
            )
            return instruments

        except Exception as e:
            logger.error(f"Error loading cache for {exchange} from {cache_path}: {e}")
            return None

    def load_scrip_master(self, force_download: bool = False) -> bool:
        """
        Load scrip master data for configured exchanges.

        Strategy:
        1. If force_download: Download fresh data
        2. If today's cache exists: Use today's cache
        3. If today's cache not available: Use latest available cache file
        4. If no cache available: Download fresh data
        5. Clean up old cache files (keep latest 5 days)

        Args:
            force_download: Force fresh download even if cache exists

        Returns:
            True if successful (at least one exchange loaded)
        """
        success = True
        at_least_one_loaded = False

        for exchange in self.exchanges:
            instruments = None

            if force_download:
                # Force fresh download
                logger.info(f"Force downloading scrip master for {exchange}...")
                instruments = self._download_scrip_master(exchange, auth_client=self.auth_client)
                if instruments:
                    self._save_to_cache(exchange, instruments)
                    # Clean up old files after saving new one
                    self._cleanup_old_cache_files(exchange, keep_days=5)
            elif self._is_cache_valid(exchange):
                # Today's cache is available
                instruments = self._load_from_cache(exchange)
                # Clean up old files even when using today's cache
                if instruments:
                    self._cleanup_old_cache_files(exchange, keep_days=5)
            else:
                # Today's cache not available, try latest available
                logger.info(
                    f"Today's cache not available for {exchange}, "
                    f"looking for latest available cache file..."
                )
                latest_cache = self._find_latest_cache_file(exchange)

                if latest_cache:
                    # Use latest available cache
                    instruments = self._load_from_cache(exchange, cache_path=latest_cache)
                    if instruments:
                        logger.info(
                            f"Using latest available cache for {exchange}: {latest_cache.name}. "
                            f"Will attempt to download fresh data in background."
                        )
                        # Try to download fresh data in background (non-blocking)
                        try:
                            fresh_instruments = self._download_scrip_master(
                                exchange, auth_client=self.auth_client
                            )
                            if fresh_instruments:
                                self._save_to_cache(exchange, fresh_instruments)
                                # Use fresh data if download succeeded
                                instruments = fresh_instruments
                                logger.info(
                                    f"Successfully downloaded fresh scrip master for {exchange}"
                                )
                        except Exception as e:
                            logger.debug(
                                f"Background download failed for {exchange}: {e}, using cached data"
                            )
                else:
                    # No cache available, must download
                    logger.info(f"No cache files found for {exchange}, downloading fresh data...")
                    instruments = self._download_scrip_master(
                        exchange, auth_client=self.auth_client
                    )
                    if instruments:
                        self._save_to_cache(exchange, instruments)

            if instruments:
                self.scrip_data[exchange] = instruments
                self._build_symbol_map(exchange, instruments)
                at_least_one_loaded = True
                # Clean up old cache files after successful load
                self._cleanup_old_cache_files(exchange, keep_days=5)
            else:
                logger.error(f"Failed to load scrip master for {exchange}")
                success = False

        # Return True if at least one exchange loaded successfully
        return at_least_one_loaded

    def _build_symbol_map(self, exchange: str, instruments: list[dict]):
        """Build quick lookup map for symbols"""
        for instrument in instruments:
            # Extract relevant fields - pTrdSymbol is the trading symbol (e.g. GLENMARK-EQ)
            # pSymbol is numeric ID in Kotak's new format
            trading_symbol = (
                instrument.get("pTrdSymbol")
                or instrument.get("symbol")
                or instrument.get("tradingSymbol")
            )
            token = (
                instrument.get("pSymbol")
                or instrument.get("instrumentToken")
                or instrument.get("token")
            )

            # Extract tick size from scrip master (dTickSize is in paise, convert to rupees)
            tick_size_paise = instrument.get("dTickSize", "-1")
            tick_size = None
            if tick_size_paise and tick_size_paise != "-1":
                try:
                    # dTickSize is in paise, convert to rupees (divide by 100)
                    tick_size = float(tick_size_paise) / 100.0
                except (ValueError, TypeError):
                    tick_size = None

            if trading_symbol:
                # Store with exchange prefix for uniqueness
                key = f"{exchange}:{trading_symbol}"
                self.symbol_map[key] = {
                    "exchange": exchange,
                    "symbol": trading_symbol,  # This is the trading symbol like GLENMARK-EQ
                    "token": token,
                    "tick_size": tick_size,  # Tick size in rupees (from dTickSize in paise)
                    "instrument": instrument,
                }

                # Also store without exchange for convenience (NSE only)
                if exchange == "NSE" and trading_symbol not in self.symbol_map:
                    self.symbol_map[trading_symbol] = self.symbol_map[key]

                # Also store base symbol without suffix (e.g., GLENMARK from GLENMARK-EQ)
                base_symbol = trading_symbol.split("-")[0]
                if exchange == "NSE" and base_symbol not in self.symbol_map:
                    self.symbol_map[base_symbol] = self.symbol_map[key]

    def get_instrument(self, symbol: str, exchange: str = "NSE") -> dict | None:
        """
        Get instrument data for a symbol

        Args:
            symbol: Trading symbol (e.g., 'RELIANCE-EQ', 'INFY-EQ')
            exchange: Exchange (default: NSE)

        Returns:
            Instrument data dict or None
        """
        # Try with exchange prefix first
        key = f"{exchange}:{symbol}"
        if key in self.symbol_map:
            return self.symbol_map[key]

        # Try without exchange
        if symbol in self.symbol_map:
            return self.symbol_map[symbol]

        # Try removing suffix (-EQ, -BE, etc.)
        base_symbol = symbol.split("-")[0]
        if base_symbol in self.symbol_map:
            return self.symbol_map[base_symbol]

        key = f"{exchange}:{base_symbol}"
        if key in self.symbol_map:
            return self.symbol_map[key]

        logger.warning(f"Instrument not found: {symbol} ({exchange})")
        return None

    def get_token(self, symbol: str, exchange: str = "NSE") -> str | None:
        """Get instrument token for a symbol"""
        instrument = self.get_instrument(symbol, exchange)
        return instrument["token"] if instrument else None

    def get_trading_symbol(self, symbol: str, exchange: str = "NSE") -> str | None:
        """Get correct trading symbol for order placement"""
        instrument = self.get_instrument(symbol, exchange)
        return instrument["symbol"] if instrument else None

    def get_tick_size(self, symbol: str, exchange: str = "NSE") -> float | None:
        """
        Get tick size for a symbol from scrip master.

        Args:
            symbol: Trading symbol (e.g., 'RELIANCE-EQ', 'INFY-EQ')
            exchange: Exchange (default: NSE)

        Returns:
            Tick size in rupees, or None if not found or invalid
        """
        instrument = self.get_instrument(symbol, exchange)
        if instrument:
            tick_size = instrument.get("tick_size")
            # Only return if tick_size is valid (not None and > 0)
            if tick_size is not None and tick_size > 0:
                return tick_size
        return None

    def search_instruments(self, keyword: str, exchange: str = None) -> list[dict]:
        """
        Search for instruments by keyword

        Args:
            keyword: Search keyword
            exchange: Filter by exchange (optional)

        Returns:
            List of matching instruments
        """
        keyword_upper = keyword.upper()
        results = []

        for key, data in self.symbol_map.items():
            if exchange and data["exchange"] != exchange:
                continue

            symbol = data["symbol"].upper()
            if keyword_upper in symbol:
                results.append(data)

        return results


def initialize_scrip_master(force_download: bool = False) -> KotakNeoScripMaster:
    """
    Initialize and load scrip master data

    Args:
        force_download: Force fresh download

    Returns:
        Initialized KotakNeoScripMaster instance
    """
    scrip_master = KotakNeoScripMaster(exchanges=["NSE"])

    if not scrip_master.load_scrip_master(force_download=force_download):
        logger.warning("Some exchanges failed to load, but continuing...")

    return scrip_master


if __name__ == "__main__":
    """Test scrip master functionality"""
    logger.info("Testing Kotak Neo Scrip Master...")

    # Initialize
    sm = initialize_scrip_master(force_download=True)

    # Test lookups
    test_symbols = ["RELIANCE-EQ", "TCS-EQ", "INFY-EQ", "HDFCBANK-EQ"]

    for symbol in test_symbols:
        instrument = sm.get_instrument(symbol)
        if instrument:
            logger.info(f"{symbol}: Token={instrument['token']}, Full data available")
        else:
            logger.warning(f"{symbol}: Not found")

    # Search test
    results = sm.search_instruments("RELIANCE")
    logger.info(f"Search 'RELIANCE': Found {len(results)} matches")
