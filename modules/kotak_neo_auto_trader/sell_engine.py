#!/usr/bin/env python3
"""
Sell Order Management Engine for Kotak Neo Auto Trader

Manages profit-taking sell orders with EMA9 target tracking:
1. Places limit sell orders at market open (9:15 AM) with daily EMA9 as target
2. Monitors and updates orders every minute with lowest EMA9 value
3. Tracks order execution and updates trade history
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime, time as dt_time
from math import floor
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger
from core.data_fetcher import fetch_ohlcv_yf
from core.indicators import compute_indicators

try:
    from .auth import KotakNeoAuth
    from .orders import KotakNeoOrders
    from .portfolio import KotakNeoPortfolio
    from .market_data import KotakNeoMarketData
    from .storage import load_history, save_history
    from .scrip_master import KotakNeoScripMaster
    from .live_price_cache import LivePriceCache
    from .order_state_manager import OrderStateManager
    from .utils.symbol_utils import extract_ticker_base, extract_base_symbol, get_lookup_symbol
    from .utils.price_manager_utils import get_ltp_from_manager
    from .utils.order_field_extractor import OrderFieldExtractor
    from .utils.order_status_parser import OrderStatusParser
    from . import config
except ImportError:
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
    from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio
    from modules.kotak_neo_auto_trader.market_data import KotakNeoMarketData
    from modules.kotak_neo_auto_trader.storage import load_history, save_history
    from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster
    from modules.kotak_neo_auto_trader.live_price_cache import LivePriceCache
    from modules.kotak_neo_auto_trader.order_state_manager import OrderStateManager
    from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_ticker_base, extract_base_symbol, get_lookup_symbol
    from modules.kotak_neo_auto_trader.utils.price_manager_utils import get_ltp_from_manager
    from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor
    from modules.kotak_neo_auto_trader.utils.order_status_parser import OrderStatusParser
    from modules.kotak_neo_auto_trader import config


class SellOrderManager:
    """
    Manages automated sell orders with EMA9 target tracking
    """
    
    def __init__(self, auth: KotakNeoAuth, history_path: str = None, max_workers: int = 10, price_manager=None, order_state_manager: Optional[OrderStateManager] = None):
        """
        Initialize sell order manager
        
        Args:
            auth: Authenticated Kotak Neo session
            history_path: Path to trade history JSON
            max_workers: Maximum threads for parallel monitoring
            price_manager: Optional LivePriceManager for real-time prices
            order_state_manager: Optional OrderStateManager for unified state management
        """
        self.auth = auth
        self.orders = KotakNeoOrders(auth)
        self.portfolio = KotakNeoPortfolio(auth)
        self.market_data = KotakNeoMarketData(auth)
        self.history_path = history_path or config.TRADES_HISTORY_PATH
        self.max_workers = max_workers
        self.price_manager = price_manager
        
        # Initialize OrderStateManager if not provided (for backward compatibility)
        self.state_manager = order_state_manager
        if self.state_manager is None:
            try:
                # Try to create OrderStateManager with same history_path
                data_dir = str(Path(self.history_path).parent) if self.history_path else "data"
                self.state_manager = OrderStateManager(
                    history_path=self.history_path,
                    data_dir=data_dir
                )
                logger.debug("OrderStateManager initialized automatically")
            except Exception as e:
                logger.debug(f"OrderStateManager not available, using legacy mode: {e}")
                self.state_manager = None
        
        # Initialize scrip master for symbol/token resolution
        self.scrip_master = KotakNeoScripMaster(
            auth_client=auth.client if hasattr(auth, 'client') else None
        )
        
        # Load scrip master data (use cache if available)
        try:
            self.scrip_master.load_scrip_master(force_download=False)
            logger.info("Scrip master loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load scrip master: {e}. Will use symbols as-is.")
        
        # Track active sell orders {symbol: {'order_id': str, 'target_price': float}}
        # Legacy mode: Used when OrderStateManager is not available
        self.active_sell_orders: Dict[str, Dict[str, Any]] = {}
        
        # Track lowest EMA9 values {symbol: float}
        self.lowest_ema9: Dict[str, float] = {}
        
        logger.info(f"SellOrderManager initialized with {max_workers} worker threads")
    
    def _register_order(self, symbol: str, order_id: str, target_price: float, qty: int, ticker: Optional[str] = None, **kwargs) -> None:
        """
        Helper method to register order using OrderStateManager if available, otherwise legacy mode.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            target_price: Target price
            qty: Quantity
            ticker: Optional ticker symbol
            **kwargs: Additional metadata
        """
        if self.state_manager:
            self.state_manager.register_sell_order(
                symbol=symbol,
                order_id=order_id,
                target_price=target_price,
                qty=qty,
                ticker=ticker,
                **kwargs
            )
            # Sync active_sell_orders for backward compatibility
            base_symbol = extract_base_symbol(symbol).upper()
            self.active_sell_orders[base_symbol] = {
                'order_id': order_id,
                'target_price': target_price,
                'qty': qty,
                'ticker': ticker,
                **kwargs
            }
        else:
            # Legacy mode
            base_symbol = extract_base_symbol(symbol).upper()
            self.active_sell_orders[base_symbol] = {
                'order_id': order_id,
                'target_price': target_price,
                'qty': qty,
                'ticker': ticker,
                **kwargs
            }
    
    def _update_order_price(self, symbol: str, new_price: float) -> bool:
        """
        Helper method to update order price using OrderStateManager if available.
        
        Args:
            symbol: Trading symbol
            new_price: New target price
            
        Returns:
            True if updated, False otherwise
        """
        if self.state_manager:
            result = self.state_manager.update_sell_order_price(symbol, new_price)
            if result:
                # Sync active_sell_orders for backward compatibility
                base_symbol = extract_base_symbol(symbol).upper()
                if base_symbol in self.active_sell_orders:
                    self.active_sell_orders[base_symbol]['target_price'] = new_price
            return result
        else:
            # Legacy mode
            base_symbol = extract_base_symbol(symbol).upper()
            if base_symbol in self.active_sell_orders:
                self.active_sell_orders[base_symbol]['target_price'] = new_price
                return True
            return False
    
    def _remove_order(self, symbol: str, reason: Optional[str] = None) -> bool:
        """
        Helper method to remove order using OrderStateManager if available.
        
        Args:
            symbol: Trading symbol
            reason: Optional reason for removal
            
        Returns:
            True if removed, False otherwise
        """
        base_symbol = extract_base_symbol(symbol).upper()
        
        if self.state_manager:
            # Always sync from OrderStateManager first to ensure consistency
            state_orders = self.state_manager.get_active_sell_orders()
            self.active_sell_orders.update(state_orders)
            
            # Try to remove from OrderStateManager (may or may not be there)
            result = self.state_manager.remove_from_tracking(symbol, reason=reason)
            
            # Always remove from self.active_sell_orders if present (for backward compatibility)
            # This ensures removal even if OrderStateManager didn't have it
            removed = False
            if base_symbol in self.active_sell_orders:
                del self.active_sell_orders[base_symbol]
                removed = True
            
            # Return True if either OrderStateManager had it or we removed from local dict
            return result or removed
        else:
            # Legacy mode
            if base_symbol in self.active_sell_orders:
                del self.active_sell_orders[base_symbol]
                return True
            return False
    
    def _get_active_orders(self) -> Dict[str, Dict[str, Any]]:
        """
        Helper method to get active orders, syncing from OrderStateManager if available.
        
        Returns:
            Dict of active sell orders
        """
        if self.state_manager:
            # Sync from OrderStateManager
            state_orders = self.state_manager.get_active_sell_orders()
            self.active_sell_orders.update(state_orders)
        
        return self.active_sell_orders
    
    def _mark_order_executed(self, symbol: str, order_id: str, execution_price: float, execution_qty: Optional[int] = None) -> bool:
        """
        Helper method to mark order as executed using OrderStateManager if available.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            execution_price: Execution price
            execution_qty: Optional execution quantity
            
        Returns:
            True if successful, False otherwise
        """
        if self.state_manager:
            result = self.state_manager.mark_order_executed(
                symbol=symbol,
                order_id=order_id,
                execution_price=execution_price,
                execution_qty=execution_qty
            )
            if result:
                # Sync active_sell_orders for backward compatibility
                base_symbol = extract_base_symbol(symbol).upper()
                if base_symbol in self.active_sell_orders:
                    del self.active_sell_orders[base_symbol]
            return result
        else:
            # Legacy mode - just remove from tracking
            base_symbol = extract_base_symbol(symbol).upper()
            if base_symbol in self.active_sell_orders:
                del self.active_sell_orders[base_symbol]
                return True
            return False
    
    @staticmethod
    def round_to_tick_size(price: float, exchange: str = "NSE") -> float:
        """
        Round price to exchange-specific tick size
        
        NSE Tick Size Rules (Cash Equity Segment):
        - All price ranges: ₹0.05 (as per NSE circular)
        
        BSE Tick Size Rules:
        - ₹0 to ₹10: ₹0.01
        - ₹10+ to ₹20: ₹0.05  
        - ₹20+ to ₹50: ₹0.05
        - ₹50+: ₹0.05
        
        Args:
            price: Price to round
            exchange: Exchange name ("NSE" or "BSE")
            
        Returns:
            Price rounded to valid tick size (rounded UP to next valid tick)
        """
        if price <= 0:
            return price
        
        # Determine tick size based on exchange and price
        if exchange.upper() == "BSE":
            # BSE has price-dependent tick sizes
            if price < 10:
                tick_size = 0.01
            else:
                tick_size = 0.05
        else:
            # NSE tick size rules (cash equity segment)
            # 0-100: ₹0.05
            # 100-1000: ₹0.05
            # 1000+: ₹0.10
            if price >= 1000:
                tick_size = 0.10
            else:
                tick_size = 0.05
        
        # Round UP to next valid tick (ceiling)
        # Use decimal arithmetic to avoid floating point precision issues
        from decimal import Decimal, ROUND_UP
        
        # Convert to Decimal for precise arithmetic
        price_decimal = Decimal(str(price))
        tick_decimal = Decimal(str(tick_size))
        
        # Round UP to next tick (always round in favor of seller)
        rounded = (price_decimal / tick_decimal).quantize(Decimal('1'), rounding=ROUND_UP) * tick_decimal
        
        # Convert back to float with 2 decimal places
        return float(rounded.quantize(Decimal('0.01')))
    
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions from trade history
        
        Returns:
            List of open trade entries
        """
        try:
            history = load_history(self.history_path)
            trades = history.get('trades', [])
            
            # Filter for open positions
            open_trades = [t for t in trades if t.get('status') == 'open']
            
            logger.info(f"Found {len(open_trades)} open positions in trade history")
            return open_trades
            
        except Exception as e:
            logger.error(f"Error loading open positions: {e}")
            return []
    
    def get_current_ema9(self, ticker: str, broker_symbol: str = None) -> Optional[float]:
        """
        Calculate real-time daily EMA9 value using current LTP
        
        EMA9 updates in real-time during trading as current candle forms.
        Formula: Today's EMA9 = (Current LTP × k) + (Yesterday's EMA9 × (1 - k))
        where k = 2 / (period + 1) = 2 / 10 = 0.2
        
        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')
            broker_symbol: Broker symbol for LTP fetch (e.g., 'RELIANCE-EQ')
            
        Returns:
            Current real-time EMA9 value or None if failed
        """
        try:
            # Step 1: Get historical daily data (exclude current day for past EMA)
            df = fetch_ohlcv_yf(ticker, days=200, interval='1d', add_current_day=False)
            
            if df is None or df.empty:
                logger.warning(f"No historical data for {ticker}")
                return None
            
            # Step 2: Calculate EMA9 on historical data
            if len(df) < 9:
                logger.warning(f"Insufficient data for EMA9 calculation: {len(df)} days")
                return None
            
            # Calculate EMA9 using exponential weighted mean
            ema_series = df['close'].ewm(span=9, adjust=False).mean()
            yesterday_ema9 = float(ema_series.iloc[-1])
            
            # Step 3: Get current LTP (today's price)
            current_ltp = self.get_current_ltp(ticker, broker_symbol)
            
            if current_ltp is None:
                logger.warning(f"No LTP available for {ticker}, using yesterday's EMA9")
                return yesterday_ema9
            
            # Step 4: Calculate today's EMA9 with current LTP
            # EMA formula: EMA_today = (Price_today × k) + (EMA_yesterday × (1 - k))
            # where k = 2 / (period + 1) = 2 / (9 + 1) = 0.2
            k = 2.0 / (9 + 1)
            current_ema9 = (current_ltp * k) + (yesterday_ema9 * (1 - k))
            
            logger.info(f"{ticker.replace('.NS', '')}: LTP=₹{current_ltp:.2f}, Yesterday EMA9=₹{yesterday_ema9:.2f} → Current EMA9=₹{current_ema9:.2f}")
            return current_ema9
            
        except Exception as e:
            logger.error(f"Error calculating real-time EMA9 for {ticker}: {e}")
            return None
    
    def get_current_ltp(self, ticker: str, broker_symbol: str = None) -> Optional[float]:
        """
        Get current Last Traded Price for a ticker
        Uses LivePriceManager if available, falls back to yfinance
        
        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')
            broker_symbol: Broker symbol (e.g., 'RELIANCE-EQ') - optional
            
        Returns:
            Current LTP or None
        """
        # Extract base symbol using utility function
        base_symbol = extract_ticker_base(ticker)
        
        # Try LivePriceCache/LivePriceManager first (real-time WebSocket prices)
        if self.price_manager:
            try:
                # Get appropriate lookup symbol (prioritize broker_symbol for correct instrument token)
                lookup_symbol = get_lookup_symbol(broker_symbol, base_symbol)
                
                # Use utility function to handle different price manager interfaces
                ltp = get_ltp_from_manager(self.price_manager, lookup_symbol, ticker)
                
                if ltp is not None:
                    logger.info(f"{base_symbol} LTP from WebSocket: ₹{ltp:.2f}")
                    return ltp
            except Exception as e:
                logger.debug(f"WebSocket LTP failed for {base_symbol}: {e}")
        
        # Fallback to yfinance (delayed ~15-20 min)
        try:
            df = fetch_ohlcv_yf(ticker, days=1, interval='1m', add_current_day=True)
            
            if df is None or df.empty:
                logger.warning(f"No LTP data for {ticker} from yfinance")
                return None
            
            ltp = float(df['close'].iloc[-1])
            logger.info(f"{base_symbol} LTP from yfinance (delayed ~15min): ₹{ltp:.2f}")
            return ltp
            
        except Exception as e:
            logger.error(f"Error fetching LTP for {ticker}: {e}")
            return None
    
    def place_sell_order(self, trade: Dict[str, Any], target_price: float) -> Optional[str]:
        """
        Place a limit sell order for a position
        
        Args:
            trade: Trade entry from history
            target_price: Target sell price (EMA9)
            
        Returns:
            Order ID if successful, None otherwise
        """
        try:
            symbol = trade.get('placed_symbol') or trade.get('symbol')
            if not symbol:
                logger.error(f"No symbol found in trade entry")
                return None
            
            # Ensure symbol has exchange suffix
            if not symbol.endswith(('-EQ', '-BE', '-BL', '-BZ')):
                symbol = f"{symbol}-EQ"
            
            # Try to get correct trading symbol from scrip master
            if self.scrip_master and self.scrip_master.symbol_map:
                correct_symbol = self.scrip_master.get_trading_symbol(symbol)
                if correct_symbol:
                    logger.debug(f"Resolved {symbol} -> {correct_symbol} via scrip master")
                    symbol = correct_symbol
            
            qty = trade.get('qty', 0)
            if qty <= 0:
                logger.warning(f"Invalid quantity {qty} for {symbol}")
                return None
            
            # Round price to valid tick size
            rounded_price = self.round_to_tick_size(target_price)
            if rounded_price != target_price:
                logger.debug(f"Rounded price from ₹{target_price:.4f} to ₹{rounded_price:.2f} (tick size)")
            
            # Place limit sell order
            logger.info(f"Placing LIMIT SELL order: {symbol} x{qty} @ ₹{rounded_price:.2f}")
            
            response = self.orders.place_limit_sell(
                symbol=symbol,
                quantity=qty,
                price=rounded_price,
                variety="REGULAR",  # Regular day order (not AMO)
                exchange=config.DEFAULT_EXCHANGE,
                product=config.DEFAULT_PRODUCT
            )
            
            if not response:
                logger.error(f"Failed to place sell order for {symbol}")
                return None
            
            # Extract order ID - try multiple response formats
            order_id = (
                response.get('nOrdNo') or  # Direct field (most common)
                response.get('data', {}).get('nOrdNo') or
                response.get('data', {}).get('order_id') or
                response.get('data', {}).get('neoOrdNo') or
                response.get('order', {}).get('neoOrdNo') or
                response.get('neoOrdNo') or
                response.get('orderId')
            )
            
            if order_id:
                logger.info(f"Sell order placed: {symbol} @ ₹{rounded_price:.2f}, Order ID: {order_id}")
                return str(order_id)
            else:
                logger.warning(f"Order placed but no ID returned: {response}")
                return None
            
        except Exception as e:
            logger.error(f"Error placing sell order: {e}")
            return None
    
    def update_sell_order(self, order_id: str, symbol: str, qty: int, new_price: float) -> bool:
        """
        Update (modify) an existing sell order with new price
        Uses modify_order API instead of cancel+replace for efficiency
        
        Args:
            order_id: Existing order ID
            symbol: Trading symbol
            qty: Order quantity
            new_price: New target price
            
        Returns:
            True if successful
        """
        try:
            # Round price to valid tick size
            rounded_price = self.round_to_tick_size(new_price)
            if rounded_price != new_price:
                logger.debug(f"Rounded price from ₹{new_price:.4f} to ₹{rounded_price:.2f} (tick size)")
            
            # Modify existing order directly (more efficient than cancel+replace)
            logger.info(f"Modifying order {order_id}: {symbol} x{qty} @ ₹{rounded_price:.2f}")
            
            modify_resp = self.orders.modify_order(
                order_id=str(order_id),
                quantity=qty,
                price=rounded_price,
                order_type="L"  # L = Limit order
            )
            
            if not modify_resp:
                logger.error(f"Failed to modify order {order_id}")
                # Fallback to cancel+replace if modify fails
                logger.info(f"Falling back to cancel+replace for order {order_id}")
                return self._cancel_and_replace_order(order_id, symbol, qty, rounded_price)
            
            # Validate modification response
            if isinstance(modify_resp, dict):
                stat = modify_resp.get('stat', '')
                if stat == 'Ok':
                    logger.info(f"Order modified successfully: {symbol} @ ₹{rounded_price:.2f}")
                    
                    # Update tracking (order_id stays same, just update price)
                    self._update_order_price(symbol, rounded_price)
                    
                    return True
                else:
                    logger.warning(f"Modify order returned non-Ok status: {modify_resp}")
                    # Fallback to cancel+replace
                    logger.info(f"Falling back to cancel+replace for order {order_id}")
                    return self._cancel_and_replace_order(order_id, symbol, qty, rounded_price)
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating sell order: {e}")
            # Try fallback on exception
            try:
                logger.info(f"Falling back to cancel+replace due to error")
                return self._cancel_and_replace_order(order_id, symbol, qty, rounded_price)
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                return False
    
    def _cancel_and_replace_order(self, order_id: str, symbol: str, qty: int, price: float) -> bool:
        """
        Fallback method: Cancel existing order and place new one
        Used when modify_order fails
        
        Args:
            order_id: Existing order ID to cancel
            symbol: Trading symbol
            qty: Order quantity
            price: New target price (already rounded)
            
        Returns:
            True if successful
        """
        try:
            # Cancel existing order
            logger.info(f"Cancelling order {order_id}")
            cancel_resp = self.orders.cancel_order(order_id)
            
            if not cancel_resp:
                logger.error(f"Failed to cancel order {order_id}")
                return False
            
            # Place new order with updated price
            logger.info(f"Placing new sell order: {symbol} x{qty} @ ₹{price:.2f}")
            response = self.orders.place_limit_sell(
                symbol=symbol,
                quantity=qty,
                price=price,
                variety="REGULAR",
                exchange=config.DEFAULT_EXCHANGE,
                product=config.DEFAULT_PRODUCT
            )
            
            if not response:
                logger.error(f"Failed to place replacement sell order for {symbol}")
                return False
            
            # Extract new order ID
            new_order_id = (
                response.get('nOrdNo') or
                response.get('data', {}).get('nOrdNo') or
                response.get('data', {}).get('order_id') or
                response.get('data', {}).get('neoOrdNo') or
                response.get('order', {}).get('neoOrdNo') or
                response.get('neoOrdNo') or
                response.get('orderId')
            )
            
            if new_order_id:
                logger.info(f"Replacement order placed: {symbol} @ ₹{price:.2f}, Order ID: {new_order_id}")
                # Update tracking with new order ID
                base_symbol = extract_base_symbol(symbol)
                old_entry = self.active_sell_orders.get(base_symbol, {})
                self._register_order(
                    symbol=symbol,
                    order_id=str(new_order_id),
                    target_price=price,
                    qty=qty,
                    ticker=old_entry.get('ticker'),
                    placed_symbol=symbol
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in cancel+replace: {e}")
            return False
    
    def check_order_execution(self) -> List[str]:
        """
        Check which sell orders have been executed
        
        Returns:
            List of executed order IDs
        """
        try:
            executed_orders = self.orders.get_executed_orders()
            
            if not executed_orders:
                return []
            
            # Filter for our tracked sell orders
            executed_ids = []
            for order in executed_orders:
                order_id = order.get('neoOrdNo') or order.get('orderId')
                if order_id and any(
                    info.get('order_id') == str(order_id) 
                    for info in self.active_sell_orders.values()
                ):
                    executed_ids.append(str(order_id))
                    logger.info(f"Sell order executed: Order ID {order_id}")
            
            return executed_ids
            
        except Exception as e:
            logger.error(f"Error checking order execution: {e}")
            return []
    
    def mark_position_closed(self, symbol: str, exit_price: float, order_id: str) -> bool:
        """
        Mark a position as closed in trade history
        
        Args:
            symbol: Trading symbol (base, without suffix)
            exit_price: Execution price
            order_id: Order ID
            
        Returns:
            True if successful
        """
        try:
            history = load_history(self.history_path)
            trades = history.get('trades', [])
            
            updated = False
            for trade in trades:
                trade_symbol = trade.get('symbol', '').upper()
                if trade_symbol == symbol.upper() and trade.get('status') == 'open':
                    # Mark as closed
                    trade['status'] = 'closed'
                    trade['exit_price'] = exit_price
                    trade['exit_time'] = datetime.now().isoformat()
                    trade['exit_reason'] = 'EMA9_TARGET'
                    trade['sell_order_id'] = order_id
                    
                    # Calculate P&L
                    entry_price = trade.get('entry_price', 0)
                    qty = trade.get('qty', 0)
                    if entry_price and qty:
                        pnl = (exit_price - entry_price) * qty
                        pnl_pct = ((exit_price / entry_price) - 1) * 100
                        trade['pnl'] = pnl
                        trade['pnl_pct'] = pnl_pct
                        logger.info(f"Position closed: {symbol} - P&L: ₹{pnl:.2f} ({pnl_pct:+.2f}%)")
                    
                    updated = True
                    break
            
            if updated:
                save_history(self.history_path, history)
                logger.info(f"Trade history updated: {symbol} marked as closed")
                return True
            else:
                logger.warning(f"No open position found for {symbol} in trade history")
                return False
            
        except Exception as e:
            logger.error(f"Error marking position closed: {e}")
            return False
    
    def is_market_open(self) -> bool:
        """
        Check if market is currently open (9:15 AM - 3:30 PM)
        
        Returns:
            True if market is open
        """
        now = datetime.now().time()
        market_open = dt_time(9, 15)
        market_close = dt_time(15, 30)
        
        return market_open <= now <= market_close
    
    def _cleanup_rejected_orders(self):
        """
        Remove rejected/cancelled orders from active tracking
        Also detects manual buys of bot-recommended stocks
        """
        try:
            # 1. Detect manual buys
            self._detect_and_handle_manual_buys()
            
            # 2. Detect manual sells and handle
            manual_sells = self._detect_manual_sells()
            if manual_sells:
                self._handle_manual_sells(manual_sells)
            
            # 3. Remove rejected/cancelled orders
            self._remove_rejected_orders()
                
        except Exception as e:
            logger.warning(f"Error cleaning up rejected orders: {e}")
    
    def _detect_and_handle_manual_buys(self) -> List[str]:
        """
        Detect manual buys of failed orders.
        
        Returns:
            List of symbols that were manually bought
        """
        from .storage import check_manual_buys_of_failed_orders
        manual_buys = check_manual_buys_of_failed_orders(self.history_path, self.orders)
        if manual_buys:
            logger.info(f"Detected {len(manual_buys)} manual buys of bot recommendations: {', '.join(manual_buys)}")
        return manual_buys
    
    def _detect_manual_sells(self) -> Dict[str, Dict[str, Any]]:
        """
        Detect manual sell orders by checking executed SELL orders.
        
        Returns:
            Dict mapping symbol -> {'qty': int, 'orders': List[Dict]}
        """
        executed_orders = self.orders.get_executed_orders()
        if not executed_orders:
            return {}
        
        manual_sells = {}
        
        for order in executed_orders:
            # Only check SELL orders
            if not OrderFieldExtractor.is_sell_order(order):
                continue
            
            order_id = OrderFieldExtractor.get_order_id(order)
            symbol = extract_base_symbol(OrderFieldExtractor.get_symbol(order))
            
            # Check if this is a manual sell (order_id not in our tracked orders)
            if not self._is_tracked_order(order_id) and symbol:
                qty = OrderFieldExtractor.get_quantity(order)
                avg_price = OrderFieldExtractor.get_price(order)
                
                if qty > 0:
                    if symbol not in manual_sells:
                        manual_sells[symbol] = {'qty': 0, 'orders': []}
                    
                    manual_sells[symbol]['qty'] += qty
                    manual_sells[symbol]['orders'].append({
                        'order_id': order_id,
                        'qty': qty,
                        'price': avg_price
                    })
        
        return manual_sells
    
    def _is_tracked_order(self, order_id: str) -> bool:
        """
        Check if order_id is in our tracked orders.
        
        Args:
            order_id: Order ID to check
            
        Returns:
            True if order is tracked, False otherwise
        """
        return any(
            info.get('order_id') == order_id 
            for info in self.active_sell_orders.values()
        )
    
    def _handle_manual_sells(self, manual_sells: Dict[str, Dict[str, Any]]):
        """
        Handle detected manual sells: cancel bot orders, update trade history.
        
        Args:
            manual_sells: Dict mapping symbol -> sell info
        """
        rejected_symbols = []
        
        for symbol, sell_info in manual_sells.items():
            symbol_upper = symbol.upper()
            
            # Skip if not in tracked orders
            tracked_symbol = next(
                (s for s in self.active_sell_orders.keys() if s.upper() == symbol_upper),
                None
            )
            if not tracked_symbol:
                continue
            
            order_info = self.active_sell_orders[tracked_symbol]
            sold_qty = sell_info['qty']
            tracked_qty = order_info.get('qty', 0)
            remaining_qty = tracked_qty - sold_qty
            
            logger.warning(f"Manual sell detected for {symbol}: sold {sold_qty} shares")
            
            # Cancel existing bot order (wrong quantity now)
            self._cancel_bot_order_for_manual_sell(symbol, order_info)
            
            # Update trade history
            self._update_trade_history_for_manual_sell(symbol, sell_info, remaining_qty)
            
            # Remove from tracking
            rejected_symbols.append(tracked_symbol)
            if remaining_qty > 0:
                logger.info(f"Removing {symbol} from tracking: will place new order with qty={remaining_qty}")
            else:
                logger.info(f"Removing {symbol} from tracking: fully sold manually")
        
        # Remove from tracking
        for symbol in rejected_symbols:
            self._remove_from_tracking(symbol)
    
    def _cancel_bot_order_for_manual_sell(self, symbol: str, order_info: Dict[str, Any]):
        """
        Cancel bot order when manual sell detected.
        
        Args:
            symbol: Symbol name
            order_info: Order info dict
        """
        order_id = order_info.get('order_id')
        if order_id:
            try:
                logger.info(f"Cancelling order {order_id} for {symbol} due to manual sale")
                self.orders.cancel_order(order_id)
            except Exception as e:
                logger.warning(f"Failed to cancel order {order_id}: {e}")
    
    def _update_trade_history_for_manual_sell(
        self, 
        symbol: str, 
        sell_info: Dict[str, Any], 
        remaining_qty: int
    ):
        """
        Update trade history for manual sell.
        
        Args:
            symbol: Symbol name
            sell_info: Manual sell info dict
            remaining_qty: Remaining quantity after manual sell
        """
        try:
            history = load_history(self.history_path)
            trades = history.get('trades', [])
            
            symbol_upper = symbol.upper()
            sold_qty = sell_info['qty']
            
            for trade in trades:
                if trade.get('symbol', '').upper() == symbol_upper and trade.get('status') == 'open':
                    if remaining_qty <= 0:
                        # Full manual exit
                        self._mark_trade_as_closed(trade, sell_info, sold_qty, 'MANUAL_EXIT')
                        logger.info(f"Trade history updated: {symbol} marked as manually closed (full exit)")
                    else:
                        # Partial manual exit
                        trade['qty'] = remaining_qty
                        
                        if 'partial_exits' not in trade:
                            trade['partial_exits'] = []
                        
                        avg_price = self._calculate_avg_price_from_orders(sell_info['orders'])
                        trade['partial_exits'].append({
                            'qty': sold_qty,
                            'exit_time': datetime.now().isoformat(),
                            'exit_reason': 'MANUAL_PARTIAL_EXIT',
                            'exit_price': avg_price,
                        })
                        
                        logger.info(f"Trade history updated: {symbol} qty reduced to {remaining_qty} (sold {sold_qty} manually)")
                    break
            
            save_history(self.history_path, history)
        except Exception as e:
            logger.warning(f"Could not update trade history for manual sale of {symbol}: {e}")
    
    def _mark_trade_as_closed(self, trade: Dict[str, Any], sell_info: Dict[str, Any], sold_qty: int, exit_reason: str):
        """
        Mark trade as closed in trade history.
        
        Args:
            trade: Trade dict from history
            sell_info: Manual sell info dict
            sold_qty: Quantity sold
            exit_reason: Exit reason string
        """
        trade['status'] = 'closed'
        trade['exit_time'] = datetime.now().isoformat()
        trade['exit_reason'] = exit_reason
        
        avg_price = self._calculate_avg_price_from_orders(sell_info['orders'])
        trade['exit_price'] = avg_price
        
        entry_price = trade.get('entry_price', 0)
        if entry_price and avg_price:
            pnl = (avg_price - entry_price) * sold_qty
            pnl_pct = ((avg_price / entry_price) - 1) * 100
            trade['pnl'] = pnl
            trade['pnl_pct'] = pnl_pct
    
    def _calculate_avg_price_from_orders(self, orders: List[Dict[str, Any]]) -> float:
        """
        Calculate average price from order list.
        
        Args:
            orders: List of order dicts with 'price' and 'qty'
            
        Returns:
            Average price as float
        """
        if not orders:
            return 0.0
        
        total_value = sum(o['price'] * o['qty'] for o in orders)
        total_qty = sum(o['qty'] for o in orders)
        
        return total_value / total_qty if total_qty > 0 else 0.0
    
    def _remove_rejected_orders(self):
        """
        Remove rejected/cancelled orders from active tracking.
        """
        all_orders = self.orders.get_orders()
        if not all_orders or 'data' not in all_orders:
            return
        
        rejected_symbols = []
        
        for symbol, order_info in list(self.active_sell_orders.items()):
            order_id = order_info.get('order_id')
            if not order_id:
                continue
            
            # Find this order in broker orders
            broker_order = self._find_order_in_broker_orders(order_id, all_orders['data'])
            if broker_order:
                # Check if order is rejected or cancelled
                if OrderStatusParser.is_rejected(broker_order) or OrderStatusParser.is_cancelled(broker_order):
                    status = OrderStatusParser.parse_status(broker_order)
                    rejected_symbols.append(symbol)
                    logger.info(f"Removing {symbol} from tracking: order {order_id} is {status.value}")
        
        # Clean up rejected/cancelled orders
        for symbol in rejected_symbols:
            self._remove_from_tracking(symbol)
        
        if rejected_symbols:
            logger.info(f"Cleaned up {len(rejected_symbols)} invalid orders from tracking")
    
    def _find_order_in_broker_orders(self, order_id: str, broker_orders: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Find order in broker orders list by order ID.
        
        Args:
            order_id: Order ID to find
            broker_orders: List of broker order dicts
            
        Returns:
            Order dict if found, None otherwise
        """
        for order in broker_orders:
            broker_order_id = OrderFieldExtractor.get_order_id(order)
            if str(broker_order_id) == str(order_id):
                return order
        return None
    
    def _remove_from_tracking(self, symbol: str, reason: Optional[str] = None):
        """
        Remove symbol from active tracking.
        
        Args:
            symbol: Symbol to remove
            reason: Optional reason for removal
        """
        self._remove_order(symbol, reason=reason)
        if symbol in self.lowest_ema9:
            del self.lowest_ema9[symbol]
    
    def has_completed_sell_order(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Check if a symbol has a completed/executed sell order.
        
        Uses get_orders() directly to get ALL orders (including completed ones).
        get_pending_orders() filters out completed orders, so we need get_orders().
        
        Args:
            symbol: Base symbol (e.g., 'DALBHARAT') or full symbol (e.g., 'DALBHARAT-EQ')
            
        Returns:
            Dict with order details {'order_id': str, 'price': float} if completed order found,
            None otherwise
        """
        try:
            # Use get_orders() directly to get ALL orders (including completed ones)
            all_orders = self.orders.get_orders()
            if not all_orders or 'data' not in all_orders:
                return None
            
            # Extract base symbol for comparison using utility function
            base_symbol = extract_base_symbol(symbol)
            
            # Check for completed SELL orders matching the symbol
            for order in all_orders.get('data', []):
                # Check transaction type - only SELL orders
                if not OrderFieldExtractor.is_sell_order(order):
                    continue
                
                # Extract order symbol using utility function
                order_symbol = OrderFieldExtractor.get_symbol(order)
                order_base_symbol = extract_base_symbol(order_symbol)
                
                # Check if symbol matches
                if order_base_symbol != base_symbol:
                    continue
                
                # Check order status - look for completed/executed/filled
                if OrderStatusParser.is_completed(order):
                    order_id = OrderFieldExtractor.get_order_id(order)
                    order_price = OrderFieldExtractor.get_price(order)
                    
                    logger.info(f"Found completed sell order for {base_symbol}: Order ID {order_id}, Price: ₹{order_price:.2f}")
                    
                    return {
                        'order_id': order_id,
                        'price': order_price
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error checking for completed sell order for {symbol}: {e}")
            return None
    
    def get_existing_sell_orders(self) -> Dict[str, Dict[str, Any]]:
        """
        Get existing pending sell orders from broker to avoid duplicates
        
        Returns:
            Dict mapping symbol -> order info {order_id, qty, price}
        """
        try:
            existing_orders = {}
            
            # Get pending orders from broker
            pending = self.orders.get_pending_orders()
            if not pending:
                return existing_orders
            
            # Filter for SELL orders only
            for order in pending:
                try:
                    if not OrderFieldExtractor.is_sell_order(order):
                        continue
                    
                    # Extract symbol (remove -EQ suffix)
                    symbol = extract_base_symbol(OrderFieldExtractor.get_symbol(order))
                    
                    # Extract order details
                    qty = OrderFieldExtractor.get_quantity(order)
                    price = OrderFieldExtractor.get_price(order)
                    order_id = OrderFieldExtractor.get_order_id(order)
                    
                    if symbol and qty > 0:
                        existing_orders[symbol.upper()] = {
                            'order_id': order_id,
                            'qty': qty,
                            'price': price
                        }
                        logger.debug(f"Found existing sell order: {symbol} x{qty} @ ₹{price:.2f}")
                        
                except Exception as e:
                    logger.debug(f"Error parsing order: {e}")
                    continue
            
            if existing_orders:
                logger.info(f"Found {len(existing_orders)} existing sell orders in broker")
            
            return existing_orders
            
        except Exception as e:
            logger.warning(f"Could not fetch existing orders: {e}. Will proceed with placement.")
            return {}
    
    def run_at_market_open(self) -> int:
        """
        Place sell orders for all open positions at market open
        Checks for existing orders to avoid duplicates
        
        Returns:
            Number of orders placed
        """
        logger.info("🔔 Running sell order placement at market open...")
        
        open_positions = self.get_open_positions()
        if not open_positions:
            logger.info("No open positions to place sell orders")
            return 0
        
        # Check for existing sell orders to avoid duplicates
        existing_orders = self.get_existing_sell_orders()
        
        orders_placed = 0
        
        for trade in open_positions:
            symbol = trade.get('symbol')
            ticker = trade.get('ticker')
            qty = trade.get('qty', 0)
            
            if not symbol or not ticker:
                logger.warning(f"Skipping trade with missing symbol/ticker: {trade}")
                continue
            
            # Check if position already has a completed sell order (already sold)
            completed_order_info = self.has_completed_sell_order(symbol)
            if completed_order_info:
                logger.info(f"Skipping {symbol}: Already has completed sell order - position already sold")
                # Update trade history to mark position as closed
                order_id = completed_order_info.get('order_id', '')
                order_price = completed_order_info.get('price', 0)
                if self.state_manager:
                    if self._mark_order_executed(symbol, order_id, order_price):
                        logger.info(f"Updated trade history: {symbol} marked as closed (Order ID: {order_id}, Price: ₹{order_price:.2f})")
                else:
                    if self.mark_position_closed(symbol, order_price, order_id):
                        logger.info(f"Updated trade history: {symbol} marked as closed (Order ID: {order_id}, Price: ₹{order_price:.2f})")
                continue
            
            # Check for existing order with same symbol and quantity (avoid duplicate)
            if symbol.upper() in existing_orders:
                existing = existing_orders[symbol.upper()]
                if existing['qty'] == qty:
                    logger.info(f"Skipping {symbol}: Existing sell order found (Order ID: {existing['order_id']}, Qty: {qty}, Price: ₹{existing['price']:.2f})")
                    # Track the existing order for monitoring
                    # IMPORTANT: Must include ticker for monitoring to work
                    self._register_order(
                        symbol=symbol,
                        order_id=existing['order_id'],
                        target_price=existing['price'],
                        qty=qty,
                        ticker=ticker,  # From trade history (e.g., GLENMARK.NS)
                        placed_symbol=trade.get('placed_symbol') or f"{symbol}-EQ"
                    )
                    self.lowest_ema9[symbol] = existing['price']
                    orders_placed += 1  # Count as placed (existing)
                    logger.debug(f"Tracked {symbol}: ticker={ticker}, order_id={existing['order_id']}")
                    continue
            
            # Get current EMA9 as target (real-time with LTP)
            broker_sym = trade.get('placed_symbol') or f"{symbol}-EQ"
            ema9 = self.get_current_ema9(ticker, broker_symbol=broker_sym)
            if not ema9:
                logger.warning(f"Skipping {symbol}: Failed to calculate EMA9")
                continue
            
            # Check if price is reasonable (not too far from entry)
            entry_price = trade.get('entry_price', 0)
            if entry_price and ema9 < entry_price * 0.95:  # More than 5% below entry
                logger.warning(f"Skipping {symbol}: EMA9 (₹{ema9:.2f}) is too low (entry: ₹{entry_price:.2f})")
                continue
            
            # Place sell order
            order_id = self.place_sell_order(trade, ema9)
            
            if order_id:
                # Track the order
                self._register_order(
                    symbol=symbol,
                    order_id=order_id,
                    target_price=ema9,
                    qty=qty,
                    ticker=ticker,
                    placed_symbol=trade.get('placed_symbol') or f"{symbol}-EQ"
                )
                self.lowest_ema9[symbol] = ema9
                orders_placed += 1
        
        # Clean up any rejected orders from tracking
        self._cleanup_rejected_orders()
        
        logger.info(f"Placed {orders_placed} sell orders at market open")
        return orders_placed
    
    def _check_and_update_single_stock(self, symbol: str, order_info: Dict[str, Any], executed_ids: List[str]) -> Dict[str, Any]:
        """
        Check and update a single stock (used for parallel processing)
        
        Args:
            symbol: Stock symbol
            order_info: Order information dict
            executed_ids: List of executed order IDs
            
        Returns:
            Dict with result info
        """
        result = {'symbol': symbol, 'action': None, 'ema9': None, 'success': False}
        
        try:
            order_id = order_info.get('order_id')
            
            # Check if this order was executed
            if order_id in executed_ids:
                current_price = order_info.get('target_price', 0)
                # Use OrderStateManager if available, otherwise legacy method
                if self.state_manager:
                    self._mark_order_executed(symbol, order_id, current_price)
                else:
                    self.mark_position_closed(symbol, current_price, order_id)
                result['action'] = 'executed'
                result['success'] = True
                return result
            
            # Get current EMA9
            ticker = order_info.get('ticker')
            if not ticker:
                logger.warning(f"No ticker found for {symbol}")
                return result
            
            broker_sym = order_info.get('placed_symbol')
            current_ema9 = self.get_current_ema9(ticker, broker_symbol=broker_sym)
            if not current_ema9:
                logger.warning(f"Failed to calculate EMA9 for {symbol}")
                return result
            
            result['ema9'] = current_ema9
            
            # Round EMA9 to tick size BEFORE comparing (avoid unnecessary updates)
            rounded_ema9 = self.round_to_tick_size(current_ema9)
            
            # Check if ROUNDED EMA9 is lower than lowest seen
            lowest_so_far = self.lowest_ema9.get(symbol, float('inf'))
            current_target = order_info.get('target_price', lowest_so_far)
            
            # Log EMA9 values for monitoring
            logger.info(f"{symbol}: Current EMA9=₹{rounded_ema9:.2f}, Target=₹{current_target:.2f}, Lowest=₹{lowest_so_far:.2f}")
            
            if rounded_ema9 < lowest_so_far:
                logger.info(f"{symbol}: New lower EMA9 found - ₹{rounded_ema9:.2f} (was ₹{lowest_so_far:.2f})")
                
                # Update sell order
                success = self.update_sell_order(
                    order_id=order_id,
                    symbol=order_info.get('placed_symbol'),
                    qty=order_info.get('qty'),
                    new_price=rounded_ema9
                )
                
                if success:
                    result['action'] = 'updated'
                    result['success'] = True
                    return result
            
            result['action'] = 'checked'
            result['success'] = True
            
        except Exception as e:
            logger.error(f"Error checking {symbol}: {e}")
            result['action'] = 'error'
        
        return result
    
    def monitor_and_update(self) -> Dict[str, int]:
        """
        Monitor EMA9 and update sell orders if lower value found (parallel processing)
        
        Returns:
            Dict with statistics
        """
        stats = {'checked': 0, 'updated': 0, 'executed': 0}
        
        # Clean up any rejected/cancelled orders before monitoring
        self._cleanup_rejected_orders()
        
        if not self.active_sell_orders:
            logger.debug("No active sell orders to monitor")
            return stats
        
        logger.debug(f"Monitoring {len(self.active_sell_orders)} active sell orders in parallel...")
        
        # Check for executed orders first (single API call)
        executed_ids = self.check_order_execution()
        
        # Remove executed orders BEFORE monitoring (don't waste API calls on executed orders)
        symbols_executed = []
        for symbol, order_info in list(self.active_sell_orders.items()):
            order_id = order_info.get('order_id')
            
            # Check if sell order has been completed (via get_orders() to catch all statuses)
            completed_order_info = self.has_completed_sell_order(symbol)
            if completed_order_info:
                logger.info(f"{symbol} sell order completed - removing from monitoring")
                # Mark position as closed in trade history
                # Use order price from completed order info, fallback to target_price
                order_price = completed_order_info.get('price', 0)
                if order_price == 0:
                    order_price = order_info.get('target_price', 0)
                
                # Use order_id from completed order info if available, fallback to tracked order_id
                completed_order_id = completed_order_info.get('order_id', '')
                if not completed_order_id:
                    completed_order_id = order_id or 'completed'
                
                if self.state_manager:
                    if self._mark_order_executed(symbol, completed_order_id, order_price):
                        symbols_executed.append(symbol)
                        logger.info(f"Position closed: {symbol} - removing from tracking")
                else:
                    if self.mark_position_closed(symbol, order_price, completed_order_id):
                        symbols_executed.append(symbol)
                        logger.info(f"Position closed: {symbol} - removing from tracking")
                continue
            
            # Also check executed_ids (from get_executed_orders())
            if order_id in executed_ids:
                # Mark position as closed in trade history
                current_price = order_info.get('target_price', 0)
                if self.state_manager:
                    if self._mark_order_executed(symbol, order_id, current_price):
                        symbols_executed.append(symbol)
                        logger.info(f"Order executed: {symbol} - removing from tracking")
                else:
                    if self.mark_position_closed(symbol, current_price, order_id):
                        symbols_executed.append(symbol)
                        logger.info(f"Order executed: {symbol} - removing from tracking")
        
        # Clean up executed orders
        for symbol in symbols_executed:
            # Remove from tracking (OrderStateManager handles this if available)
            self._remove_order(symbol, reason="Executed")
            if symbol in self.lowest_ema9:
                del self.lowest_ema9[symbol]
        
        stats['executed'] = len(symbols_executed)
        
        # If no orders left to monitor, return
        if not self.active_sell_orders:
            if stats['executed'] > 0:
                logger.info(f"Monitor cycle: {stats['executed']} executed, all orders completed")
            return stats
        
        # Process remaining active stocks in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all monitoring tasks (only for non-executed orders)
            future_to_symbol = {
                executor.submit(
                    self._check_and_update_single_stock,
                    symbol,
                    order_info,
                    []  # Empty list - executed orders already removed
                ): symbol
                for symbol, order_info in self.active_sell_orders.items()
            }
            
            # Process results as they complete
            symbols_to_update_ema = {}
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                
                try:
                    result = future.result()
                    action = result.get('action')
                    
                    if action == 'updated':
                        symbols_to_update_ema[symbol] = result.get('ema9')
                        stats['updated'] += 1
                    elif action in ['checked', 'error']:
                        stats['checked'] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing result for {symbol}: {e}")
                    stats['checked'] += 1
            
            # Update lowest EMA9 tracking for updated orders
            for symbol, ema9 in symbols_to_update_ema.items():
                if symbol in self.active_sell_orders:
                    self.lowest_ema9[symbol] = ema9
        
        logger.info(f"Monitor cycle: {stats['checked']} checked, {stats['updated']} updated, {stats['executed']} executed")
        return stats
