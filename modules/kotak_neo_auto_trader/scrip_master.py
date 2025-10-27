#!/usr/bin/env python3
"""
Kotak Neo Scrip Master Handler

Downloads and manages the scrip master file containing instrument tokens,
symbols, and other metadata required for accurate order placement and quotes.
"""

import os
import sys
from pathlib import Path
import json
import csv
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger

try:
    from . import config
except ImportError:
    import config


class KotakNeoScripMaster:
    """
    Manages Kotak Neo scrip master data for instrument lookups
    """
    
    # Kotak Neo scrip master URLs
    SCRIP_MASTER_URLS = {
        'NSE': 'https://preferred.kotaksecurities.com/security/production/TradeApiInstruments_Cash_NSE_09_11_2023.txt',
        'BSE': 'https://preferred.kotaksecurities.com/security/production/TradeApiInstruments_Cash_BSE_09_11_2023.txt',
        'NFO': 'https://preferred.kotaksecurities.com/security/production/TradeApiInstruments_FNO_14_11_2023.txt',
        'CDS': 'https://preferred.kotaksecurities.com/security/production/TradeApiInstruments_Currency_14_11_2023.txt',
    }
    
    def __init__(self, cache_dir: str = "data/scrip_master", exchanges: List[str] = None, auth_client=None):
        """
        Initialize scrip master handler
        
        Args:
            cache_dir: Directory to cache scrip master files
            exchanges: List of exchanges to download (default: ['NSE'])
            auth_client: Authenticated Kotak Neo client for API access
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.exchanges = exchanges or ['NSE']
        self.auth_client = auth_client
        self.scrip_data: Dict[str, List[Dict]] = {}
        self.symbol_map: Dict[str, Dict] = {}  # Quick lookup: symbol -> instrument data
        
        logger.info(f"KotakNeoScripMaster initialized for exchanges: {self.exchanges}")
    
    def _get_cache_path(self, exchange: str) -> Path:
        """Get cache file path for an exchange"""
        return self.cache_dir / f"scrip_master_{exchange}_{datetime.now().strftime('%Y%m%d')}.json"
    
    def _is_cache_valid(self, exchange: str) -> bool:
        """Check if cached scrip master is valid (today's date)"""
        cache_path = self._get_cache_path(exchange)
        
        if not cache_path.exists():
            return False
        
        # Check if file is from today
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                cache_date = data.get('download_date', '')
                if cache_date == datetime.now().strftime('%Y-%m-%d'):
                    return True
        except Exception as e:
            logger.warning(f"Error reading cache for {exchange}: {e}")
        
        return False
    
    def _download_scrip_master(self, exchange: str, auth_client=None) -> Optional[List[Dict]]:
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
            
            # Use auth client if provided
            if auth_client and hasattr(auth_client, 'scrip_master'):
                try:
                    result = auth_client.scrip_master(exchange_segment=exchange)
                    if result and isinstance(result, dict):
                        instruments = result.get('data', [])
                        if instruments:
                            logger.info(f"Downloaded {len(instruments)} instruments for {exchange} via API")
                            return instruments
                except Exception as e:
                    logger.warning(f"API scrip master failed: {e}, trying URL fallback...")
            
            # Fallback to direct URL download
            url = self.SCRIP_MASTER_URLS.get(exchange.upper())
            if not url:
                logger.error(f"Unknown exchange: {exchange}")
                return None
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse CSV/TXT format
            lines = response.text.strip().split('\n')
            if len(lines) < 2:
                logger.error(f"Invalid scrip master format for {exchange}")
                return None
            
            # First line is header
            headers = [h.strip() for h in lines[0].split('|')]
            
            instruments = []
            for line in lines[1:]:
                if not line.strip():
                    continue
                
                fields = [f.strip() for f in line.split('|')]
                if len(fields) != len(headers):
                    continue
                
                instrument = dict(zip(headers, fields))
                instruments.append(instrument)
            
            logger.info(f"Downloaded {len(instruments)} instruments for {exchange}")
            return instruments
            
        except requests.RequestException as e:
            logger.error(f"Failed to download scrip master for {exchange}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing scrip master for {exchange}: {e}")
            return None
    
    def _save_to_cache(self, exchange: str, instruments: List[Dict]) -> bool:
        """Save scrip master data to cache"""
        try:
            cache_path = self._get_cache_path(exchange)
            
            cache_data = {
                'exchange': exchange,
                'download_date': datetime.now().strftime('%Y-%m-%d'),
                'download_timestamp': datetime.now().isoformat(),
                'instrument_count': len(instruments),
                'instruments': instruments
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            
            logger.info(f"Cached {len(instruments)} instruments for {exchange}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving cache for {exchange}: {e}")
            return False
    
    def _load_from_cache(self, exchange: str) -> Optional[List[Dict]]:
        """Load scrip master data from cache"""
        try:
            cache_path = self._get_cache_path(exchange)
            
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            instruments = cache_data.get('instruments', [])
            logger.info(f"Loaded {len(instruments)} instruments for {exchange} from cache")
            return instruments
            
        except Exception as e:
            logger.error(f"Error loading cache for {exchange}: {e}")
            return None
    
    def load_scrip_master(self, force_download: bool = False) -> bool:
        """
        Load scrip master data for configured exchanges
        
        Args:
            force_download: Force fresh download even if cache exists
            
        Returns:
            True if successful
        """
        success = True
        
        for exchange in self.exchanges:
            # Check cache first
            if not force_download and self._is_cache_valid(exchange):
                instruments = self._load_from_cache(exchange)
            else:
                # Download fresh data
                instruments = self._download_scrip_master(exchange, auth_client=self.auth_client)
                if instruments:
                    self._save_to_cache(exchange, instruments)
            
            if instruments:
                self.scrip_data[exchange] = instruments
                self._build_symbol_map(exchange, instruments)
            else:
                logger.error(f"Failed to load scrip master for {exchange}")
                success = False
        
        return success
    
    def _build_symbol_map(self, exchange: str, instruments: List[Dict]):
        """Build quick lookup map for symbols"""
        for instrument in instruments:
            # Extract relevant fields (field names may vary)
            symbol = instrument.get('pSymbol') or instrument.get('symbol') or instrument.get('tradingSymbol')
            token = instrument.get('pTrdSymbol') or instrument.get('instrumentToken') or instrument.get('token')
            
            if symbol:
                # Store with exchange prefix for uniqueness
                key = f"{exchange}:{symbol}"
                self.symbol_map[key] = {
                    'exchange': exchange,
                    'symbol': symbol,
                    'token': token,
                    'instrument': instrument
                }
                
                # Also store without exchange for convenience (NSE only)
                if exchange == 'NSE' and symbol not in self.symbol_map:
                    self.symbol_map[symbol] = self.symbol_map[key]
    
    def get_instrument(self, symbol: str, exchange: str = 'NSE') -> Optional[Dict]:
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
        base_symbol = symbol.split('-')[0]
        if base_symbol in self.symbol_map:
            return self.symbol_map[base_symbol]
        
        key = f"{exchange}:{base_symbol}"
        if key in self.symbol_map:
            return self.symbol_map[key]
        
        logger.warning(f"Instrument not found: {symbol} ({exchange})")
        return None
    
    def get_token(self, symbol: str, exchange: str = 'NSE') -> Optional[str]:
        """Get instrument token for a symbol"""
        instrument = self.get_instrument(symbol, exchange)
        return instrument['token'] if instrument else None
    
    def get_trading_symbol(self, symbol: str, exchange: str = 'NSE') -> Optional[str]:
        """Get correct trading symbol for order placement"""
        instrument = self.get_instrument(symbol, exchange)
        return instrument['symbol'] if instrument else None
    
    def search_instruments(self, keyword: str, exchange: str = None) -> List[Dict]:
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
            if exchange and data['exchange'] != exchange:
                continue
            
            symbol = data['symbol'].upper()
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
    scrip_master = KotakNeoScripMaster(exchanges=['NSE'])
    
    if not scrip_master.load_scrip_master(force_download=force_download):
        logger.warning("Some exchanges failed to load, but continuing...")
    
    return scrip_master


if __name__ == "__main__":
    """Test scrip master functionality"""
    logger.info("Testing Kotak Neo Scrip Master...")
    
    # Initialize
    sm = initialize_scrip_master(force_download=True)
    
    # Test lookups
    test_symbols = ['RELIANCE-EQ', 'TCS-EQ', 'INFY-EQ', 'HDFCBANK-EQ']
    
    for symbol in test_symbols:
        instrument = sm.get_instrument(symbol)
        if instrument:
            logger.info(f"{symbol}: Token={instrument['token']}, Full data available")
        else:
            logger.warning(f"{symbol}: Not found")
    
    # Search test
    results = sm.search_instruments('RELIANCE')
    logger.info(f"Search 'RELIANCE': Found {len(results)} matches")
