#!/usr/bin/env python3
"""
⚠️ DEPRECATED - Use run_trading_service.py instead

This script is kept for manual fallback only.
The unified trading service (run_trading_service.py) handles sell orders automatically from 9:15 AM.

Automated Sell Order Runner

Runs at market open (9:15 AM) and continuously monitors sell orders until market close.
- Places limit sell orders for all open positions with EMA9 as target
- Updates orders every minute if lower EMA9 is found
- Marks positions as closed in trade history when orders execute
"""

import sys
from pathlib import Path
import argparse
import time
from datetime import datetime, time as dt_time

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger

try:
    from .sell_engine import SellOrderManager
    from .auth import KotakNeoAuth
    from .auto_trade_engine import AutoTradeEngine
    from .live_price_cache import LivePriceCache
    from .live_price_manager import LivePriceManager
    from .portfolio import KotakNeoPortfolio
    from .scrip_master import KotakNeoScripMaster
except ImportError:
    from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
    from modules.kotak_neo_auto_trader.live_price_cache import LivePriceCache
    from modules.kotak_neo_auto_trader.live_price_manager import LivePriceManager
    from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio
    from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster


def is_trading_day() -> bool:
    """Check if today is a trading day (Monday-Friday)"""
    return datetime.now().weekday() < 5  # 0-4 is Monday-Friday


def wait_until_market_open():
    """Wait until market opens at 9:15 AM"""
    now = datetime.now()
    market_open = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
    
    if now >= market_open:
        logger.info("Market already open")
        return
    
    wait_seconds = (market_open - now).total_seconds()
    logger.info(f"Waiting {wait_seconds/60:.1f} minutes until market open (9:15 AM)...")
    time.sleep(wait_seconds)
    logger.info("Market opened - starting sell order placement")


