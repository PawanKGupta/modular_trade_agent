#!/usr/bin/env python3
"""
Live Price Manager
High-level manager for real-time LTP with automatic fallback to yfinance
"""

import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger
from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster
from modules.kotak_neo_auto_trader.live_price_cache import LivePriceCache


class LivePriceManager:
    """
    Manages real-time price fetching with automatic fallback.
    
    Features:
    - Real-time LTP from Kotak Neo WebSocket
    - Automatic fallback to yfinance
    - Dynamic subscription management
    - Simple get_ltp() interface
    """
    
    def __init__(
        self,
        env_file: str = "modules/kotak_neo_auto_trader/kotak_neo.env",
        enable_websocket: bool = True,
        enable_yfinance_fallback: bool = True
    ):
        """
        Initialize live price manager.
        
        Args:
            env_file: Path to Kotak Neo credentials
            enable_websocket: Enable WebSocket live prices
            enable_yfinance_fallback: Fall back to yfinance if WebSocket unavailable
        """
        self.enable_websocket = enable_websocket
        self.enable_yfinance_fallback = enable_yfinance_fallback
        
        self.auth = None
        self.scrip_master = None
        self.price_cache = None
        self._initialized = False
        
        # Stats
        self.stats = {
            'websocket_hits': 0,
            'yfinance_fallbacks': 0,
            'errors': 0,
            'last_websocket_time': None,
            'last_yfinance_time': None
        }
        
        # Initialize if WebSocket enabled
        if self.enable_websocket:
            try:
                self._initialize_websocket(env_file)
            except Exception as e:
                logger.error(f"WebSocket initialization failed: {e}")
                if not self.enable_yfinance_fallback:
                    raise
                logger.warning("Will use yfinance fallback only")
    
    def _initialize_websocket(self, env_file: str):
        """Initialize WebSocket components."""
        logger.info("Initializing live price manager with WebSocket...")
        
        # Login to Kotak Neo
        self.auth = KotakNeoAuth(env_file)
        if not self.auth.login():
            raise RuntimeError("Kotak Neo login failed")
        
        logger.info("✓ Logged in to Kotak Neo")
        
        # Load scrip master
        self.scrip_master = KotakNeoScripMaster(
            auth_client=self.auth.client,
            exchanges=['NSE']
        )
        self.scrip_master.load_scrip_master(force_download=False)
        logger.info("✓ Scrip master loaded")
        
        # Initialize price cache
        self.price_cache = LivePriceCache(
            auth_client=self.auth.client,
            scrip_master=self.scrip_master,
            stale_threshold_seconds=60,
            reconnect_delay_seconds=5
        )
        
        # Start WebSocket service
        self.price_cache.start()
        logger.info("✓ WebSocket price cache started")
        
        self._initialized = True
        logger.info("Live price manager initialized successfully")
    
    def subscribe_to_positions(self, symbols: List[str]):
        """
        Subscribe to live prices for given symbols.
        
        Args:
            symbols: List of symbols (e.g., ["RELIANCE", "TCS"])
        """
        if not self._initialized or not self.price_cache:
            logger.warning("WebSocket not initialized, cannot subscribe")
            return
        
        if not symbols:
            return
        
        try:
            self.price_cache.subscribe(symbols)
            logger.info(f"✓ Subscribed to {len(symbols)} positions")
            
            # Wait for initial connection and data
            if self.price_cache.wait_for_connection(timeout=10):
                logger.info("✓ WebSocket connected")
                if self.price_cache.wait_for_data(timeout=10):
                    logger.info("✓ Receiving live data")
                else:
                    logger.warning("⚠️ No data received yet (market may be closed)")
            else:
                logger.warning("⚠️ WebSocket connection timeout")
                
        except Exception as e:
            logger.error(f"Subscription failed: {e}")
            self.stats['errors'] += 1
    
    def unsubscribe_from_positions(self, symbols: List[str]):
        """
        Unsubscribe from live prices for given symbols.
        
        Args:
            symbols: List of symbols to unsubscribe
        """
        if not self._initialized or not self.price_cache:
            return
        
        try:
            self.price_cache.unsubscribe(symbols)
            logger.info(f"✓ Unsubscribed from {len(symbols)} positions")
        except Exception as e:
            logger.error(f"Unsubscribe failed: {e}")
    
    def get_ltp(self, symbol: str, ticker: Optional[str] = None) -> Optional[float]:
        """
        Get latest LTP for a symbol with automatic fallback.
        
        Priority:
        1. Try WebSocket cache (if enabled and available)
        2. Fall back to yfinance (if enabled)
        
        Args:
            symbol: Symbol name (e.g., "RELIANCE")
            ticker: Yahoo Finance ticker (e.g., "RELIANCE.NS") - used for fallback
        
        Returns:
            Latest LTP or None if unavailable
        """
        # Try WebSocket first
        if self._initialized and self.price_cache:
            try:
                ltp = self.price_cache.get_ltp(symbol)
                if ltp is not None:
                    self.stats['websocket_hits'] += 1
                    self.stats['last_websocket_time'] = datetime.now()
                    logger.debug(f"Got LTP from WebSocket: {symbol} = ₹{ltp}")
                    return ltp
            except Exception as e:
                logger.warning(f"WebSocket LTP fetch failed for {symbol}: {e}")
                self.stats['errors'] += 1
        
        # Fall back to yfinance
        if self.enable_yfinance_fallback:
            try:
                ltp = self._get_ltp_yfinance(symbol, ticker)
                if ltp is not None:
                    self.stats['yfinance_fallbacks'] += 1
                    self.stats['last_yfinance_time'] = datetime.now()
                    logger.debug(f"Got LTP from yfinance: {symbol} = ₹{ltp}")
                    return ltp
            except Exception as e:
                logger.warning(f"yfinance LTP fetch failed for {symbol}: {e}")
                self.stats['errors'] += 1
        
        logger.warning(f"Could not get LTP for {symbol}")
        return None
    
    def _get_ltp_yfinance(self, symbol: str, ticker: Optional[str] = None) -> Optional[float]:
        """
        Get LTP from yfinance (fallback).
        
        Args:
            symbol: Symbol name
            ticker: Yahoo Finance ticker
        
        Returns:
            LTP from yfinance
        """
        import yfinance as yf
        
        # Construct ticker if not provided
        if not ticker:
            ticker = f"{symbol}.NS"
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Try different price fields
            ltp = (
                info.get('currentPrice') or
                info.get('regularMarketPrice') or
                info.get('previousClose')
            )
            
            return float(ltp) if ltp else None
            
        except Exception as e:
            logger.debug(f"yfinance fetch error for {ticker}: {e}")
            return None
    
    def get_all_ltps(self) -> dict:
        """
        Get all cached LTPs from WebSocket.
        
        Returns:
            Dict of {symbol: ltp}
        """
        if not self._initialized or not self.price_cache:
            return {}
        
        try:
            return self.price_cache.get_all_prices()
        except Exception as e:
            logger.error(f"Failed to get all LTPs: {e}")
            return {}
    
    def is_websocket_connected(self) -> bool:
        """Check if WebSocket is connected and receiving data."""
        if not self._initialized or not self.price_cache:
            return False
        
        return self.price_cache.is_connected()
    
    def get_stats(self) -> dict:
        """
        Get usage statistics.
        
        Returns:
            Dict with stats
        """
        stats = {
            **self.stats,
            'websocket_enabled': self.enable_websocket,
            'websocket_initialized': self._initialized,
            'websocket_connected': self.is_websocket_connected(),
            'yfinance_fallback_enabled': self.enable_yfinance_fallback
        }
        
        # Add WebSocket cache stats if available
        if self._initialized and self.price_cache:
            try:
                cache_stats = self.price_cache.get_stats()
                stats['websocket_cache'] = cache_stats
            except:
                pass
        
        return stats
    
    def print_stats(self):
        """Print usage statistics."""
        stats = self.get_stats()
        
        print("\n" + "=" * 70)
        print("LIVE PRICE MANAGER STATS")
        print("=" * 70)
        print(f"WebSocket Enabled: {stats['websocket_enabled']}")
        print(f"WebSocket Initialized: {stats['websocket_initialized']}")
        print(f"WebSocket Connected: {stats['websocket_connected']}")
        print(f"yfinance Fallback Enabled: {stats['yfinance_fallback_enabled']}")
        print()
        print(f"WebSocket Hits: {stats['websocket_hits']}")
        print(f"yfinance Fallbacks: {stats['yfinance_fallbacks']}")
        print(f"Errors: {stats['errors']}")
        
        if stats.get('last_websocket_time'):
            print(f"Last WebSocket Fetch: {stats['last_websocket_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        if stats.get('last_yfinance_time'):
            print(f"Last yfinance Fallback: {stats['last_yfinance_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        if stats.get('websocket_cache'):
            cache = stats['websocket_cache']
            print()
            print("WebSocket Cache:")
            print(f"  Subscriptions: {cache.get('subscriptions', 0)}")
            print(f"  Cache Size: {cache.get('cache_size', 0)}")
            print(f"  Messages Received: {cache.get('messages_received', 0)}")
            print(f"  Updates Processed: {cache.get('updates_processed', 0)}")
            print(f"  Reconnections: {cache.get('reconnections', 0)}")
            if cache.get('last_update'):
                print(f"  Last Update: {cache['last_update'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        print("=" * 70 + "\n")
    
    def stop(self):
        """Stop the price manager and clean up resources."""
        logger.info("Stopping live price manager...")
        
        if self.price_cache:
            try:
                self.price_cache.stop()
                logger.info("✓ WebSocket cache stopped")
            except Exception as e:
                logger.error(f"Error stopping WebSocket cache: {e}")
        
        if self.auth:
            try:
                self.auth.logout()
                logger.info("✓ Logged out from Kotak Neo")
            except Exception as e:
                logger.error(f"Error logging out: {e}")
        
        logger.info("Live price manager stopped")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - clean up resources."""
        self.stop()


# Global singleton instance
_price_manager_instance = None


def get_live_price_manager(
    env_file: str = "modules/kotak_neo_auto_trader/kotak_neo.env",
    enable_websocket: bool = True,
    enable_yfinance_fallback: bool = True
) -> LivePriceManager:
    """
    Get or create live price manager singleton.
    
    Args:
        env_file: Path to Kotak Neo credentials
        enable_websocket: Enable WebSocket live prices
        enable_yfinance_fallback: Fall back to yfinance if WebSocket unavailable
    
    Returns:
        LivePriceManager instance
    """
    global _price_manager_instance
    
    if _price_manager_instance is None:
        _price_manager_instance = LivePriceManager(
            env_file=env_file,
            enable_websocket=enable_websocket,
            enable_yfinance_fallback=enable_yfinance_fallback
        )
    
    return _price_manager_instance
