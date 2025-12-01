#!/usr/bin/env python3
"""
Get All NSE Stocks

Fetches all listed NSE stocks for bulk backtesting and ML training data collection.
Uses scrip master file (11,000+ stocks) or yfinance as fallback.
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger


def get_all_nse_stocks_from_scrip_master() -> list[str]:
    """
    Get all NSE stocks from scrip master file (11,000+ stocks)

    Returns:
        List of stock symbols with .NS suffix (yfinance format)
    """
    logger.info("Fetching NSE stocks from scrip master file...")

    try:
        # Try to use KotakNeoScripMaster if available
        from modules.kotak_neo_auto_trader.scrip_master import (
            KotakNeoScripMaster,
            initialize_scrip_master,
        )

        # Initialize scrip master (will load from cache if available)
        scrip_master = KotakNeoScripMaster(exchanges=["NSE"])

        # Try to load from cache first (no auth required)
        cache_dir = Path("data/scrip_master")
        cache_file = cache_dir / f"scrip_master_NSE_{datetime.now().strftime('%Y%m%d')}.json"

        # Also try to find any cached file (not just today's)
        if not cache_file.exists():
            cache_files = list(cache_dir.glob("scrip_master_NSE_*.json"))
            if cache_files:
                # Use the most recent cache file
                cache_file = max(cache_files, key=lambda p: p.stat().st_mtime)
                logger.info(f"Using cached scrip master: {cache_file.name}")

        if cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    cache_data = json.load(f)
                    instruments = cache_data.get("instruments", [])
                    logger.info(f"Loaded {len(instruments)} instruments from scrip master cache")
            except Exception as e:
                logger.warning(f"Failed to load from cache: {e}")
                instruments = []
        else:
            logger.info("No scrip master cache found, attempting to load via scrip master class...")
            # Try to load via scrip master (may require auth)
            if scrip_master.load_scrip_master(force_download=False):
                instruments = scrip_master.scrip_data.get("NSE", [])
            else:
                logger.warning("Failed to load scrip master, falling back to yfinance")
                return []

        if not instruments:
            logger.warning("No instruments found in scrip master")
            return []

        # Extract stock symbols and convert to yfinance format
        nse_stocks = []
        seen_symbols = set()

        # Filter patterns for non-equity instruments
        excluded_patterns = [
            "NIFTY",
            "BANKNIFTY",
            "FINNIFTY",
            "MIDCPNIFTY",  # Indices
            "SGB",  # Sovereign Gold Bonds
            "ETF",
            "NIFTYBEES",
            "BANKBEES",  # ETFs
            "MASP",
            "MONQ",  # ETFs/Mutual Funds
        ]

        for instrument in instruments:
            # Filter by exchange segment - only include cash market (equity) stocks
            exch_seg = instrument.get("pExchSeg", "").lower()
            if exch_seg not in ["nse_cm", ""]:  # Only cash market (equity) segment
                continue

            # Try different field names for trading symbol
            trading_symbol = (
                instrument.get("pTrdSymbol")
                or instrument.get("symbol")
                or instrument.get("tradingSymbol")
                or instrument.get("InstrumentIdentifier")
                or ""
            )

            if not trading_symbol:
                continue

            # Convert from Kotak format (e.g., "RELIANCE-EQ") to yfinance format (e.g., "RELIANCE.NS")
            # Get suffix to identify instrument type
            symbol_parts = trading_symbol.split("-")
            base_symbol = symbol_parts[0].strip().upper()
            symbol_suffix = symbol_parts[-1].upper() if len(symbol_parts) > 1 else ""

            # Prefer equity instruments with -EQ suffix, but also accept others from cash market
            # Exclude known non-equity suffixes
            excluded_suffixes = ["BOND", "GSEC", "TBILL", "CD", "CP", "DEB", "NCD", "WD", "BE"]
            if symbol_suffix in excluded_suffixes:
                continue

            # Filter out non-equity instruments by pattern
            is_excluded = False
            for pattern in excluded_patterns:
                if pattern in base_symbol:
                    is_excluded = True
                    break

            # Skip bonds (numeric/alphanumeric patterns that look like bond codes)
            # Bonds often have patterns like: numbers + letters + numbers (e.g., "716CG33")
            if base_symbol:
                # Check for bond-like patterns: starts with 2-3 digits followed by letters and numbers
                if re.match(r"^\d{2,3}[A-Z]{2,}\d{2,}", base_symbol):
                    is_excluded = True
                # Skip if starts with digits and has length > 10 (likely bond with date)
                elif base_symbol[0].isdigit() and len(base_symbol) > 10:
                    is_excluded = True
                # Skip very short symbols (likely special instruments)
                elif len(base_symbol) < 2:
                    is_excluded = True

            if is_excluded:
                continue

            # Skip if already seen
            if base_symbol in seen_symbols:
                continue

            # Add .NS suffix for yfinance
            yfinance_symbol = f"{base_symbol}.NS"
            nse_stocks.append(yfinance_symbol)
            seen_symbols.add(base_symbol)

        logger.info(f"Extracted {len(nse_stocks)} unique NSE stocks from scrip master")
        return nse_stocks

    except ImportError:
        logger.warning("KotakNeoScripMaster not available, falling back to yfinance")
        return []
    except Exception as e:
        logger.error(f"Error loading scrip master: {e}")
        logger.warning("Falling back to yfinance method")
        return []


def get_all_nse_stocks_from_yfinance() -> list[str]:
    """
    Get all NSE stocks using yfinance ticker list

    This method uses a known list of major NSE stocks and validates them.
    For a complete list, we can use NSE website or a predefined list.

    Returns:
        List of stock symbols with .NS suffix
    """
    logger.info("Fetching all NSE stocks...")

    # Common approach: Use known NSE stock list or fetch from NSE website
    # For now, we'll use a combination of:
    # 1. Major NSE stocks (known list)
    # 2. Nifty 500 constituents (can fetch from NSE website)

    # Major NSE stocks (common tickers)
    major_stocks = [
        # Nifty 50
        "RELIANCE",
        "TCS",
        "HDFCBANK",
        "INFY",
        "ICICIBANK",
        "HINDUNILVR",
        "BHARTIARTL",
        "SBIN",
        "BAJFINANCE",
        "LICI",
        "ITC",
        "HCLTECH",
        "LT",
        "AXISBANK",
        "KOTAKBANK",
        "ASIANPAINT",
        "MARUTI",
        "TITAN",
        "SUNPHARMA",
        "TATAMOTORS",
        "ADANIENT",
        "ADANIPORTS",
        "ADANIPOWER",
        "BAJAJFINSV",
        "WIPRO",
        "ONGC",
        "NTPC",
        "POWERGRID",
        "NESTLEIND",
        "ULTRACEMCO",
        "COALINDIA",
        "TATASTEEL",
        "JSWSTEEL",
        "HDFCLIFE",
        "DIVISLAB",
        "TECHM",
        "HINDALCO",
        "GRASIM",
        "CIPLA",
        "DRREDDY",
        "TATACONSUM",
        "SBILIFE",
        "EICHERMOT",
        "BRITANNIA",
        "HEROMOTOCO",
        "APOLLOHOSP",
        "ADANIGREEN",
        "M&M",
        "TATASTEEL",
        # Nifty Midcap 150
        "MANAPPURAM",
        "VOLTAS",
        "MRF",
        "ESCORTS",
        "BATAINDIA",
        "BAJAJHOLDINGS",
        "DABUR",
        "MCDOWELL-N",
        "GODREJCP",
        "HAVELLS",
        "AMBUJACEM",
        "ACC",
        "SHREECEM",
        "TORNTPHARM",
        "LUPIN",
        "AUROPHARMA",
        "PIIND",
        "ALKEM",
        "GLENMARK",
        "CADILAHC",
        "DIVISLAB",
        # Add more stocks as needed
    ]

    # Add .NS suffix and validate
    nse_stocks = []
    logger.info(f"Validating {len(major_stocks)} stocks...")

    for stock in major_stocks:
        ticker = f"{stock}.NS"
        try:
            # Quick validation - try to get basic info
            info = yf.Ticker(ticker).info
            if info and "symbol" in info:
                nse_stocks.append(ticker)
                logger.debug(f"Validated: {ticker}")
            time.sleep(0.1)  # Rate limiting
        except Exception as e:
            logger.debug(f"Skipping {ticker}: {e}")
            continue

    logger.info(f"Found {len(nse_stocks)} valid NSE stocks")
    return nse_stocks


def get_nse_stocks_from_file(file_path: str) -> list[str]:
    """
    Get NSE stocks from a file (CSV or text file)

    Args:
        file_path: Path to file with stock symbols

    Returns:
        List of stock symbols with .NS suffix
    """
    try:
        # Try CSV first
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
            # Look for column with stock symbols
            symbol_col = None
            for col in ["Symbol", "SYMBOL", "symbol", "Ticker", "TICKER", "ticker"]:
                if col in df.columns:
                    symbol_col = col
                    break

            if symbol_col:
                stocks = df[symbol_col].dropna().unique().tolist()
            else:
                # Use first column
                stocks = df.iloc[:, 0].dropna().unique().tolist()
        else:
            # Text file - one symbol per line
            with open(file_path) as f:
                stocks = [line.strip() for line in f if line.strip()]

        # Add .NS suffix if not present
        nse_stocks = []
        for stock in stocks:
            stock = stock.upper().strip()
            if not stock.endswith(".NS"):
                stock = f"{stock}.NS"
            nse_stocks.append(stock)

        logger.info(f"Loaded {len(nse_stocks)} stocks from {file_path}")
        return nse_stocks

    except Exception as e:
        logger.error(f"Failed to load stocks from {file_path}: {e}")
        return []


def get_all_nse_stocks(
    output_file: str = "data/all_nse_stocks.txt", use_scrip_master: bool = True
) -> list[str]:
    """
    Get all NSE stocks and save to file

    This function:
    1. Tries to load from saved file
    2. Fetches from scrip master (11,000+ stocks) - RECOMMENDED
    3. Falls back to yfinance (limited)
    4. Validates and saves to file

    Args:
        output_file: Path to save stock list
        use_scrip_master: Use scrip master file (default: True)

    Returns:
        List of NSE stock symbols with .NS suffix
    """
    stocks = []

    # Method 1: Try to load from saved file
    if Path(output_file).exists():
        logger.info(f"Loading stocks from {output_file}...")
        stocks = get_nse_stocks_from_file(output_file)
        if stocks:
            logger.info(f"Loaded {len(stocks)} stocks from file")
            return stocks

    # Method 2: Fetch from scrip master (11,000+ stocks) - RECOMMENDED
    if use_scrip_master:
        logger.info("Fetching stocks from scrip master file...")
        stocks = get_all_nse_stocks_from_scrip_master()

        if stocks and len(stocks) > 100:
            logger.info(f"? Successfully loaded {len(stocks)} stocks from scrip master")
        elif stocks:
            logger.warning(f"Only {len(stocks)} stocks found in scrip master, may need to download")
        else:
            logger.warning("Scrip master method failed, falling back to yfinance")
            stocks = []

    # Method 3: Fallback to yfinance (limited but works)
    if not stocks or len(stocks) < 100:
        logger.info("Fetching stocks from yfinance (fallback)...")
        yf_stocks = get_all_nse_stocks_from_yfinance()
        if yf_stocks:
            # Merge with scrip master stocks if any
            existing = set(stocks)
            for stock in yf_stocks:
                if stock not in existing:
                    stocks.append(stock)
            logger.info(f"Added {len(yf_stocks)} stocks from yfinance")

    # Save to file for future use
    if stocks:
        import os

        os.makedirs(Path(output_file).parent, exist_ok=True)
        with open(output_file, "w") as f:
            for stock in stocks:
                f.write(f"{stock}\n")
        logger.info(f"? Saved {len(stocks)} stocks to {output_file}")
    else:
        logger.error("? No stocks found from any source")

    return stocks


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Get all NSE stocks for ML training")
    parser.add_argument(
        "--output", "-o", default="data/all_nse_stocks.txt", help="Output file path"
    )
    parser.add_argument("--file", "-f", help="Load from existing file")
    parser.add_argument(
        "--no-scrip-master", action="store_true", help="Disable scrip master (use yfinance only)"
    )

    args = parser.parse_args()

    if args.file:
        stocks = get_nse_stocks_from_file(args.file)
    else:
        stocks = get_all_nse_stocks(args.output, use_scrip_master=not args.no_scrip_master)

    print(f"\n{'=' * 70}")
    print(f"Found {len(stocks)} NSE stocks")
    print(f"{'=' * 70}")

    if stocks:
        print("\nFirst 20 stocks:")
        for stock in stocks[:20]:
            print(f"  - {stock}")

        if len(stocks) > 20:
            print(f"\n... and {len(stocks) - 20} more")

        print(f"\nTotal: {len(stocks)} stocks")
        print(f"Saved to: {args.output}")

        # Show statistics
        print(f"\n{'=' * 70}")
        print("Statistics:")
        print(f"  Total stocks: {len(stocks)}")
        if len(stocks) >= 1000:
            print("  ? Excellent coverage (1000+ stocks)")
        elif len(stocks) >= 500:
            print("  ? Good coverage (500+ stocks)")
        elif len(stocks) >= 200:
            print("  [WARN]?  Moderate coverage (200+ stocks)")
        else:
            print("  [WARN]?  Low coverage (<200 stocks)")
    else:
        print("\n? No stocks found!")
        print("\nTroubleshooting:")
        print("  1. Check if scrip master file exists: data/scrip_master/scrip_master_NSE_*.json")
        print("  2. Try running without scrip master: --no-scrip-master")
        print("  3. Ensure yfinance is installed and working")