def main():
    """Main runner function"""
    parser = argparse.ArgumentParser(
        description="Automated Sell Order Management - Places and monitors profit-taking orders"
    )
    parser.add_argument(
        "--env",
        default="modules/kotak_neo_auto_trader/kotak_neo.env",
        help="Path to Kotak Neo credentials env file"
    )
    parser.add_argument(
        "--monitor-interval",
        type=int,
        default=60,
        help="Monitor interval in seconds (default: 60)"
    )
    parser.add_argument(
        "--skip-wait",
        action="store_true",
        help="Skip waiting for market open (for testing)"
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Place orders once and exit (no monitoring)"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("SELL ORDER MANAGEMENT SYSTEM")
    logger.info("=" * 60)
    
    # Check if trading day
    if not is_trading_day() and not args.skip_wait:
        logger.info("Today is not a trading day (weekend). Exiting.")
        return
    
    # Wait until market open
    if not args.skip_wait:
        wait_until_market_open()
    
    # Initialize authentication
    logger.info(f"Authenticating with Kotak Neo (env: {args.env})...")
    try:
        auth = KotakNeoAuth(args.env)
        
        if not auth.login():
            logger.error("Authentication failed. Exiting.")
            return
        
        logger.info("✅ Authentication successful")
        
    except Exception as e:
        logger.error(f"Failed to initialize auth: {e}")
        return
    
    # Initialize LivePriceManager for real-time WebSocket prices
    price_manager = None
    try:
        logger.info("Initializing LivePriceManager for real-time prices...")
        
        # Get open orders to extract symbols
        from .orders import KotakNeoOrders
        orders_api = KotakNeoOrders(auth)
        orders_response = orders_api.get_orders()
        
        # Extract symbols from open sell orders
        symbols = []
        if orders_response and 'data' in orders_response:
            for order in orders_response['data']:
                # Check if it's an open sell order
                status = (order.get('orderStatus') or order.get('ordSt') or order.get('status') or '').lower()
                txn_type = (order.get('transactionType') or order.get('trnsTp') or order.get('txnType') or '').upper()
                broker_symbol = (order.get('tradingSymbol') or order.get('trdSym') or order.get('symbol') or '').replace('-EQ', '')
                
                if status == 'open' and txn_type == 'S' and broker_symbol:
                    if broker_symbol not in symbols:
                        symbols.append(broker_symbol)
        
        if symbols:
            # Initialize scrip_master and load data
            scrip_master = KotakNeoScripMaster(exchanges=['NSE'], auth_client=auth.get_client())
            scrip_master.load_scrip_master()  # Load scrip data
            
            # Initialize LivePriceCache (use directly, not via LivePriceManager)
            price_cache = LivePriceCache(
                auth_client=auth.client,
                scrip_master=scrip_master,
                stale_threshold_seconds=60,
                reconnect_delay_seconds=5
            )
            
            # Start WebSocket service
            price_cache.start()
            logger.info("✅ WebSocket price feed started")
            
            # Wait for connection to be established before subscribing
            logger.info("Waiting for WebSocket connection...")
            if price_cache.wait_for_connection(timeout=10):
                logger.info("✅ WebSocket connection established")
            else:
                logger.warning("⚠️ WebSocket connection timeout, subscriptions may fail")
            
            # Subscribe to symbols
            price_cache.subscribe(symbols)
            price_manager = price_cache  # Use LivePriceCache directly
            
            logger.info(f"✅ LivePriceCache started for {len(symbols)} symbols: {', '.join(symbols)}")
            
            # Give it a moment to fetch initial prices
            time.sleep(2)
        else:
            logger.info("No open sell orders found, skipping LivePriceManager initialization")
            
    except Exception as e:
        logger.warning(f"Failed to initialize LivePriceManager: {e}")
        logger.info("Will fallback to yfinance for price data")
    
    # Initialize sell order manager
    try:
        sell_manager = SellOrderManager(auth, price_manager=price_manager)
        logger.info("✅ Sell Order Manager initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize Sell Order Manager: {e}")
        return
    
    try:
        # Phase 1: Place sell orders at market open
        logger.info("")
        logger.info("=" * 60)
        logger.info("PHASE 1: PLACING SELL ORDERS AT MARKET OPEN")
        logger.info("=" * 60)
        
        orders_placed = sell_manager.run_at_market_open()
        
        if orders_placed == 0:
            logger.info("No orders to place. Exiting.")
            return
        
        logger.info(f"✅ Phase 1 complete: {orders_placed} sell orders placed")
        
        # If run-once mode, exit here
        if args.run_once:
            logger.info("Run-once mode - exiting after order placement")
            return
        
        # Phase 2: Continuous monitoring
        logger.info("")
        logger.info("=" * 60)
        logger.info("PHASE 2: CONTINUOUS MONITORING")
        logger.info("=" * 60)
        logger.info(f"Monitoring every {args.monitor_interval} seconds until market close (3:30 PM)")
        logger.info("Press Ctrl+C to stop")
        
        monitor_count = 0
        total_stats = {'checked': 0, 'updated': 0, 'executed': 0}
        
        while True:
            # Check if market is still open
            now = datetime.now().time()
            market_close = dt_time(15, 30)
            
            if now > market_close:
                logger.info("")
                logger.info("=" * 60)
                logger.info("Market closed (3:30 PM) - stopping monitoring")
                logger.info("=" * 60)
                break
            
            # Monitor and update
            monitor_count += 1
            logger.info(f"\n--- Monitor Cycle #{monitor_count} ({datetime.now().strftime('%H:%M:%S')}) ---")
            
            stats = sell_manager.monitor_and_update()
            
            # Accumulate statistics
            for key in total_stats:
                total_stats[key] += stats[key]
            
            # Check if all orders executed
            if not sell_manager.active_sell_orders:
                logger.info("")
                logger.info("=" * 60)
                logger.info("All sell orders executed - no more positions to monitor")
                logger.info("=" * 60)
                break
            
            # Sleep until next cycle
            logger.debug(f"Sleeping for {args.monitor_interval} seconds...")
            time.sleep(args.monitor_interval)
        
        # Summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("SESSION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total monitor cycles: {monitor_count}")
        logger.info(f"Positions checked: {total_stats['checked']}")
        logger.info(f"Orders updated: {total_stats['updated']}")
        logger.info(f"Orders executed: {total_stats['executed']}")
        logger.info("=" * 60)
        
    except KeyboardInterrupt:
        logger.info("\n\nMonitoring stopped by user (Ctrl+C)")
        logger.info("Active sell orders will remain in the system")
        
    except Exception as e:
        logger.error(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        logger.info("\nSell order management session ended")


if __name__ == "__main__":
    main()
