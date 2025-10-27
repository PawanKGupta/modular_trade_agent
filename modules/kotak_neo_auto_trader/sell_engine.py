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
    from . import config
except ImportError:
    from auth import KotakNeoAuth
    from orders import KotakNeoOrders
    from portfolio import KotakNeoPortfolio
    from market_data import KotakNeoMarketData
    from storage import load_history, save_history
    from scrip_master import KotakNeoScripMaster
    import config


class SellOrderManager:
    """
    Manages automated sell orders with EMA9 target tracking
    """
    
    def __init__(self, auth: KotakNeoAuth, history_path: str = None, max_workers: int = 10):
        """
        Initialize sell order manager
        
        Args:
            auth: Authenticated Kotak Neo session
            history_path: Path to trade history JSON
            max_workers: Maximum threads for parallel monitoring
        """
        self.auth = auth
        self.orders = KotakNeoOrders(auth)
        self.portfolio = KotakNeoPortfolio(auth)
        self.market_data = KotakNeoMarketData(auth)
        self.history_path = history_path or config.TRADES_HISTORY_PATH
        self.max_workers = max_workers
        
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
        self.active_sell_orders: Dict[str, Dict[str, Any]] = {}
        
        # Track lowest EMA9 values {symbol: float}
        self.lowest_ema9: Dict[str, float] = {}
        
        logger.info(f"SellOrderManager initialized with {max_workers} worker threads")
    
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
            Price rounded to valid tick size
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
            # NSE uses ₹0.05 for all equity stocks (cash segment)
            tick_size = 0.05
        
        # Round to nearest tick
        # Use decimal arithmetic to avoid floating point precision issues
        from decimal import Decimal, ROUND_HALF_UP
        
        # Convert to Decimal for precise arithmetic
        price_decimal = Decimal(str(price))
        tick_decimal = Decimal(str(tick_size))
        
        # Round to nearest tick
        rounded = (price_decimal / tick_decimal).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * tick_decimal
        
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
            
            logger.debug(f"{ticker} - Yesterday EMA9: ₹{yesterday_ema9:.2f}, LTP: ₹{current_ltp:.2f}, Current EMA9: ₹{current_ema9:.2f}")
            return current_ema9
            
        except Exception as e:
            logger.error(f"Error calculating real-time EMA9 for {ticker}: {e}")
            return None
    
    def get_current_ltp(self, ticker: str, broker_symbol: str = None) -> Optional[float]:
        """
        Get current Last Traded Price for a ticker using Kotak Neo API
        Falls back to yfinance if Kotak API fails
        
        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')
            broker_symbol: Broker symbol (e.g., 'RELIANCE-EQ') - optional
            
        Returns:
            Current LTP or None
        """
        # Resolve symbol via scrip master if available
        resolved_symbol = broker_symbol
        if broker_symbol and self.scrip_master and self.scrip_master.symbol_map:
            correct_symbol = self.scrip_master.get_trading_symbol(broker_symbol)
            if correct_symbol:
                resolved_symbol = correct_symbol
                logger.debug(f"Resolved symbol: {broker_symbol} -> {resolved_symbol}")
        
        # Try Kotak Neo API first (real-time)
        if resolved_symbol:
            try:
                ltp = self.market_data.get_ltp(resolved_symbol, exchange="NSE")
                if ltp is not None:
                    logger.debug(f"{ticker} LTP from Kotak Neo: ₹{ltp:.2f}")
                    return ltp
                else:
                    logger.debug(f"Kotak Neo LTP returned None for {resolved_symbol}, trying yfinance...")
            except Exception as e:
                logger.warning(f"Kotak Neo LTP fetch failed for {resolved_symbol}: {e}, falling back to yfinance")
        
        # Fallback to yfinance (delayed but reliable)
        try:
            df = fetch_ohlcv_yf(ticker, days=1, interval='1m', add_current_day=True)
            
            if df is None or df.empty:
                logger.warning(f"No LTP data for {ticker} from yfinance")
                return None
            
            ltp = float(df['close'].iloc[-1])
            logger.debug(f"{ticker} LTP from yfinance (delayed): ₹{ltp:.2f}")
            return ltp
            
        except Exception as e:
            logger.error(f"Error fetching LTP for {ticker} from both sources: {e}")
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
            
            # Extract order ID
            order_id = (
                response.get('data', {}).get('order_id') or
                response.get('data', {}).get('neoOrdNo') or
                response.get('order', {}).get('neoOrdNo') or
                response.get('neoOrdNo')
            )
            
            if order_id:
                logger.info(f"✅ Sell order placed: {symbol} @ ₹{rounded_price:.2f}, Order ID: {order_id}")
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
            
            # Cancel existing order
            logger.info(f"Cancelling order {order_id} to update price")
            cancel_resp = self.orders.cancel_order(order_id)
            
            if not cancel_resp:
                logger.error(f"Failed to cancel order {order_id}")
                return False
            
            # Place new order with updated price
            logger.info(f"Placing new sell order: {symbol} x{qty} @ ₹{rounded_price:.2f}")
            response = self.orders.place_limit_sell(
                symbol=symbol,
                quantity=qty,
                price=rounded_price,
                variety="REGULAR",
                exchange=config.DEFAULT_EXCHANGE,
                product=config.DEFAULT_PRODUCT
            )
            
            if not response:
                logger.error(f"Failed to place updated sell order for {symbol}")
                return False
            
            # Extract new order ID
            new_order_id = (
                response.get('data', {}).get('order_id') or
                response.get('data', {}).get('neoOrdNo') or
                response.get('order', {}).get('neoOrdNo') or
                response.get('neoOrdNo')
            )
            
            if new_order_id:
                logger.info(f"✅ Order updated: {symbol} @ ₹{rounded_price:.2f}, New Order ID: {new_order_id}")
                # Update tracking
                base_symbol = symbol.split('-')[0]
                self.active_sell_orders[base_symbol] = {
                    'order_id': str(new_order_id),
                    'target_price': rounded_price,
                    'placed_symbol': symbol,
                    'qty': qty
                }
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating sell order: {e}")
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
                    logger.info(f"✅ Sell order executed: Order ID {order_id}")
            
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
    
    def run_at_market_open(self) -> int:
        """
        Place sell orders for all open positions at market open
        
        Returns:
            Number of orders placed
        """
        logger.info("🔔 Running sell order placement at market open...")
        
        open_positions = self.get_open_positions()
        if not open_positions:
            logger.info("No open positions to place sell orders")
            return 0
        
        orders_placed = 0
        
        for trade in open_positions:
            symbol = trade.get('symbol')
            ticker = trade.get('ticker')
            
            if not symbol or not ticker:
                logger.warning(f"Skipping trade with missing symbol/ticker: {trade}")
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
                self.active_sell_orders[symbol] = {
                    'order_id': order_id,
                    'target_price': ema9,
                    'placed_symbol': trade.get('placed_symbol') or f"{symbol}-EQ",
                    'qty': trade.get('qty', 0),
                    'ticker': ticker
                }
                self.lowest_ema9[symbol] = ema9
                orders_placed += 1
        
        logger.info(f"✅ Placed {orders_placed} sell orders at market open")
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
                if self.mark_position_closed(symbol, current_price, order_id):
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
            
            # Check if EMA9 is lower than lowest seen
            lowest_so_far = self.lowest_ema9.get(symbol, float('inf'))
            
            if current_ema9 < lowest_so_far:
                logger.info(f"{symbol}: New lower EMA9 found - ₹{current_ema9:.2f} (was ₹{lowest_so_far:.2f})")
                
                # Update sell order
                success = self.update_sell_order(
                    order_id=order_id,
                    symbol=order_info.get('placed_symbol'),
                    qty=order_info.get('qty'),
                    new_price=current_ema9
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
        
        if not self.active_sell_orders:
            logger.debug("No active sell orders to monitor")
            return stats
        
        logger.debug(f"Monitoring {len(self.active_sell_orders)} active sell orders in parallel...")
        
        # Check for executed orders first (single API call)
        executed_ids = self.check_order_execution()
        
        # Process all stocks in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all monitoring tasks
            future_to_symbol = {
                executor.submit(
                    self._check_and_update_single_stock,
                    symbol,
                    order_info,
                    executed_ids
                ): symbol
                for symbol, order_info in self.active_sell_orders.items()
            }
            
            # Process results as they complete
            symbols_to_remove = []
            symbols_to_update_ema = {}
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                
                try:
                    result = future.result()
                    action = result.get('action')
                    
                    if action == 'executed':
                        symbols_to_remove.append(symbol)
                        stats['executed'] += 1
                    elif action == 'updated':
                        symbols_to_update_ema[symbol] = result.get('ema9')
                        stats['updated'] += 1
                    elif action in ['checked', 'error']:
                        stats['checked'] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing result for {symbol}: {e}")
                    stats['checked'] += 1
            
            # Clean up executed orders (thread-safe, done after all futures complete)
            for symbol in symbols_to_remove:
                if symbol in self.active_sell_orders:
                    del self.active_sell_orders[symbol]
                if symbol in self.lowest_ema9:
                    del self.lowest_ema9[symbol]
            
            # Update lowest EMA9 tracking for updated orders
            for symbol, ema9 in symbols_to_update_ema.items():
                if symbol in self.active_sell_orders:
                    self.lowest_ema9[symbol] = ema9
        
        logger.info(f"Monitor cycle: {stats['checked']} checked, {stats['updated']} updated, {stats['executed']} executed")
        return stats
