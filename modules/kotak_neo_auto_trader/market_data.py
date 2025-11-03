#!/usr/bin/env python3
"""
Market Data Module for Kotak Neo API
Handles real-time quotes, LTP, and market data fetching
"""

from typing import Optional, Dict, List
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger

try:
    from .auth import KotakNeoAuth
    from .auth_handler import handle_reauth
except ImportError:
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.auth_handler import handle_reauth


class KotakNeoMarketData:
    """
    Market data handler for Kotak Neo API
    """
    
    def __init__(self, auth: KotakNeoAuth):
        """
        Initialize market data handler
        
        Args:
            auth: Authenticated Kotak Neo session
        """
        self.auth = auth
        logger.info("KotakNeoMarketData initialized")
    
    @handle_reauth
    def get_quote(self, symbol: str, exchange: str = "NSE", instrument_token: str = None) -> Optional[Dict]:
        """
        Get real-time quote for a symbol
        
        Args:
            symbol: Trading symbol (e.g., 'RELIANCE-EQ')
            exchange: Exchange segment (NSE/BSE)
            instrument_token: Optional instrument token for faster lookup
            
        Returns:
            Quote data dict or None if failed
        """
        client = self.auth.get_client()
        if not client:
            logger.error("Client not available for quote fetch")
            return None
        
        try:
            # Try multiple method names for quote fetching
            method_names = [
                "quotes",
                "quote",
                "get_quote",
                "get_quotes",
                "scrip_master",
                "market_quote"
            ]
            
            for method_name in method_names:
                if not hasattr(client, method_name):
                    continue
                
                method = getattr(client, method_name)
                
                try:
                    # Try with symbol
                    quote = method(instrument_tokens=instrument_token) if instrument_token else method(
                        exchange_segment=exchange,
                        instrument_tokens=[symbol] if isinstance(method_name, str) and 'quotes' in method_name else symbol
                    )
                    
                    if quote and isinstance(quote, dict) and 'error' not in quote:
                        logger.debug(f"Quote fetched via {method_name}: {symbol}")
                        return quote
                    
                except TypeError:
                    # Try different parameter combinations
                    try:
                        quote = method(symbol)
                        if quote and isinstance(quote, dict) and 'error' not in quote:
                            logger.debug(f"Quote fetched via {method_name}: {symbol}")
                            return quote
                    except Exception:
                        continue
                        
                except Exception as e:
                    logger.debug(f"Method {method_name} failed: {e}")
                    continue
            
            logger.warning(f"No compatible quote method found for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None
    
    def get_ltp(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        """
        Get Last Traded Price for a symbol
        
        Args:
            symbol: Trading symbol (e.g., 'RELIANCE-EQ')
            exchange: Exchange segment
            
        Returns:
            LTP value or None if failed
        """
        try:
            quote = self.get_quote(symbol, exchange)
            
            if not quote:
                logger.warning(f"No quote data for {symbol}")
                return None
            
            # Try multiple possible field names for LTP
            ltp_fields = [
                'ltp',
                'lastPrice',
                'last_price',
                'lastTradedPrice',
                'last_traded_price',
                'price',
                'close',
                'lastClosePrice'
            ]
            
            # Check if data is nested
            data = quote.get('data', quote)
            
            # Handle list response (some APIs return list of quotes)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            
            # Extract LTP
            for field in ltp_fields:
                if field in data:
                    ltp = float(data[field])
                    logger.debug(f"{symbol} LTP: ₹{ltp:.2f}")
                    return ltp
            
            logger.warning(f"LTP field not found in quote data for {symbol}. Available fields: {list(data.keys())}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting LTP for {symbol}: {e}")
            return None
    
    def get_market_depth(self, symbol: str, exchange: str = "NSE") -> Optional[Dict]:
        """
        Get market depth (order book) for a symbol
        
        Args:
            symbol: Trading symbol
            exchange: Exchange segment
            
        Returns:
            Market depth data or None
        """
        client = self.auth.get_client()
        if not client:
            return None
        
        try:
            method_names = ["market_depth", "get_market_depth", "depth"]
            
            for method_name in method_names:
                if hasattr(client, method_name):
                    method = getattr(client, method_name)
                    try:
                        depth = method(exchange_segment=exchange, symbol=symbol)
                        if depth and 'error' not in depth:
                            return depth
                    except Exception:
                        continue
            
            logger.warning(f"No market depth method available for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching market depth for {symbol}: {e}")
            return None
    
    def get_multiple_ltp(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, float]:
        """
        Get LTP for multiple symbols (batch operation)
        
        Args:
            symbols: List of trading symbols
            exchange: Exchange segment
            
        Returns:
            Dict mapping symbol to LTP
        """
        results = {}
        
        for symbol in symbols:
            ltp = self.get_ltp(symbol, exchange)
            if ltp is not None:
                results[symbol] = ltp
        
        logger.info(f"Fetched LTP for {len(results)}/{len(symbols)} symbols")
        return results
    
    def search_scrip(self, search_term: str, exchange: str = "NSE") -> Optional[List[Dict]]:
        """
        Search for scrip/instrument by name or symbol
        
        Args:
            search_term: Search string
            exchange: Exchange segment
            
        Returns:
            List of matching instruments or None
        """
        client = self.auth.get_client()
        if not client:
            return None
        
        try:
            method_names = ["search_scrip", "scrip_search", "search"]
            
            for method_name in method_names:
                if hasattr(client, method_name):
                    method = getattr(client, method_name)
                    try:
                        results = method(exchange_segment=exchange, symbol=search_term)
                        if results and 'error' not in results:
                            return results.get('data', results)
                    except Exception:
                        continue
            
            logger.warning(f"No scrip search method available")
            return None
            
        except Exception as e:
            logger.error(f"Error searching scrip {search_term}: {e}")
            return None
