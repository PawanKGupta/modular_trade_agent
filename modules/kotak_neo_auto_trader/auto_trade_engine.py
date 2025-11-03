#!/usr/bin/env python3
"""
Auto Trade Engine for Kotak Neo
- Reads recommendations (from analysis_results CSV)
- Places AMO buy orders within portfolio constraints
- Tracks positions and executes re-entry and exit based on RSI/EMA
"""

import os
import glob
from dataclasses import dataclass
from math import floor
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple

# Project logger
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

# Core market data
from core.data_fetcher import fetch_ohlcv_yf
from core.indicators import compute_indicators
from core.scoring import compute_strength_score
from core.telegram import send_telegram

# Kotak Neo modules
try:
    from .trader import KotakNeoTrader
    from .orders import KotakNeoOrders
    from .portfolio import KotakNeoPortfolio
    from .auth import KotakNeoAuth
    from .scrip_master import KotakNeoScripMaster
    from . import config
    from .storage import load_history, save_history, append_trade, add_failed_order, get_failed_orders, remove_failed_order, cleanup_expired_failed_orders, check_manual_buys_of_failed_orders
    from .tracking_scope import add_tracked_symbol, is_tracked, get_tracked_symbols, update_tracked_qty
    from .order_tracker import extract_order_id, add_pending_order, search_order_in_broker_orderbook
    # Phase 2 modules
    from .order_status_verifier import get_order_status_verifier
    from .telegram_notifier import get_telegram_notifier
    from .manual_order_matcher import get_manual_order_matcher
    from .eod_cleanup import get_eod_cleanup, schedule_eod_cleanup
except ImportError:
    from modules.kotak_neo_auto_trader.trader import KotakNeoTrader
    from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
    from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster
    from modules.kotak_neo_auto_trader import config
    from modules.kotak_neo_auto_trader.storage import load_history, save_history, append_trade, add_failed_order, get_failed_orders, remove_failed_order, cleanup_expired_failed_orders, check_manual_buys_of_failed_orders
    from modules.kotak_neo_auto_trader.tracking_scope import add_tracked_symbol, is_tracked, get_tracked_symbols, update_tracked_qty
    from modules.kotak_neo_auto_trader.order_tracker import extract_order_id, add_pending_order, search_order_in_broker_orderbook
    # Phase 2 modules
    from modules.kotak_neo_auto_trader.order_status_verifier import get_order_status_verifier
    from modules.kotak_neo_auto_trader.telegram_notifier import get_telegram_notifier
    from modules.kotak_neo_auto_trader.manual_order_matcher import get_manual_order_matcher
    from modules.kotak_neo_auto_trader.eod_cleanup import get_eod_cleanup, schedule_eod_cleanup


@dataclass
class Recommendation:
    ticker: str  # e.g. RELIANCE.NS
    verdict: str  # strong_buy|buy|watch
    last_close: float


