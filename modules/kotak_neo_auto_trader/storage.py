#!/usr/bin/env python3
"""
Storage utilities for trades history JSON
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any

from utils.logger import logger

DEFAULT_HISTORY_TEMPLATE = {
    "trades": [],  # list of trade entries
    "failed_orders": [],  # orders that failed due to insufficient balance (to retry later)
    "last_run": None,
}


def ensure_dir(path: str):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def load_history(path: str) -> Dict[str, Any]:
    try:
        if not os.path.exists(path):
            ensure_dir(path)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_HISTORY_TEMPLATE, f, indent=2)
            return DEFAULT_HISTORY_TEMPLATE.copy()
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load trades history at {path}: {e}")
        return DEFAULT_HISTORY_TEMPLATE.copy()


essential_trade_fields = [
    "symbol", "entry_price", "entry_time", "rsi10", "ema9", "ema200",
    "capital", "qty", "rsi_entry_level", "order_response", "status"
]


def append_trade(path: str, trade: Dict[str, Any]) -> None:
    try:
        data = load_history(path)
        data.setdefault("trades", [])
        data["trades"].append(trade)
        data["last_run"] = datetime.now().isoformat()
        ensure_dir(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to append trade to history: {e}")


def save_history(path: str, data: Dict[str, Any]) -> None:
    try:
        ensure_dir(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save trades history: {e}")


def add_failed_order(path: str, failed_order: Dict[str, Any]) -> None:
    """
    Add an order that failed due to insufficient balance to retry later.
    
    Args:
        path: Path to the history file
        failed_order: Dict containing symbol, ticker, close price, qty, reason, timestamp
    """
    try:
        data = load_history(path)
        data.setdefault("failed_orders", [])
        
        # Check if this symbol already exists in failed orders (avoid duplicates)
        symbol = failed_order.get('symbol', '')
        existing = [fo for fo in data['failed_orders'] if fo.get('symbol') == symbol]
        
        if existing:
            # Update the existing failed order with latest info
            for fo in data['failed_orders']:
                if fo.get('symbol') == symbol:
                    fo.update(failed_order)
                    fo['last_retry_attempt'] = datetime.now().isoformat()
                    break
            logger.info(f"Updated existing failed order for {symbol}")
        else:
            # Add new failed order
            failed_order['first_failed_at'] = datetime.now().isoformat()
            failed_order['retry_count'] = 0
            data['failed_orders'].append(failed_order)
            logger.info(f"Added new failed order for {symbol} to retry queue")
        
        ensure_dir(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to add failed order to history: {e}")


def get_failed_orders(path: str, include_previous_day_before_market: bool = True) -> list:
    """
    Get all orders that failed due to insufficient balance.
    
    Args:
        path: Path to the history file
        include_previous_day_before_market: If True, include yesterday's orders before 9:15 AM (default: True)
    
    Returns:
        List of failed orders (valid for retry)
    """
    try:
        data = load_history(path)
        failed_orders = data.get('failed_orders', [])
        
        if not include_previous_day_before_market:
            return failed_orders
        
        now = datetime.now()
        today = now.date()
        current_time = now.time()
        
        # Market opens at 9:15 AM
        market_open_time = datetime.strptime('09:15', '%H:%M').time()
        
        valid_orders = []
        
        for order in failed_orders:
            failed_at = order.get('first_failed_at')
            if not failed_at:
                continue
            
            try:
                failed_datetime = datetime.fromisoformat(failed_at)
                failed_date = failed_datetime.date()
                
                # Same day orders - always valid
                if failed_date == today:
                    valid_orders.append(order)
                # Previous day orders - valid only before market open (9:15 AM)
                elif failed_date == today - timedelta(days=1):
                    if current_time < market_open_time:
                        valid_orders.append(order)
                        logger.info(f"Including previous day failed order for {order.get('symbol')} (before market open)")
                    else:
                        logger.debug(f"Skipping expired failed order for {order.get('symbol')} (market already opened)")
                # Older orders - expired
                else:
                    logger.debug(f"Skipping expired failed order for {order.get('symbol')} from {failed_date}")
            except Exception:
                continue
        
        return valid_orders
    except Exception as e:
        logger.error(f"Failed to get failed orders: {e}")
        return []


def remove_failed_order(path: str, symbol: str) -> None:
    """
    Remove a failed order from the retry queue (after successful placement).
    
    Args:
        path: Path to the history file
        symbol: Symbol of the order to remove
    """
    try:
        data = load_history(path)
        failed_orders = data.get('failed_orders', [])
        data['failed_orders'] = [fo for fo in failed_orders if fo.get('symbol') != symbol]
        
        ensure_dir(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Removed {symbol} from failed orders queue")
    except Exception as e:
        logger.error(f"Failed to remove failed order: {e}")


def check_manual_buys_of_failed_orders(path: str, orders_client) -> list:
    """
    Check if user manually bought any stocks from failed orders list.
    If found, add them to trade history so bot can manage them.
    
    Args:
        path: Path to the history file
        orders_client: KotakNeoOrders instance to fetch executed orders
    
    Returns:
        List of symbols that were manually bought and added to trade history
    """
    try:
        from datetime import datetime, date
        
        data = load_history(path)
        failed_orders = data.get('failed_orders', [])
        
        if not failed_orders:
            return []
        
        # Get all executed BUY orders today
        executed_orders = orders_client.get_executed_orders()
        if not executed_orders:
            return []
        
        today = date.today()
        manually_bought = []
        
        for order in executed_orders:
            # Only check BUY orders
            txn_type = (order.get('trnsTp') or order.get('transactionType') or '').upper()
            if txn_type not in ['B', 'BUY']:
                continue
            
            # Check if order is from today
            order_time_str = order.get('ordDtTm') or order.get('orderTime') or ''
            try:
                if order_time_str:
                    # Parse order date
                    order_date = datetime.strptime(order_time_str.split()[0], '%d-%b-%Y').date()
                    if order_date != today:
                        continue
            except Exception:
                # If can't parse date, skip
                continue
            
            # Extract symbol
            symbol = order.get('trdSym') or order.get('tradingSymbol') or ''
            if '-' in symbol:
                symbol = symbol.split('-')[0]
            symbol = symbol.upper()
            
            if not symbol:
                continue
            
            # Check if this symbol is in failed orders
            failed_order = next((fo for fo in failed_orders if fo.get('symbol', '').upper() == symbol), None)
            
            if failed_order:
                # This stock was recommended by bot but buy failed, now user bought it manually!
                qty = int(order.get('qty') or order.get('quantity') or order.get('fldQty') or 0)
                avg_price = float(order.get('avgPrc') or order.get('price') or 0)
                order_id = order.get('nOrdNo') or order.get('orderId') or ''
                
                if qty > 0 and avg_price > 0:
                    # Add to trade history
                    trade_entry = {
                        'symbol': symbol,
                        'ticker': failed_order.get('ticker', f'{symbol}.NS'),
                        'entry_price': avg_price,
                        'entry_time': datetime.now().isoformat(),
                        'entry_type': 'manual_buy_of_bot_recommendation',
                        'qty': qty,
                        'status': 'open',
                        'placed_symbol': order.get('trdSym') or f'{symbol}-EQ',
                        'order_id': str(order_id),
                        'capital': avg_price * qty,
                        # Copy technical data from failed order if available
                        'rsi10': failed_order.get('rsi10', 0),
                        'ema9': failed_order.get('ema9', 0),
                        'ema200': failed_order.get('ema200', 0),
                        'rsi_entry_level': failed_order.get('rsi_entry_level', 'unknown'),
                        'original_recommendation_date': failed_order.get('first_failed_at'),
                    }
                    
                    data.setdefault('trades', [])
                    data['trades'].append(trade_entry)
                    manually_bought.append(symbol)
                    
                    logger.info(f"✅ Added {symbol} to trade history (manual buy of bot recommendation, qty={qty}, price=₹{avg_price:.2f})")
        
        # Save updated history and remove these from failed orders
        if manually_bought:
            data['failed_orders'] = [fo for fo in failed_orders if fo.get('symbol', '').upper() not in [s.upper() for s in manually_bought]]
            ensure_dir(path)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Detected and added {len(manually_bought)} manual buys: {', '.join(manually_bought)}")
        
        return manually_bought
        
    except Exception as e:
        logger.error(f"Error checking manual buys: {e}")
        return []


def cleanup_expired_failed_orders(path: str) -> int:
    """
    Remove failed orders that are expired:
    - Orders from yesterday are valid until 9:15 AM today (before market open)
    - Orders from 2+ days ago are always expired
    
    Args:
        path: Path to the history file
    
    Returns:
        Number of expired orders removed
    """
    try:
        data = load_history(path)
        failed_orders = data.get('failed_orders', [])
        
        now = datetime.now()
        today = now.date()
        current_time = now.time()
        market_open_time = datetime.strptime('09:15', '%H:%M').time()
        
        kept_orders = []
        removed_count = 0
        
        for order in failed_orders:
            failed_at = order.get('first_failed_at')
            if not failed_at:
                removed_count += 1
                continue
            
            try:
                failed_datetime = datetime.fromisoformat(failed_at)
                failed_date = failed_datetime.date()
                
                # Today's orders - always keep
                if failed_date == today:
                    kept_orders.append(order)
                # Yesterday's orders - keep only before market open
                elif failed_date == today - timedelta(days=1):
                    if current_time < market_open_time:
                        kept_orders.append(order)
                    else:
                        logger.info(f"Removing expired failed order for {order.get('symbol')} from {failed_date} (market opened)")
                        removed_count += 1
                # Older orders - remove
                else:
                    logger.info(f"Removing expired failed order for {order.get('symbol')} from {failed_date}")
                    removed_count += 1
            except Exception:
                removed_count += 1
                continue
        
        if removed_count > 0:
            data['failed_orders'] = kept_orders
            ensure_dir(path)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Cleaned up {removed_count} expired failed order(s)")
        
        return removed_count
    except Exception as e:
        logger.error(f"Failed to cleanup expired orders: {e}")
        return 0
