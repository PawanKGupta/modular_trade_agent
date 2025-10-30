#!/usr/bin/env python3
"""
Live Price Cache Service
Maintains real-time LTP cache using Kotak Neo WebSocket
"""

import sys
import time
import threading
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger


@dataclass
class PriceData:
    """Cached price data for a symbol"""
    ltp: float
    timestamp: datetime
    trading_symbol: str
    instrument_token: int


class LivePriceCache:
    """
    Thread-safe cache for real-time LTP from Kotak Neo WebSocket.
    
    Features:
    - Real-time price updates via WebSocket
    - Thread-safe access
    - Auto-reconnection on disconnect
    - Stale data detection
    - Subscription management
    """
    
    def __init__(
        self,
        auth_client,
        scrip_master,
        stale_threshold_seconds: int = 60,
        reconnect_delay_seconds: int = 5
    ):
        """
        Initialize live price cache.
        
        Args:
            auth_client: Authenticated Kotak Neo client
            scrip_master: KotakNeoScripMaster instance
            stale_threshold_seconds: Mark data stale after this many seconds
            reconnect_delay_seconds: Wait time before reconnect attempt
        """
        self.client = auth_client
        self.scrip_master = scrip_master
        self.stale_threshold = timedelta(seconds=stale_threshold_seconds)
        self.reconnect_delay = reconnect_delay_seconds
        
        # Thread-safe price cache
        self._cache: Dict[str, PriceData] = {}
        self._cache_lock = threading.Lock()
        
        # Subscription tracking
        self._subscribed_tokens: List[Dict] = []
        self._symbol_to_token: Dict[str, int] = {}
        
        # WebSocket state
        self._ws_connected = threading.Event()
        self._ws_running = threading.Event()
        self._first_data_received = threading.Event()
        self._shutdown = threading.Event()
        
        # Internal threads/handles
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Stats
        self.stats = {
            'messages_received': 0,
            'updates_processed': 0,
            'errors': 0,
            'reconnections': 0,
            'last_update': None
        }
        
        logger.info("LivePriceCache initialized")
    
    def start(self):
        """Start the WebSocket price cache service."""
        if self._ws_running.is_set():
            logger.warning("WebSocket already running")
            return
        
        logger.info("Starting live price cache service...")
        
        # Set up callbacks
        self._setup_callbacks()
        
        # Mark as running
        self._ws_running.set()
        self._shutdown.clear()
        
        # If the underlying client supports disabling auto-reconnect, do it
        try:
            for attr in ("auto_reconnect", "enable_reconnect", "reconnect_enabled"):
                if hasattr(self.client, attr):
                    setattr(self.client, attr, False)
        except Exception:
            pass
        
        # Start reconnection monitor in background
        self._monitor_thread = threading.Thread(
            target=self._connection_monitor,
            daemon=True,
            name="WebSocket-Monitor"
        )
        self._monitor_thread.start()
        
        logger.info("Live price cache service started")
    
    def stop(self):
        """Stop the WebSocket service gracefully."""
        logger.info("Stopping live price cache service...")
        
        # Signal threads/callbacks to stop first
        self._shutdown.set()
        self._ws_running.clear()
        
        # Detach callbacks to avoid late logs during shutdown
        self._detach_callbacks()
        
        # Unsubscribe from all (best-effort)
        if self._subscribed_tokens:
            try:
                self.client.un_subscribe(
                    instrument_tokens=self._subscribed_tokens,
                    isIndex=False,
                    isDepth=False
                )
                logger.info("Unsubscribed from all instruments")
            except Exception as e:
                logger.debug(f"Unsubscribe failed: {e}")
        
        # Attempt to close the underlying WebSocket/stream if SDK exposes it
        self._close_client_socket()
        
        # Wait briefly for monitor thread to exit (don't block forever)
        try:
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=self.reconnect_delay + 1)
        except Exception:
            pass
        
        logger.info("Live price cache service stopped")
    
    def subscribe(self, symbols: List[str]):
        """
        Subscribe to live prices for given symbols.
        
        Args:
            symbols: List of symbols (e.g., ["RELIANCE", "TCS"])
        """
        if not symbols:
            return
        
        logger.info(f"Subscribing to {len(symbols)} symbols: {', '.join(symbols)}")
        
        # Get instrument tokens
        tokens_to_subscribe = []
        
        for symbol in symbols:
            instrument = self.scrip_master.get_instrument(symbol)
            if not instrument:
                logger.warning(f"Instrument not found for {symbol}")
                continue
            
            token = instrument.get('token')
            trading_symbol = instrument.get('symbol')
            exchange = instrument.get('exchange', 'NSE').lower()
            
            # Determine exchange segment
            if exchange == 'nse':
                exchange_segment = 'nse_cm'
            elif exchange == 'bse':
                exchange_segment = 'bse_cm'
            else:
                exchange_segment = 'nse_cm'
            
            # Add to subscription list
            token_dict = {
                'instrument_token': token,
                'exchange_segment': exchange_segment
            }
            
            if token_dict not in self._subscribed_tokens:
                tokens_to_subscribe.append(token_dict)
                self._subscribed_tokens.append(token_dict)
                self._symbol_to_token[symbol] = token
                
                logger.info(
                    f"  {symbol:12s} → {trading_symbol:15s} "
                    f"(token: {token}, segment: {exchange_segment})"
                )
        
        if not tokens_to_subscribe:
            logger.info("No new symbols to subscribe")
            return
        
        # Subscribe via WebSocket
        try:
            self.client.subscribe(
                instrument_tokens=tokens_to_subscribe,
                isIndex=False,
                isDepth=False
            )
            logger.info(f"✓ Subscribed to {len(tokens_to_subscribe)} new instruments")
        except Exception as e:
            logger.error(f"Subscription failed: {e}", exc_info=True)
            self.stats['errors'] += 1
    
    def unsubscribe(self, symbols: List[str]):
        """
        Unsubscribe from live prices for given symbols.
        
        Args:
            symbols: List of symbols to unsubscribe
        """
        if not symbols:
            return
        
        logger.info(f"Unsubscribing from {len(symbols)} symbols")
        
        tokens_to_unsubscribe = []
        
        for symbol in symbols:
            if symbol not in self._symbol_to_token:
                continue
            
            token = self._symbol_to_token[symbol]
            
            # Find and remove from subscribed list
            token_dict = None
            for t in self._subscribed_tokens:
                if t['instrument_token'] == token:
                    token_dict = t
                    break
            
            if token_dict:
                tokens_to_unsubscribe.append(token_dict)
                self._subscribed_tokens.remove(token_dict)
                del self._symbol_to_token[symbol]
                
                # Remove from cache
                with self._cache_lock:
                    if symbol in self._cache:
                        del self._cache[symbol]
        
        if tokens_to_unsubscribe:
            try:
                self.client.un_subscribe(
                    instrument_tokens=tokens_to_unsubscribe,
                    isIndex=False,
                    isDepth=False
                )
                logger.info(f"✓ Unsubscribed from {len(tokens_to_unsubscribe)} instruments")
            except Exception as e:
                logger.error(f"Unsubscribe failed: {e}")
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """
        Get latest LTP for a symbol.
        
        Args:
            symbol: Symbol name (e.g., "RELIANCE")
        
        Returns:
            Latest LTP or None if not available/stale
        """
        with self._cache_lock:
            if symbol not in self._cache:
                return None
            
            price_data = self._cache[symbol]
            
            # Check if data is stale
            age = datetime.now() - price_data.timestamp
            if age > self.stale_threshold:
                logger.debug(f"Stale data for {symbol} (age: {age.seconds}s)")
                return None
            
            return price_data.ltp
    
    def get_all_prices(self) -> Dict[str, float]:
        """
        Get all cached LTPs (non-stale only).
        
        Returns:
            Dict of {symbol: ltp}
        """
        prices = {}
        now = datetime.now()
        
        with self._cache_lock:
            for symbol, price_data in self._cache.items():
                age = now - price_data.timestamp
                if age <= self.stale_threshold:
                    prices[symbol] = price_data.ltp
        
        return prices
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._ws_connected.is_set()
    
    def wait_for_connection(self, timeout: float = 10.0) -> bool:
        """
        Wait for WebSocket connection.
        
        Args:
            timeout: Max seconds to wait
        
        Returns:
            True if connected within timeout
        """
        return self._ws_connected.wait(timeout)
    
    def wait_for_data(self, timeout: float = 10.0) -> bool:
        """
        Wait for first data to arrive.
        
        Args:
            timeout: Max seconds to wait
        
        Returns:
            True if data received within timeout
        """
        return self._first_data_received.wait(timeout)
    
    def _setup_callbacks(self):
        """Set up WebSocket callbacks."""
        self.client.on_message = self._on_message
        self.client.on_error = self._on_error
        self.client.on_open = self._on_open
        self.client.on_close = self._on_close
    
    def _detach_callbacks(self):
        """Detach/neutralize callbacks on the client to prevent late invocations during shutdown."""
        try:
            noop = lambda *_, **__: None
            for attr in ("on_message", "on_error", "on_open", "on_close"):
                if hasattr(self.client, attr):
                    setattr(self.client, attr, noop)
        except Exception:
            pass
    
    def _on_message(self, message):
        """WebSocket message callback - parse and cache prices."""
        try:
            self.stats['messages_received'] += 1
            
            # Parse message
            if not isinstance(message, dict):
                return
            
            # Handle different message types
            msg_type = message.get('type')
            data = message.get('data')
            
            if not data:
                return
            
            # Parse price data
            if isinstance(data, list):
                for item in data:
                    self._process_price_update(item)
            elif isinstance(data, dict):
                self._process_price_update(data)
            
            self.stats['last_update'] = datetime.now()
            self._first_data_received.set()
            
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}", exc_info=True)
            self.stats['errors'] += 1
    
    def _process_price_update(self, item: Dict):
        """Process a single price update from WebSocket data."""
        try:
            # Extract fields (WebSocket sends abbreviated keys)
            token = item.get('tk')  # instrument_token
            trading_symbol = item.get('ts')  # trading_symbol
            ltp = item.get('ltp') or item.get('last_traded_price')
            
            if not token or not ltp:
                return
            
            # Find symbol from token
            symbol = None
            for sym, tok in self._symbol_to_token.items():
                if tok == token:
                    symbol = sym
                    break
            
            if not symbol:
                return
            
            # Update cache
            price_data = PriceData(
                ltp=float(ltp),
                timestamp=datetime.now(),
                trading_symbol=trading_symbol,
                instrument_token=token
            )
            
            with self._cache_lock:
                self._cache[symbol] = price_data
            
            self.stats['updates_processed'] += 1
            logger.debug(f"Updated {symbol}: ₹{ltp}")
            
        except Exception as e:
            logger.error(f"Error processing price update: {e}", exc_info=True)
    
    def _on_error(self, error):
        """WebSocket error callback."""
        if self._shutdown.is_set():
            logger.debug(f"WebSocket error during shutdown: {error}")
            return
        logger.error(f"WebSocket error: {error}")
        self.stats['errors'] += 1
        self._ws_connected.clear()
    
    def _on_open(self, message):
        """WebSocket open callback."""
        if self._shutdown.is_set():
            # Ignore late open during shutdown
            return
        logger.info(f"WebSocket connected: {message}")
        self._ws_connected.set()
    
    def _on_close(self, message):
        """WebSocket close callback."""
        if self._shutdown.is_set():
            logger.debug(f"WebSocket closed during shutdown: {message}")
            return
        logger.warning(f"WebSocket closed: {message}")
        self._ws_connected.clear()
    
    def _connection_monitor(self):
        """Monitor connection and reconnect if needed."""
        logger.info("Connection monitor started")
        
        while self._ws_running.is_set() and not self._shutdown.is_set():
            try:
                # Check if connected
                if not self._ws_connected.is_set():
                    if self._shutdown.is_set():
                        break
                    logger.warning("WebSocket disconnected, attempting reconnect...")
                    self._reconnect()
                
                # Sleep before next check
                for _ in range(int(max(1, self.reconnect_delay))):
                    if not self._ws_running.is_set() or self._shutdown.is_set():
                        break
                    time.sleep(1)
                
            except Exception as e:
                if self._shutdown.is_set():
                    break
                logger.error(f"Connection monitor error: {e}", exc_info=True)
                time.sleep(self.reconnect_delay)
        
        logger.info("Connection monitor stopped")
    
    def _reconnect(self):
        """Attempt to reconnect WebSocket."""
        if self._shutdown.is_set() or not self._ws_running.is_set():
            return
        try:
            if not self._subscribed_tokens:
                logger.debug("No subscriptions to reconnect")
                return
            
            logger.info(f"Reconnecting with {len(self._subscribed_tokens)} subscriptions...")
            
            # Resubscribe
            self.client.subscribe(
                instrument_tokens=self._subscribed_tokens,
                isIndex=False,
                isDepth=False
            )
            
            self.stats['reconnections'] += 1
            logger.info("✓ Reconnected successfully")
            
        except Exception as e:
            if not self._shutdown.is_set():
                logger.error(f"Reconnection failed: {e}")
                self.stats['errors'] += 1
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with self._cache_lock:
            cache_size = len(self._cache)
        
        return {
            **self.stats,
            'cache_size': cache_size,
            'subscriptions': len(self._subscribed_tokens),
            'connected': self._ws_connected.is_set()
        }
    
    def _close_client_socket(self) -> None:
        """Best-effort attempt to close the underlying SDK WebSocket/stream."""
        c = self.client
        try:
            # Common method names used by various SDKs
            candidates = [
                "close_websocket",
                "closeWebsocket",
                "closeWebSocket",
                "close_stream",
                "stop_websocket",
                "disconnect",
                "close",
                "stop",
                "shutdown",
                "terminate",
            ]
            for name in candidates:
                if hasattr(c, name) and callable(getattr(c, name)):
                    try:
                        getattr(c, name)()
                        return
                    except Exception:
                        continue
            # Direct WS handle if exposed
            for attr in ("ws", "websocket", "socket"):
                try:
                    ws = getattr(c, attr, None)
                    if ws is not None and hasattr(ws, "close"):
                        ws.close()
                        return
                except Exception:
                    continue
        except Exception:
            pass