class AutoTradeEngine:
    def __init__(
        self,
        env_file: str = "kotak_neo.env",
        auth: Optional[KotakNeoAuth] = None,
        enable_verifier: bool = True,
        enable_telegram: bool = True,
        enable_eod_cleanup: bool = True,
        verifier_interval: int = 1800
    ):
        self.env_file = env_file
        self.auth = auth if auth is not None else KotakNeoAuth(env_file)
        self.orders: Optional[KotakNeoOrders] = None
        self.portfolio: Optional[KotakNeoPortfolio] = None
        self.history_path = config.TRADES_HISTORY_PATH
        
        # Initialize scrip master for symbol resolution
        self.scrip_master: Optional[KotakNeoScripMaster] = None
        
        # Phase 2 modules configuration
        self._enable_verifier = enable_verifier
        self._enable_telegram = enable_telegram
        self._enable_eod_cleanup = enable_eod_cleanup
        self._verifier_interval = verifier_interval
        
        # Phase 2 module instances (initialized in login)
        self.telegram_notifier = None
        self.order_verifier = None
        self.manual_matcher = None
        self.eod_cleanup = None

    # ---------------------- Utilities ----------------------
    @staticmethod
    def parse_symbol_for_broker(ticker: str) -> str:
        # Convert 'RELIANCE.NS' -> 'RELIANCE'
        return ticker.replace(".NS", "").upper()

    @staticmethod
    def is_trading_weekday(d: Optional[date] = None) -> bool:
        d = d or datetime.now().date()
        return d.weekday() in config.MARKET_DAYS

    @staticmethod
    def market_was_open_today() -> bool:
        # Try NIFTY 50 index to detect trading day
        try:
            df = fetch_ohlcv_yf("^NSEI", days=5, interval='1d', add_current_day=True)
            if df is None or df.empty:
                return False
            latest = df['date'].iloc[-1].date()
            return latest == datetime.now().date()
        except Exception:
            # If detection fails, fallback to weekday check only
            return AutoTradeEngine.is_trading_weekday()

    @staticmethod
    def load_latest_recommendations_from_csv(csv_path: str) -> List[Recommendation]:
        import pandas as pd
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.error(f"Failed to read recommendations CSV {csv_path}: {e}")
            return []
        # If CSV already has post-scored fields, use them
        if 'final_verdict' in df.columns:
            from . import config as _cfg
            verdict_col = 'final_verdict'
            # Apply combined_score threshold if present (default from config)
            if 'combined_score' in df.columns:
                th = getattr(_cfg, 'MIN_COMBINED_SCORE', 25)
                df_buy = df[
                    df[verdict_col].astype(str).str.lower().isin(['buy','strong_buy']) &
                    (df['combined_score'].fillna(0) >= th) &
                    (df.get('status', 'success') == 'success')
                ]
            else:
                df_buy = df[df[verdict_col].astype(str).str.lower().isin(['buy','strong_buy'])]
            recs = []
            for _, row in df_buy.iterrows():
                ticker = str(row.get('ticker','')).strip().upper()
                last_close = float(row.get('last_close', 0) or 0)
                recs.append(Recommendation(ticker=ticker, verdict=row[verdict_col], last_close=last_close))
            logger.info(f"Loaded {len(recs)} BUY recommendations from {csv_path}")
            return recs
        # Otherwise, DO NOT recompute; trust the CSV that trade_agent produced
        if 'verdict' in df.columns:
            df_buy = df[df['verdict'].astype(str).str.lower().isin(['buy','strong_buy'])]
            recs = [Recommendation(ticker=str(row.get('ticker','')).strip().upper(), verdict=str(row.get('verdict','')).lower(), last_close=float(row.get('last_close', 0) or 0)) for _, row in df_buy.iterrows()]
            logger.info(f"Loaded {len(recs)} BUY recommendations from {csv_path} (raw verdicts)")
            return recs
        logger.warning(f"CSV {csv_path} missing 'final_verdict' and 'verdict' columns; no recommendations loaded")
        return []

    def load_latest_recommendations(self) -> List[Recommendation]:
        # If a custom CSV path is set (from runner), use it
        if hasattr(self, '_custom_csv_path') and self._custom_csv_path:
            return self.load_latest_recommendations_from_csv(self._custom_csv_path)
        path = config.ANALYSIS_DIR
        # Prefer post-scored CSV; fallback to base if not present
        patterns = [
            os.path.join(path, getattr(config, 'RECOMMENDED_CSV_GLOB', 'bulk_analysis_final_*.csv')),
            os.path.join(path, 'bulk_analysis_*.csv'),
        ]
        files = []
        for pat in patterns:
            files = sorted(glob.glob(pat), key=os.path.getmtime, reverse=True)
            if files:
                break
        if not files:
            logger.warning(f"No recommendation CSV found in {path}")
            return []
        latest = files[0]
        return self.load_latest_recommendations_from_csv(latest)

    @staticmethod
    def get_daily_indicators(ticker: str) -> Optional[Dict[str, Any]]:
        try:
            from sys import path as sys_path
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent
            if str(project_root) not in sys_path:
                sys_path.insert(0, str(project_root))
            from config.settings import VOLUME_LOOKBACK_DAYS
            
            df = fetch_ohlcv_yf(ticker, days=800, interval='1d', add_current_day=False)
            df = compute_indicators(df)
            if df is None or df.empty:
                return None
            last = df.iloc[-1]
            # Calculate average volume over configurable period (default: 50 days)
            avg_vol = df['volume'].tail(VOLUME_LOOKBACK_DAYS).mean() if 'volume' in df.columns else 0
            return {
                'close': float(last['close']),
                'rsi10': float(last['rsi10']),
                'ema9': float(df['close'].ewm(span=config.EMA_SHORT).mean().iloc[-1]) if 'ema9' not in df.columns else float(last.get('ema9', 0)),
                'ema200': float(last['ema200']) if 'ema200' in df.columns else float(df['close'].ewm(span=config.EMA_LONG).mean().iloc[-1]),
                'avg_volume': float(avg_vol)
            }
        except Exception as e:
            logger.warning(f"Failed to get indicators for {ticker}: {e}")
            return None
    
    @staticmethod
    def check_position_volume_ratio(qty: int, avg_volume: float, symbol: str, price: float = 0) -> bool:
        """Check if position size is within acceptable range of daily volume based on stock price."""
        from sys import path as sys_path
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys_path:
            sys_path.insert(0, str(project_root))
        from config.settings import POSITION_VOLUME_RATIO_TIERS
        
        if avg_volume <= 0:
            logger.warning(f"{symbol}: No volume data available")
            return False
        
        # Determine max ratio based on stock price tier
        max_ratio = 0.20  # Default: 20% for unknown price
        tier_used = "default (20%)"
        
        if price > 0:
            # Find applicable tier (sorted descending by price threshold)
            for price_threshold, ratio_limit in POSITION_VOLUME_RATIO_TIERS:
                if price >= price_threshold:
                    max_ratio = ratio_limit
                    if price_threshold > 0:
                        tier_used = f"₹{price_threshold}+ ({ratio_limit:.1%})"
                    else:
                        tier_used = f"<₹500 ({ratio_limit:.1%})"
                    break
        
        ratio = qty / avg_volume
        if ratio > max_ratio:
            logger.warning(
                f"{symbol}: Position too large relative to volume "
                f"(price=₹{price:.2f}, qty={qty}, avg_vol={int(avg_volume)}, "
                f"ratio={ratio:.1%} > {max_ratio:.1%} for tier {tier_used})"
            )
            return False
        
        logger.debug(
            f"{symbol}: Volume check passed (ratio={ratio:.2%} of daily volume, "
            f"tier={tier_used})"
        )
        return True

    def reconcile_holdings_to_history(self) -> None:
        """
        Add holdings to history - ONLY for system-recommended (tracked) symbols.
        Non-tracked symbols are completely ignored.
        Also performs manual trade reconciliation if enabled.
        """
        try:
            if not self.portfolio:
                return
            
            # Phase 2: Manual trade reconciliation
            if self.manual_matcher and self._enable_telegram:
                try:
                    holdings_response = self.portfolio.get_holdings()
                    if holdings_response and isinstance(holdings_response, dict):
                        holdings = holdings_response.get('data', [])
                        reconciliation = self.manual_matcher.reconcile_holdings_with_tracking(holdings)
                        
                        # Log any discrepancies
                        if reconciliation.get('discrepancies'):
                            summary = self.manual_matcher.get_reconciliation_summary(reconciliation)
                            logger.info(f"\n{summary}")
                            
                            # Send Telegram notifications for manual trades
                            if self.telegram_notifier:
                                for disc in reconciliation.get('discrepancies', []):
                                    symbol = disc.get('symbol')
                                    qty_diff = disc.get('qty_diff', 0)
                                    broker_qty = disc.get('broker_qty', 0)
                                    
                                    if disc.get('trade_type') == 'MANUAL_BUY':
                                        message = (
                                            f"📈 *MANUAL BUY DETECTED*\n\n"
                                            f"📊 Symbol: {symbol}\n"
                                            f"📦 Quantity: +{qty_diff} shares\n"
                                            f"💼 New Total: {broker_qty} shares\n"
                                            f"⏰ Detected: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                            f"ℹ️ Tracking updated automatically"
                                        )
                                        self.telegram_notifier.send_message(message)
                                    
                                    elif disc.get('trade_type') == 'MANUAL_SELL':
                                        message = (
                                            f"📉 *MANUAL SELL DETECTED*\n\n"
                                            f"📊 Symbol: {symbol}\n"
                                            f"📦 Quantity: {qty_diff} shares\n"
                                            f"💼 Remaining: {broker_qty} shares\n"
                                            f"⏰ Detected: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                            f"ℹ️ Tracking updated automatically"
                                        )
                                        self.telegram_notifier.send_message(message)
                        
                        # Notify about position closures
                        closed_positions = reconciliation.get('closed_positions', [])
                        if closed_positions and self.telegram_notifier:
                            for symbol in closed_positions:
                                self.telegram_notifier.notify_tracking_stopped(
                                    symbol,
                                    "Position fully closed (manual sell detected)"
                                )
                except Exception as e:
                    logger.error(f"Manual trade reconciliation error: {e}")
            
            # Get list of symbols actively tracked by system
            tracked_symbols = get_tracked_symbols(status="active")
            if not tracked_symbols:
                logger.debug("No tracked symbols - skipping reconciliation")
                return
            
            logger.info(f"Reconciling holdings for {len(tracked_symbols)} tracked symbols")
            
            hist = load_history(self.history_path)
            existing = {t.get('symbol') for t in hist.get('trades', []) if t.get('status') == 'open'}
            h = self.portfolio.get_holdings() or {}
            
            added = 0
            skipped_not_tracked = 0
            
            for item in (h.get('data') or []):
                sym = str(item.get('tradingSymbol') or '').upper().strip()
                if not sym or sym == 'N/A':
                    continue
                    
                base = sym.split('-')[0].strip()
                if not base or not base.isalnum():
                    continue
                
                # CRITICAL: Only process if this symbol is tracked
                if not is_tracked(base):
                    skipped_not_tracked += 1
                    logger.debug(f"Skipping {base} - not system-recommended")
                    continue
                
                # Already in history
                if base in (s.split('-')[0] for s in existing if s):
                    continue
                
                # Add tracked holding to history
                ticker = f"{base}.NS"
                ind = self.get_daily_indicators(ticker) or {}
                qty = int(item.get('quantity') or 0)
                entry_price = item.get('avgPrice') or item.get('price') or item.get('ltp') or ind.get('close')
                
                trade = {
                    'symbol': base,
                    'placed_symbol': sym,
                    'ticker': ticker,
                    'entry_price': float(entry_price) if entry_price else None,
                    'entry_time': datetime.now().isoformat(),
                    'rsi10': ind.get('rsi10'),
                    'ema9': ind.get('ema9'),
                    'ema200': ind.get('ema200'),
                    'capital': None,
                    'qty': qty,
                    'rsi_entry_level': None,
                    'levels_taken': None,
                    'reset_ready': False,
                    'order_response': None,
                    'status': 'open',
                    'entry_type': 'system_recommended',
                }
                append_trade(self.history_path, trade)
                added += 1
                logger.debug(f"Added tracked holding to history: {base}")
            
            if added:
                logger.info(
                    f"Reconciled {added} system-recommended holding(s) into history "
                    f"(skipped {skipped_not_tracked} non-tracked holdings)"
                )
            elif skipped_not_tracked > 0:
                logger.info(
                    f"Reconciliation complete: {skipped_not_tracked} non-tracked holdings ignored"
                )
                
        except Exception as e:
            logger.warning(f"Reconcile holdings failed: {e}")

    # ---------------------- Session ----------------------
    def login(self) -> bool:
        ok = self.auth.login()
        if ok:
            self.orders = KotakNeoOrders(self.auth)
            self.portfolio = KotakNeoPortfolio(self.auth)
            
            # Initialize scrip master for symbol resolution
            try:
                self.scrip_master = KotakNeoScripMaster(
                    auth_client=self.auth.client if hasattr(self.auth, 'client') else None
                )
                self.scrip_master.load_scrip_master(force_download=False)
                logger.info("Scrip master loaded for buy order symbol resolution")
            except Exception as e:
                logger.warning(f"Failed to load scrip master: {e}. Will use symbol fallback.")
                self.scrip_master = None
            
            # Phase 2: Initialize modules
            self._initialize_phase2_modules()
        return ok
    
    def _initialize_phase2_modules(self) -> None:
        """Initialize Phase 2 modules (verifier, telegram, etc.)."""
        try:
            # 1. Initialize Telegram Notifier
            if self._enable_telegram:
                self.telegram_notifier = get_telegram_notifier()
                logger.info(f"Telegram notifier initialized (enabled: {self.telegram_notifier.enabled})")
            
            # 2. Initialize Manual Order Matcher
            self.manual_matcher = get_manual_order_matcher()
            logger.info("Manual order matcher initialized")
            
            # 3. Initialize Order Status Verifier with callbacks
            if self._enable_verifier:
                def on_rejection(symbol: str, order_id: str, reason: str):
                    """Callback when order is rejected."""
                    logger.warning(f"Order rejected: {symbol} ({order_id}) - {reason}")
                    if self.telegram_notifier and self.telegram_notifier.enabled:
                        # Get quantity from pending orders
                        from .order_tracker import get_order_tracker
                        tracker = get_order_tracker()
                        pending_order = tracker.get_order_by_id(order_id)
                        qty = pending_order.get('qty', 0) if pending_order else 0
                        self.telegram_notifier.notify_order_rejection(
                            symbol, order_id, qty, reason
                        )
                
                def on_execution(symbol: str, order_id: str, qty: int):
                    """Callback when order is executed."""
                    logger.info(f"Order executed: {symbol} ({order_id}) - {qty} shares")
                    if self.telegram_notifier and self.telegram_notifier.enabled:
                        self.telegram_notifier.notify_order_execution(
                            symbol, order_id, qty
                        )
                
                self.order_verifier = get_order_status_verifier(
                    broker_client=self.orders,
                    check_interval_seconds=self._verifier_interval,
                    on_rejection_callback=on_rejection,
                    on_execution_callback=on_execution
                )
                
                # Start verifier in background
                self.order_verifier.start()
                logger.info(
                    f"Order status verifier started "
                    f"(check interval: {self._verifier_interval}s)"
                )
            
            # 4. Initialize EOD Cleanup (but don't schedule yet - done in run())
            if self._enable_eod_cleanup:
                self.eod_cleanup = get_eod_cleanup(
                    broker_client=self.portfolio,  # Use portfolio for holdings access
                    order_verifier=self.order_verifier,
                    manual_matcher=self.manual_matcher,
                    telegram_notifier=self.telegram_notifier
                )
                logger.info("EOD cleanup initialized")
            
            logger.info("✓ Phase 2 modules initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Phase 2 modules: {e}", exc_info=True)
            logger.warning("Continuing without Phase 2 features")

    def monitor_positions(self, live_price_manager=None) -> Dict[str, Any]:
        """
        Monitor all open positions for reentry/exit signals.
        
        Args:
            live_price_manager: Optional shared LivePriceCache/LivePriceManager instance
                               to avoid duplicate auth sessions and WebSocket connections
        
        Returns:
            Dict with monitoring results
        """
        try:
            from .position_monitor import PositionMonitor, get_telegram_notifier
            
            # Use direct instantiation to pass shared live_price_manager
            # This avoids creating duplicate auth sessions and WebSocket connections
            telegram = get_telegram_notifier() if self._enable_telegram else None
            
            monitor = PositionMonitor(
                history_path=self.history_path,
                telegram_notifier=telegram,
                enable_alerts=self._enable_telegram,
                live_price_manager=live_price_manager,  # Pass shared instance
                enable_realtime_prices=True
            )
            
            # Run monitoring
            results = monitor.monitor_all_positions()
            
            return results
            
        except Exception as e:
            logger.error(f"Position monitoring failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                'monitored': 0,
                'alerts_sent': 0,
                'exit_imminent': 0,
                'averaging_opportunities': 0
            }
    
    def logout(self):
        # Phase 2: Stop verifier before logout
        if self.order_verifier and self.order_verifier.is_running():
            logger.info("Stopping order status verifier...")
            self.order_verifier.stop()
        
        self.auth.logout()

    # ---------------------- Portfolio helpers ----------------------
    def _response_requires_2fa(self, resp) -> bool:
        try:
            s = str(resp)
            return '2fa' in s.lower() or 'complete the 2fa' in s.lower()
        except Exception:
            return False

    def _fetch_holdings_symbols(self) -> List[str]:
        symbols = set()
        if not self.portfolio:
            return []
        # First attempt
        h = self.portfolio.get_holdings()
        # If 2FA gating detected, force re-login and retry once
        if self._response_requires_2fa(h) and hasattr(self.auth, 'force_relogin'):
            try:
                if self.auth.force_relogin():
                    h = self.portfolio.get_holdings()
            except Exception:
                pass
        data = (h or {}).get('data') if isinstance(h, dict) else None
        for item in (data or []):
            sym = str(item.get('tradingSymbol') or '').upper()
            if sym:
                symbols.add(sym)
        return sorted(symbols)

    def current_symbols_in_portfolio(self) -> List[str]:
        symbols = set(self._fetch_holdings_symbols())
        # Include pending BUY orders too
        pend = self.orders.get_pending_orders() if self.orders else []
        for o in pend or []:
            if str(o.get('transactionType', '')).upper().startswith('B'):
                sym = str(o.get('tradingSymbol') or '').upper()
                if sym:
                    symbols.add(sym)
        return sorted(symbols)

    def portfolio_size(self) -> int:
        return len(self.current_symbols_in_portfolio())

    def get_affordable_qty(self, price: float) -> int:
        """Return maximum whole quantity affordable from available cash/margin."""
        if not self.portfolio or not price or price <= 0:
            return 0
        lim = self.portfolio.get_limits() or {}
        data = lim.get('data') if isinstance(lim, dict) else None
        avail = 0.0
        used_key = None
        if isinstance(data, dict):
            # Prefer explicit cash-like fields first (CNC), then margin keys, then Net
            candidates = [
                'cash', 'availableCash', 'available_cash',
                'availableBalance', 'available_balance', 'available_bal',
                'fundsAvailable', 'funds_available', 'fundAvailable',
                'marginAvailable', 'margin_available', 'availableMargin',
                'Net', 'net'
            ]
            for k in candidates:
                try:
                    v = data.get(k)
                    if v is None or v == '':
                        continue
                    fv = float(v)
                    if fv > 0:
                        avail = fv
                        used_key = k
                        break
                except Exception:
                    continue
            # Absolute fallback: pick the max numeric value in the payload
            if avail <= 0:
                try:
                    nums = []
                    for v in data.values():
                        try:
                            nums.append(float(v))
                        except Exception:
                            pass
                    if nums:
                        avail = max(nums)
                        used_key = used_key or 'max_numeric_field'
                except Exception:
                    pass
        logger.debug(
            f"Available balance: ₹{avail:.2f} (from limits API; key={used_key or 'n/a'})"
        )
        try:
            from math import floor
            return max(0, floor(avail / float(price)))
        except Exception:
            return 0

    def get_available_cash(self) -> float:
        """Return available funds from limits with robust field fallbacks."""
        if not self.portfolio:
            return 0.0
        lim = self.portfolio.get_limits() or {}
        data = lim.get('data') if isinstance(lim, dict) else None
        avail = 0.0
        used_key = None
        if isinstance(data, dict):
            try:
                # Prefer cash-like fields first, then margin, then Net
                candidates = [
                    'cash', 'availableCash', 'available_cash',
                    'availableBalance', 'available_balance', 'available_bal',
                    'fundsAvailable', 'funds_available', 'fundAvailable',
                    'marginAvailable', 'margin_available', 'availableMargin',
                    'Net', 'net'
                ]
                for k in candidates:
                    v = data.get(k)
                    if v is None or v == '':
                        continue
                    try:
                        fv = float(v)
                    except Exception:
                        continue
                    if fv > 0:
                        avail = fv
                        used_key = k
                        break
                # Absolute fallback: use the max numeric value in payload
                if avail <= 0:
                    nums = []
                    for v in data.values():
                        try:
                            nums.append(float(v))
                        except Exception:
                            pass
                    if nums:
                        avail = max(nums)
                        used_key = used_key or 'max_numeric_field'
                logger.debug(
                    f"Available cash from limits API: ₹{avail:.2f} (key={used_key or 'n/a'})"
                )
                return float(avail)
            except Exception as e:
                logger.warning(f"Error parsing available cash: {e}")
                return 0.0
        logger.debug("Limits API returned no usable 'data' object; assuming ₹0.00 available")
        return 0.0

    # ---------------------- De-dup helpers ----------------------
    @staticmethod
    def _symbol_variants(base: str) -> List[str]:
        base = base.upper()
        return [base, f"{base}-EQ", f"{base}-BE", f"{base}-BL", f"{base}-BZ"]

    def has_holding(self, base_symbol: str) -> bool:
        if not self.portfolio:
            return False
        variants = set(self._symbol_variants(base_symbol))
        h = self.portfolio.get_holdings() or {}
        
        # Check for 2FA gate - if detected, force re-login and retry once
        if self._response_requires_2fa(h) and hasattr(self.auth, 'force_relogin'):
            logger.info(f"2FA gate detected in holdings check, attempting re-login...")
            try:
                if self.auth.force_relogin():
                    h = self.portfolio.get_holdings() or {}
                    logger.debug(f"Holdings re-fetched after re-login")
            except Exception as e:
                logger.warning(f"Re-login failed during holdings check: {e}")
        
        for item in (h.get('data') or []):
            sym = str(item.get('tradingSymbol') or '').upper()
            if sym in variants:
                return True
        return False

    def has_active_buy_order(self, base_symbol: str) -> bool:
        if not self.orders:
            return False
        variants = set(self._symbol_variants(base_symbol))
        pend = self.orders.get_pending_orders() or []
        for o in pend:
            txn = str(o.get('transactionType') or '').upper()
            sym = str(o.get('tradingSymbol') or '').upper()
            if txn.startswith('B') and sym in variants:
                return True
        return False

    def reentries_today(self, base_symbol: str) -> int:
        """Count successful re-entries recorded today for this symbol (base symbol)."""
        try:
            hist = load_history(self.history_path)
            trades = hist.get('trades') or []
            today = datetime.now().date()
            cnt = 0
            for t in trades:
                if t.get('entry_type') != 'reentry':
                    continue
                sym = str(t.get('symbol') or '').upper()
                if sym != base_symbol.upper():
                    continue
                ts = t.get('entry_time')
                if not ts:
                    continue
                try:
                    d = datetime.fromisoformat(ts).date()
                except Exception:
                    try:
                        d = datetime.strptime(ts.split('T')[0], '%Y-%m-%d').date()
                    except Exception:
                        continue
                if d == today:
                    cnt += 1
            return cnt
        except Exception:
            return 0

    def _attempt_place_order(
        self,
        broker_symbol: str,
        ticker: str,
        qty: int,
        close: float,
        ind: Dict[str, Any],
        recommendation_source: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Helper method to attempt placing an order with symbol resolution.
        
        Args:
            broker_symbol: Trading symbol
            ticker: Full ticker (e.g., RELIANCE.NS)
            qty: Order quantity
            close: Current close price
            ind: Market indicators dict
            recommendation_source: Source of recommendation (e.g., CSV file)
        
        Returns:
            Tuple of (success: bool, order_id: Optional[str])
        """
        resp = None
        placed_symbol = None
        placement_time = datetime.now().isoformat()
        
        # Determine if this is a BE/BL/BZ segment stock (trade-to-trade)
        # These segments require LIMIT orders, not MARKET orders
        is_t2t_segment = any(broker_symbol.upper().endswith(suf) for suf in ["-BE", "-BL", "-BZ"])
        
        # For T2T segments, use limit order at current price + 1% buffer
        use_limit_order = is_t2t_segment
        limit_price = close * 1.01 if use_limit_order else 0.0
        
        if use_limit_order:
            logger.info(f"Using LIMIT order for {broker_symbol} (T2T segment) @ ₹{limit_price:.2f}")
        
        # Try to resolve symbol using scrip master first
        resolved_symbol = None
        if self.scrip_master and self.scrip_master.symbol_map:
            # Try base symbol first
            instrument = self.scrip_master.get_instrument(broker_symbol)
            if instrument:
                resolved_symbol = instrument['symbol']
                logger.debug(f"Resolved {broker_symbol} -> {resolved_symbol} via scrip master")
        
        # If scrip master resolved the symbol, use it directly
        if resolved_symbol:
            place_symbol = resolved_symbol
            if use_limit_order:
                trial = self.orders.place_limit_buy(
                    symbol=place_symbol,
                    quantity=qty,
                    price=limit_price,
                    variety=config.DEFAULT_VARIETY,
                    exchange=config.DEFAULT_EXCHANGE,
                    product=config.DEFAULT_PRODUCT,
                )
            else:
                trial = self.orders.place_market_buy(
                    symbol=place_symbol,
                    quantity=qty,
                    variety=config.DEFAULT_VARIETY,
                    exchange=config.DEFAULT_EXCHANGE,
                    product=config.DEFAULT_PRODUCT,
                )
            # Check for successful response - Kotak Neo returns stat='Ok' with nOrdNo
            if isinstance(trial, dict) and 'error' not in trial:
                stat = trial.get('stat', '').lower()
                if stat == 'ok' or 'data' in trial or 'order' in trial or 'raw' in trial or 'nordno' in str(trial).lower():
                    resp = trial
                    placed_symbol = place_symbol
        
        # Fallback: Try common series suffixes if scrip master didn't work
        if not resp:
            series_suffixes = ["-EQ", "-BE", "-BL", "-BZ"]
            resp = None
            placed_symbol = None
            for suf in series_suffixes:
                place_symbol = broker_symbol if broker_symbol.endswith(suf) else f"{broker_symbol}{suf}"
                
                # Check if this suffix requires limit order
                is_t2t_suf = suf in ["-BE", "-BL", "-BZ"]
                
                if is_t2t_suf:
                    limit_price = close * 1.01
                    logger.debug(f"Trying {place_symbol} with LIMIT @ ₹{limit_price:.2f}")
                    trial = self.orders.place_limit_buy(
                        symbol=place_symbol,
                        quantity=qty,
                        price=limit_price,
                        variety=config.DEFAULT_VARIETY,
                        exchange=config.DEFAULT_EXCHANGE,
                        product=config.DEFAULT_PRODUCT,
                    )
                else:
                    trial = self.orders.place_market_buy(
                        symbol=place_symbol,
                        quantity=qty,
                        variety=config.DEFAULT_VARIETY,
                        exchange=config.DEFAULT_EXCHANGE,
                        product=config.DEFAULT_PRODUCT,
                    )
                # Check for successful response - Kotak Neo returns stat='Ok' with nOrdNo
                if isinstance(trial, dict) and 'error' not in trial:
                    stat = trial.get('stat', '').lower()
                    trial_str = str(trial).lower()
                    if (stat == 'ok' or 'data' in trial or 'order' in trial or 'raw' in trial or 'nordno' in trial_str) and 'not_ok' not in trial_str:
                        resp = trial
                        placed_symbol = place_symbol
                        break
        
        # Check if order was successful
        # Accept responses with nOrdNo (direct order ID) or data/order/raw structures
        resp_valid = isinstance(resp, dict) and ('data' in resp or 'order' in resp or 'raw' in resp or 'nOrdNo' in resp or 'nordno' in str(resp).lower()) and 'error' not in resp and 'not_ok' not in str(resp).lower()
        
        if not resp_valid:
            logger.error(f"Order placement failed for {broker_symbol}")
            return (False, None)
        
        # Extract order ID from response
        order_id = extract_order_id(resp)
        
        if not order_id:
            # Fallback: Search order book after 60 seconds
            logger.warning(
                f"No order ID in response for {broker_symbol}. "
                f"Will search order book after 60 seconds..."
            )
            order_id = search_order_in_broker_orderbook(
                self.orders,
                placed_symbol or broker_symbol,
                qty,
                placement_time,
                max_wait_seconds=60
            )
            
            if not order_id:
                # Still no order ID - uncertain placement
                logger.error(
                    f"Order placement uncertain for {broker_symbol}: "
                    f"No order ID and not found in order book"
                )
                # Send notification about uncertain order
                from core.telegram import send_telegram
                send_telegram(
                    f"⚠️ Order placement uncertain\n"
                    f"Symbol: {broker_symbol}\n"
                    f"Qty: {qty}\n"
                    f"Order ID not received and not found in order book.\n"
                    f"Please check broker app manually."
                )
                return (False, None)
        
        # Order successfully placed with order_id
        logger.info(
            f"Order placed successfully: {placed_symbol or broker_symbol} "
            f"(order_id: {order_id}, qty: {qty})"
        )
        
        # Get pre-existing quantity (if any)
        pre_existing_qty = 0
        try:
            holdings = self.portfolio.get_holdings() or {}
            for item in (holdings.get('data') or []):
                sym = str(item.get('tradingSymbol', '')).upper()
                if broker_symbol.upper() in sym:
                    pre_existing_qty = int(item.get('quantity', 0))
                    break
        except Exception as e:
            logger.debug(f"Could not get pre-existing qty: {e}")
        
        # Register in tracking scope (system-recommended)
        try:
            tracking_id = add_tracked_symbol(
                symbol=broker_symbol,
                ticker=ticker,
                initial_order_id=order_id,
                initial_qty=qty,
                pre_existing_qty=pre_existing_qty,
                recommendation_source=recommendation_source,
                recommendation_verdict=getattr(ind, 'verdict', None)
            )
            logger.debug(f"Added to tracking scope: {broker_symbol} (tracking_id: {tracking_id})")
        except Exception as e:
            logger.error(f"Failed to add to tracking scope: {e}")
        
        # Add to pending orders for status monitoring
        try:
            add_pending_order(
                order_id=order_id,
                symbol=placed_symbol or broker_symbol,
                ticker=ticker,
                qty=qty,
                order_type="MARKET",
                variety=config.DEFAULT_VARIETY
            )
            logger.debug(f"Added to pending orders: {order_id}")
        except Exception as e:
            logger.error(f"Failed to add to pending orders: {e}")
        
        return (True, order_id)

    # ---------------------- New entries ----------------------
    def place_new_entries(self, recommendations: List[Recommendation]) -> Dict[str, int]:
        summary = {
            "attempted": 0,
            "placed": 0,
            "retried": 0,
            "failed_balance": 0,
            "skipped_portfolio_limit": 0,
            "skipped_duplicates": 0,
            "skipped_missing_data": 0,
            "skipped_invalid_qty": 0,
        }
        if not self.orders or not self.portfolio:
            logger.error("Not logged in")
            return summary
        
        # Pre-flight check: Verify we can fetch holdings before proceeding
        # This prevents duplicate orders if holdings API is down
        test_holdings = self.portfolio.get_holdings()
        
        # Handle None response (API error)
        if test_holdings is None:
            logger.error("Cannot fetch holdings (API returned None) - aborting order placement to prevent duplicates")
            return summary
        
        # Check for 2FA gate
        if self._response_requires_2fa(test_holdings):
            logger.warning("Holdings API requires 2FA - attempting re-login...")
            if hasattr(self.auth, 'force_relogin') and self.auth.force_relogin():
                test_holdings = self.portfolio.get_holdings()
                if test_holdings is None:
                    logger.error("Holdings still unavailable after re-login - aborting order placement")
                    return summary
        
        # Verify holdings has 'data' field (successful response structure)
        if not isinstance(test_holdings, dict) or 'data' not in test_holdings:
            logger.error("Holdings API returned invalid response - aborting order placement to prevent duplicates")
            logger.error(f"Holdings response: {test_holdings}")
            return summary
        
        logger.info("Holdings API healthy - proceeding with order placement")
        
        # Clean up expired failed orders (past market open time)
        cleanup_expired_failed_orders(self.history_path)

        # Pre-step: If user bought manually (same day or prev day before open), update history and remove from failed queue
        try:
            detected = check_manual_buys_of_failed_orders(self.history_path, self.orders, include_previous_day_before_market=True)
            if detected:
                logger.info(f"Manual buys detected and recorded: {', '.join(detected)}")
        except Exception as e:
            logger.warning(f"Manual buy check failed: {e}")
        
        # STEP 1: Retry previously failed orders due to insufficient balance
        # (includes yesterday's orders if before 9:15 AM market open)
        failed_orders = get_failed_orders(self.history_path, include_previous_day_before_market=True)
        if failed_orders:
            logger.info(f"Found {len(failed_orders)} previously failed orders to retry")
            for failed_order in failed_orders[:]:
                # Check portfolio limit
                try:
                    current_count = len(self.current_symbols_in_portfolio())
                except Exception:
                    current_count = self.portfolio_size()
                if current_count >= config.MAX_PORTFOLIO_SIZE:
                    logger.info(f"Portfolio limit reached ({current_count}/{config.MAX_PORTFOLIO_SIZE}); skipping failed order retries")
                    break
                
                symbol = failed_order.get('symbol')
                ticker = failed_order.get('ticker')
                
                # Skip if already in holdings
                if self.has_holding(symbol):
                    logger.info(f"Removing {symbol} from retry queue: already in holdings")
                    remove_failed_order(self.history_path, symbol)
                    continue
                
                # Skip if already has active buy order
                if self.has_active_buy_order(symbol):
                    logger.info(f"Skipping retry for {symbol}: already has pending buy order")
                    continue
                
                summary["retried"] += 1
                logger.info(f"Retrying failed order for {symbol}...")
                
                # Get fresh indicators
                ind = self.get_daily_indicators(ticker)
                if not ind or any(k not in ind for k in ("close", "rsi10", "ema9", "ema200")):
                    logger.warning(f"Skipping retry {symbol}: missing indicators")
                    continue
                
                close = ind['close']
                if close <= 0:
                    logger.warning(f"Skipping retry {symbol}: invalid close price {close}")
                    continue
                
                qty = max(config.MIN_QTY, floor(config.CAPITAL_PER_TRADE / close))
                
                # Check position-to-volume ratio (liquidity filter)
                avg_vol = ind.get('avg_volume', 0)
                if not self.check_position_volume_ratio(qty, avg_vol, symbol, close):
                    logger.info(f"Skipping retry {symbol}: position size too large relative to volume")
                    summary["skipped_invalid_qty"] += 1
                    # Remove from failed orders queue since it's not a temporary issue
                    remove_failed_order(self.history_path, symbol)
                    continue
                
                # Check balance again
                affordable = self.get_affordable_qty(close)
                if affordable < config.MIN_QTY or qty > affordable:
                    avail_cash = self.get_available_cash()
                    required_cash = qty * close
                    shortfall = max(0.0, required_cash - (avail_cash or 0.0))
                    logger.warning(f"Retry failed for {symbol}: still insufficient balance (need ₹{required_cash:,.0f}, have ₹{(avail_cash or 0.0):,.0f})")
                    # Update the failed order with new attempt timestamp
                    failed_order['retry_count'] = failed_order.get('retry_count', 0) + 1
                    failed_order['last_retry_attempt'] = datetime.now().isoformat()
                    add_failed_order(self.history_path, failed_order)
                    continue
                
                # Try placing the order
                success, order_id = self._attempt_place_order(symbol, ticker, qty, close, ind)
                if success:
                    summary["placed"] += 1
                    remove_failed_order(self.history_path, symbol)
                    logger.info(f"Successfully placed retry order for {symbol} (order_id: {order_id})")
                else:
                    logger.warning(f"Retry order placement failed for {symbol}")
        
        # STEP 2: Process new recommendations
        for rec in recommendations:
            # Enforce hard portfolio cap before any balance checks
            try:
                current_count = len(self.current_symbols_in_portfolio())
            except Exception:
                current_count = self.portfolio_size()
            if current_count >= config.MAX_PORTFOLIO_SIZE:
                logger.info(f"Portfolio limit reached ({current_count}/{config.MAX_PORTFOLIO_SIZE}); skipping further entries")
                summary["skipped_portfolio_limit"] += 1
                break
            summary["attempted"] += 1
            broker_symbol = self.parse_symbol_for_broker(rec.ticker)
            # 1) Holding check
            if self.has_holding(broker_symbol):
                logger.info(f"Skipping {broker_symbol}: already in holdings")
                summary["skipped_duplicates"] += 1
                continue
            # 2) Active pending buy order check -> cancel and replace
            if self.has_active_buy_order(broker_symbol):
                variants = self._symbol_variants(broker_symbol)
                try:
                    cancelled = self.orders.cancel_pending_buys_for_symbol(variants)
                    logger.info(f"Cancelled {cancelled} pending BUY order(s) for {broker_symbol}")
                except Exception as e:
                    logger.warning(f"Could not cancel pending order(s) for {broker_symbol}: {e}")

            ind = self.get_daily_indicators(rec.ticker)
            if not ind or any(k not in ind for k in ("close", "rsi10", "ema9", "ema200")):
                logger.warning(f"Skipping {rec.ticker}: missing indicators")
                summary["skipped_missing_data"] += 1
                continue
            close = ind['close']
            if close <= 0:
                logger.warning(f"Skipping {rec.ticker}: invalid close price {close}")
                summary["skipped_invalid_qty"] += 1
                continue
            qty = max(config.MIN_QTY, floor(config.CAPITAL_PER_TRADE / close))
            
            # Check position-to-volume ratio (liquidity filter)
            avg_vol = ind.get('avg_volume', 0)
            if not self.check_position_volume_ratio(qty, avg_vol, broker_symbol, close):
                logger.info(f"Skipping {broker_symbol}: position size too large relative to volume")
                summary["skipped_invalid_qty"] += 1
                continue
            
            # Balance check (CNC needs cash) -> notify on insufficiency and save for retry
            affordable = self.get_affordable_qty(close)
            if affordable < config.MIN_QTY or qty > affordable:
                avail_cash = self.get_available_cash()
                required_cash = qty * close
                shortfall = max(0.0, required_cash - (avail_cash or 0.0))
                # Telegram message with emojis
                telegram_msg = (
                    f"⚠️ Insufficient balance for {broker_symbol} AMO BUY.\n"
                    f"Needed: ₹{required_cash:,.0f} for {qty} @ ₹{close:.2f}.\n"
                    f"Available: ₹{(avail_cash or 0.0):,.0f}. Shortfall: ₹{shortfall:,.0f}.\n\n"
                    f"🔁 Order saved for retry until 9:15 AM tomorrow (before market opens).\n"
                    f"Add balance & run script, or wait for 8 AM scheduled retry."
                )
                send_telegram(telegram_msg)
                
                # Logger message without emojis
                logger.warning(
                    f"Insufficient balance for {broker_symbol} AMO BUY. "
                    f"Needed: Rs.{required_cash:,.0f} for {qty} @ Rs.{close:.2f}. "
                    f"Available: Rs.{(avail_cash or 0.0):,.0f}. Shortfall: Rs.{shortfall:,.0f}. "
                    f"Order saved for retry until 9:15 AM tomorrow."
                )
                
                # Save failed order for retry
                failed_order_info = {
                    'symbol': broker_symbol,
                    'ticker': rec.ticker,
                    'close': close,
                    'qty': qty,
                    'required_cash': required_cash,
                    'shortfall': shortfall,
                    'reason': 'insufficient_balance',
                    'verdict': rec.verdict,
                    'rsi10': ind.get('rsi10'),
                    'ema9': ind.get('ema9'),
                    'ema200': ind.get('ema200'),
                }
                add_failed_order(self.history_path, failed_order_info)
                summary["failed_balance"] += 1
                summary["skipped_invalid_qty"] += 1
                continue

            # Try placing order (get recommendation source if available)
            rec_source = getattr(self, '_custom_csv_path', None) or 'system_recommendation'
            success, order_id = self._attempt_place_order(
                broker_symbol,
                rec.ticker,
                qty,
                close,
                ind,
                recommendation_source=rec_source
            )
            if success:
                summary["placed"] += 1
                logger.info(f"Order placed: {broker_symbol} (order_id: {order_id})")
            else:
                logger.error(f"Order placement failed for {broker_symbol}")
        return summary

    # ---------------------- Re-entry and exit ----------------------
    def evaluate_reentries_and_exits(self) -> Dict[str, int]:
        summary = {"symbols_evaluated": 0, "exits": 0, "reentries": 0}
        if not self.orders:
            logger.error("Not logged in")
            return summary
        data = load_history(self.history_path)
        trades = data.get('trades', [])
        # Group open trades by symbol
        from collections import defaultdict
        open_by_symbol: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for t in trades:
            if t.get('status') == 'open':
                open_by_symbol[t['symbol']].append(t)

        for symbol, entries in open_by_symbol.items():
            summary["symbols_evaluated"] += 1
            # Fix: Ensure symbol is valid before constructing ticker
            ticker = entries[0].get('ticker')
            if not ticker or ticker == '.NS':
                # Reconstruct ticker from symbol if missing or invalid
                if symbol and symbol.strip():
                    ticker = f"{symbol}.NS"
                else:
                    logger.warning(f"Skip invalid empty symbol in trade history")
                    continue
            ind = self.get_daily_indicators(ticker)
            if not ind:
                logger.warning(f"Skip {symbol}: missing indicators for re-entry/exit evaluation")
                continue
            rsi = ind['rsi10']
            price = ind['close']
            ema9 = ind['ema9']

            # Exit conditions
            if config.EXIT_ON_EMA9_OR_RSI50 and (price >= ema9 or rsi > 50):
                total_qty = sum(e.get('qty', 0) for e in entries)
                if total_qty > 0:
                    resp = self.orders.place_market_sell(
                        symbol=symbol,
                        quantity=total_qty,
                        variety=config.DEFAULT_VARIETY,
                        exchange=config.DEFAULT_EXCHANGE,
                        product=config.DEFAULT_PRODUCT,
                    )
                    
                    # Check if order was rejected due to insufficient quantity
                    order_rejected = False
                    if resp is None:
                        order_rejected = True
                    elif isinstance(resp, dict):
                        # Check for error indicators in response
                        keys_lower = {str(k).lower() for k in resp.keys()}
                        if any(k in keys_lower for k in ("error", "errors")):
                            error_msg = str(resp).lower()
                            # Check if error is related to insufficient quantity
                            if any(phrase in error_msg for phrase in ["insufficient", "quantity", "qty", "not enough", "exceed"]):
                                order_rejected = True
                                logger.warning(f"Sell order rejected for {symbol} (likely insufficient qty): {resp}")
                    
                    # Retry with actual available quantity from broker
                    if order_rejected:
                        logger.info(f"Retrying sell order for {symbol} with broker available quantity...")
                        try:
                            # Fetch holdings to get actual available quantity
                            holdings_response = self.portfolio.get_holdings()
                            if holdings_response and isinstance(holdings_response, dict) and 'data' in holdings_response:
                                holdings_data = holdings_response['data']
                                actual_qty = 0
                                
                                # Find the symbol in holdings
                                for holding in holdings_data:
                                    holding_symbol = (
                                        holding.get('tradingSymbol') or
                                        holding.get('symbol') or
                                        holding.get('instrumentName') or ''
                                    ).replace('-EQ', '').upper()
                                    
                                    if holding_symbol == symbol.upper():
                                        actual_qty = int(
                                            holding.get('quantity') or
                                            holding.get('qty') or
                                            holding.get('netQuantity') or
                                            holding.get('holdingsQuantity') or 0
                                        )
                                        break
                                
                                if actual_qty > 0:
                                    logger.info(f"Found {actual_qty} shares available in holdings for {symbol} (expected {total_qty})")
                                    # Retry sell with actual quantity
                                    resp = self.orders.place_market_sell(
                                        symbol=symbol,
                                        quantity=actual_qty,
                                        variety=config.DEFAULT_VARIETY,
                                        exchange=config.DEFAULT_EXCHANGE,
                                        product=config.DEFAULT_PRODUCT,
                                    )
                                    
                                    # Check if retry also failed
                                    retry_failed = False
                                    if resp is None:
                                        retry_failed = True
                                    elif isinstance(resp, dict):
                                        keys_lower = {str(k).lower() for k in resp.keys()}
                                        if any(k in keys_lower for k in ("error", "errors")):
                                            retry_failed = True
                                    
                                    if retry_failed:
                                        # Send Telegram notification for failed retry
                                        telegram_msg = (
                                            f"❌ *SELL ORDER RETRY FAILED*\n\n"
                                            f"📊 Symbol: *{symbol}*\n"
                                            f"💼 Expected Qty: {total_qty}\n"
                                            f"📦 Available Qty: {actual_qty}\n"
                                            f"📈 Price: ₹{price:.2f}\n"
                                            f"📉 RSI10: {rsi:.1f}\n"
                                            f"📍 EMA9: ₹{ema9:.2f}\n\n"
                                            f"⚠️ Both initial and retry sell orders failed.\n"
                                            f"🔧 Manual intervention may be required.\n\n"
                                            f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                        )
                                        send_telegram(telegram_msg)
                                        logger.error(f"Sell order retry FAILED for {symbol} - Telegram alert sent")
                                    else:
                                        logger.info(f"Retry sell order placed for {symbol}: {actual_qty} shares")
                                        # Update total_qty to reflect actual sold quantity
                                        total_qty = actual_qty
                                else:
                                    # Send Telegram notification when no holdings found
                                    telegram_msg = (
                                        f"❌ *SELL ORDER RETRY FAILED*\n\n"
                                        f"📊 Symbol: *{symbol}*\n"
                                        f"💼 Expected Qty: {total_qty}\n"
                                        f"📦 Available Qty: 0 (not found in holdings)\n"
                                        f"📈 Price: ₹{price:.2f}\n\n"
                                        f"⚠️ Cannot retry - symbol not found in holdings.\n"
                                        f"🔧 Manual check required.\n\n"
                                        f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                    )
                                    send_telegram(telegram_msg)
                                    logger.error(f"No holdings found for {symbol} - cannot retry sell order - Telegram alert sent")
                            else:
                                # Send Telegram notification when holdings fetch fails
                                telegram_msg = (
                                    f"❌ *SELL ORDER RETRY FAILED*\n\n"
                                    f"📊 Symbol: *{symbol}*\n"
                                    f"💼 Expected Qty: {total_qty}\n"
                                    f"📈 Price: ₹{price:.2f}\n\n"
                                    f"⚠️ Failed to fetch holdings from broker.\n"
                                    f"Cannot determine actual available quantity.\n"
                                    f"🔧 Manual intervention required.\n\n"
                                    f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                )
                                send_telegram(telegram_msg)
                                logger.error(f"Failed to fetch holdings for retry - cannot determine actual quantity for {symbol} - Telegram alert sent")
                        except Exception as e:
                            # Send Telegram notification for exception during retry
                            telegram_msg = (
                                f"❌ *SELL ORDER RETRY EXCEPTION*\n\n"
                                f"📊 Symbol: *{symbol}*\n"
                                f"💼 Expected Qty: {total_qty}\n"
                                f"📈 Price: ₹{price:.2f}\n\n"
                                f"⚠️ Error: {str(e)[:100]}\n"
                                f"🔧 Manual intervention required.\n\n"
                                f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            )
                            send_telegram(telegram_msg)
                            logger.error(f"Error during sell order retry for {symbol}: {e} - Telegram alert sent")
                    
                    # Mark all entries as closed
                    exit_time = datetime.now().isoformat()
                    for e in entries:
                        e['status'] = 'closed'
                        e['exit_price'] = price
                        e['exit_time'] = exit_time
                        e['exit_rsi10'] = rsi
                        e['exit_reason'] = 'EMA9 or RSI50'
                        e['sell_order_response'] = resp
                    logger.info(f"Exit {symbol}: qty={total_qty} at ref={price} RSI={rsi:.2f}")
                    summary["exits"] += 1
                    continue  # no re-entries if exited

            # Re-entry conditions
            # Determine next level available based on levels_taken and reset logic
            levels = entries[0].get('levels_taken', {"30": True, "20": False, "10": False})
            # Reset handling: if RSI>30, allow future cycles (but do not auto-clear past entries; apply for next re-entries)
            if rsi > 30:
                for e in entries:
                    e['reset_ready'] = True
            # If reset_ready and rsi drops below 30 again, trigger NEW CYCLE reentry at RSI<30
            if rsi < 30 and any(e.get('reset_ready') for e in entries):
                # This is a NEW CYCLE - treat RSI<30 as a fresh reentry opportunity
                for e in entries:
                    e['levels_taken'] = {"30": False, "20": False, "10": False}  # Reset all levels
                    e['reset_ready'] = False
                levels = entries[0]['levels_taken']
                # Immediately trigger reentry at this RSI<30 level
                next_level = 30
            else:
                # Normal progression through levels
                next_level = None
                if levels.get('30') and not levels.get('20') and rsi < 20:
                    next_level = 20
                if levels.get('20') and not levels.get('10') and rsi < 10:
                    next_level = 10

            if next_level is not None:
                # Daily cap: allow max 1 re-entry per symbol per day
                if self.reentries_today(symbol) >= 1:
                    logger.info(f"Re-entry daily cap reached for {symbol}; skipping today")
                    continue
                qty = max(config.MIN_QTY, floor(config.CAPITAL_PER_TRADE / price))
                # Balance check for re-entry
                affordable = self.get_affordable_qty(price)
                if affordable < 1:
                    logger.warning(f"Re-entry skip {symbol}: insufficient funds for 1 share at {price}")
                    continue
                if qty > affordable:
                    logger.info(f"Re-entry reducing qty from {qty} to {affordable} based on funds")
                    qty = affordable
                if qty > 0:
                    # Re-entry duplicate protection: holdings and active order
                    if self.has_holding(symbol) or self.has_active_buy_order(symbol):
                        logger.info(f"Re-entry skip {symbol}: already in holdings or pending order exists")
                        continue
                    place_symbol = symbol if symbol.endswith('-EQ') else f"{symbol}-EQ"
                    resp = self.orders.place_market_buy(
                        symbol=place_symbol,
                        quantity=qty,
                        variety=config.DEFAULT_VARIETY,
                        exchange=config.DEFAULT_EXCHANGE,
                        product=config.DEFAULT_PRODUCT,
                    )
                    # Record new averaging entry only if order succeeded
                    # Accept responses with nOrdNo (direct order ID) or data/order/raw structures
                    resp_valid = isinstance(resp, dict) and ('data' in resp or 'order' in resp or 'raw' in resp or 'nOrdNo' in resp or 'nordno' in str(resp).lower()) and 'error' not in resp and 'not_ok' not in str(resp).lower()
                    if resp_valid:
                        # Mark this level as taken
                        for e in entries:
                            e['levels_taken'][str(next_level)] = True
                        logger.info(f"Re-entry order placed for {symbol} at RSI<{next_level} level; will record once visible in holdings")
                        summary["reentries"] += 1
                        
                        # Update existing sell order with new total quantity
                        try:
                            logger.info(f"Checking for existing sell order to update after reentry for {symbol}...")
                            all_orders = self.orders.get_orders()
                            if all_orders and isinstance(all_orders, dict) and 'data' in all_orders:
                                for order in all_orders.get('data', []):
                                    order_symbol = (order.get('tradingSymbol') or '').split('-')[0].upper()
                                    order_type = (order.get('transactionType') or order.get('trnsTp') or '').upper()
                                    order_status = (order.get('status') or order.get('orderStatus') or order.get('ordSt') or '').lower()
                                    
                                    # Find active sell order for this symbol
                                    if order_symbol == symbol.upper() and order_type in ['S', 'SELL'] and order_status in ['open', 'pending']:
                                        old_order_id = order.get('neoOrdNo') or order.get('nOrdNo') or order.get('orderId')
                                        old_qty = int(order.get('quantity') or order.get('qty') or 0)
                                        old_price = float(order.get('price') or order.get('prc') or 0)
                                        
                                        if old_order_id and old_qty > 0:
                                            # Calculate new total quantity
                                            new_total_qty = old_qty + qty
                                            logger.info(f"Found existing sell order for {symbol}: {old_qty} shares @ ₹{old_price:.2f}")
                                            logger.info(f"Updating to new total: {old_qty} + {qty} (reentry) = {new_total_qty} shares")
                                            
                                            # Modify order with new quantity
                                            modify_resp = self.orders.modify_order(
                                                order_id=str(old_order_id),
                                                quantity=new_total_qty,
                                                price=old_price
                                            )
                                            
                                            if modify_resp:
                                                logger.info(f"✅ Sell order updated: {symbol} x{new_total_qty} @ ₹{old_price:.2f}")
                                            else:
                                                logger.warning(f"⚠️  Failed to modify sell order {old_order_id} - order may need manual update")
                                            break  # Only update the first matching sell order
                                else:
                                    logger.debug(f"No active sell order found for {symbol} (will be placed at next sell order run)")
                        except Exception as e:
                            logger.error(f"Error updating sell order after reentry: {e}")
                            # Continue execution even if sell order update fails
                        
                        # Update trade history with new total quantity
                        try:
                            logger.info(f"Updating trade history quantity after reentry for {symbol}...")
                            for e in entries:
                                old_qty = e.get('qty', 0)
                                new_total_qty = old_qty + qty
                                e['qty'] = new_total_qty
                                logger.info(f"Trade history updated: {symbol} qty {old_qty} → {new_total_qty}")
                                # Also add reentry metadata for tracking
                                if 'reentries' not in e:
                                    e['reentries'] = []
                                e['reentries'].append({
                                    'qty': qty,
                                    'level': next_level,
                                    'rsi': rsi,
                                    'price': price,
                                    'time': datetime.now().isoformat()
                                })
                        except Exception as e:
                            logger.error(f"Error updating trade history after reentry: {e}")
                    else:
                        logger.error(f"Re-entry order placement failed for {symbol}")

        # Save any in-memory modifications (exits/reset flags)
        save_history(self.history_path, data)
        return summary

    # ---------------------- Orchestrator ----------------------
    def run(self, keep_session: bool = True):
        # TEMPORARY: Skip weekend check for testing
        # if not self.is_trading_weekday():
        #     logger.info("Non-trading weekday; skipping auto trade run")
        #     return
        # if not self.market_was_open_today():
        #     logger.info("Detected market holiday/closed day; skipping run")
        #     return
        logger.warning("WARNING: Weekend check disabled for testing - this will attempt live trading!")
        if not self.login():
            logger.error("Login failed; aborting auto trade")
            return
        try:
            # Reconcile existing holdings into history (captures filled AMOs)
            self.reconcile_holdings_to_history()
            recs = self.load_latest_recommendations()
            new_summary = self.place_new_entries(recs)
            re_summary = self.evaluate_reentries_and_exits()
            # Reconcile again post-actions
            self.reconcile_holdings_to_history()
            logger.info(
                f"Run Summary: NewEntries placed={new_summary['placed']}/attempted={new_summary['attempted']}, "
                f"retried={new_summary.get('retried', 0)}, failed_balance={new_summary.get('failed_balance', 0)}, "
                f"skipped_dup={new_summary['skipped_duplicates']}, skipped_limit={new_summary['skipped_portfolio_limit']}; "
                f"Re/Exits: reentries={re_summary['reentries']}, exits={re_summary['exits']}, symbols={re_summary['symbols_evaluated']}"
            )
        finally:
            if not keep_session:
                self.logout()
            else:
                logger.info("Keeping session active (no logout)")
