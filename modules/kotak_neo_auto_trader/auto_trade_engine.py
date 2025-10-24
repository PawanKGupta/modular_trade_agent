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
from typing import List, Dict, Any, Optional

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

# Kotak Neo modules
try:
    from .trader import KotakNeoTrader
    from .orders import KotakNeoOrders
    from .portfolio import KotakNeoPortfolio
    from .auth import KotakNeoAuth
    from . import config
    from .storage import load_history, save_history, append_trade
except ImportError:
    from trader import KotakNeoTrader
    from orders import KotakNeoOrders
    from portfolio import KotakNeoPortfolio
    from auth import KotakNeoAuth
    import config
    from storage import load_history, save_history, append_trade


@dataclass
class Recommendation:
    ticker: str  # e.g. RELIANCE.NS
    verdict: str  # strong_buy|buy|watch
    last_close: float


class AutoTradeEngine:
    def __init__(self, env_file: str = "kotak_neo.env", auth: Optional[KotakNeoAuth] = None):
        self.env_file = env_file
        self.auth = auth if auth is not None else KotakNeoAuth(env_file)
        self.orders: Optional[KotakNeoOrders] = None
        self.portfolio: Optional[KotakNeoPortfolio] = None
        self.history_path = config.TRADES_HISTORY_PATH

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
            verdict_col = 'final_verdict'
            df_buy = df[df[verdict_col].astype(str).str.lower().isin(['buy','strong_buy'])]
            recs = []
            for _, row in df_buy.iterrows():
                ticker = str(row.get('ticker','')).strip().upper()
                last_close = float(row.get('last_close', 0) or 0)
                recs.append(Recommendation(ticker=ticker, verdict=row[verdict_col], last_close=last_close))
            logger.info(f"Loaded {len(recs)} BUY recommendations from {csv_path}")
            return recs
        # Otherwise, recompute post-scored verdicts to match Telegram without changing trade_agent
        try:
            # Re-analyze tickers quickly (no CSV export) then run backtest scoring
            tickers = [str(t).strip().upper() for t in df.get('ticker', []) if isinstance(t, str)]
            from core.analysis import analyze_ticker
            from core.backtest_scoring import add_backtest_scores_to_results
            analyzed = []
            for t in tickers:
                try:
                    res = analyze_ticker(t, enable_multi_timeframe=True, export_to_csv=False)
                    if res and res.get('status') == 'success':
                        # Ensure current strength score is computed (Telegram does this before post-scoring)
                        res['strength_score'] = compute_strength_score(res)
                    analyzed.append(res)
                except Exception as e:
                    logger.warning(f"Analyze failed for {t}: {e}")
            scored = add_backtest_scores_to_results(analyzed, years_back=2, dip_mode=False)
            # Apply same filter as Telegram (combined_score >= 25)
            buys = [r for r in scored if r.get('final_verdict') in ['buy','strong_buy'] and r.get('combined_score', 0) >= 25 and r.get('status') == 'success']
            recs = [Recommendation(ticker=r['ticker'].upper(), verdict=r['final_verdict'], last_close=float(r.get('last_close', 0) or 0)) for r in buys]
            logger.info(f"Re-scored {len(buys)} BUY recommendations from {csv_path} to align with Telegram")
            return recs
        except Exception as e:
            logger.error(f"Failed to recompute post-scored recommendations: {e}")
            # Fallback: use raw verdicts from CSV
            if 'verdict' in df.columns:
                df_buy = df[df['verdict'].astype(str).str.lower().isin(['buy','strong_buy'])]
                return [Recommendation(ticker=str(row['ticker']).strip().upper(), verdict=row['verdict'], last_close=float(row.get('last_close', 0) or 0)) for _, row in df_buy.iterrows()]
            return []

    def load_latest_recommendations(self) -> List[Recommendation]:
        # If a custom CSV path is set (from runner), use it
        if hasattr(self, '_custom_csv_path') and self._custom_csv_path:
            return self.load_latest_recommendations_from_csv(self._custom_csv_path)
        path = config.ANALYSIS_DIR
        # Prefer any CSV (post-scored or pre-scored)
        pattern = os.path.join(path, config.RECOMMENDED_CSV_GLOB)
        files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
        if not files:
            logger.warning(f"No recommendation CSV found at {pattern}")
            return []
        latest = files[0]
        return self.load_latest_recommendations_from_csv(latest)

    @staticmethod
    def get_daily_indicators(ticker: str) -> Optional[Dict[str, Any]]:
        try:
            df = fetch_ohlcv_yf(ticker, days=800, interval='1d', add_current_day=False)
            df = compute_indicators(df)
            if df is None or df.empty:
                return None
            last = df.iloc[-1]
            return {
                'close': float(last['close']),
                'rsi10': float(last['rsi10']),
                'ema9': float(df['close'].ewm(span=config.EMA_SHORT).mean().iloc[-1]) if 'ema9' not in df.columns else float(last.get('ema9', 0)),
                'ema200': float(last['ema200']) if 'ema200' in df.columns else float(df['close'].ewm(span=config.EMA_LONG).mean().iloc[-1])
            }
        except Exception as e:
            logger.warning(f"Failed to get indicators for {ticker}: {e}")
            return None

    def reconcile_holdings_to_history(self) -> None:
        """Add holdings not yet recorded in history (only once they appear in portfolio)."""
        try:
            if not self.portfolio:
                return
            hist = load_history(self.history_path)
            existing = {t.get('symbol') for t in hist.get('trades', []) if t.get('status') == 'open'}
            h = self.portfolio.get_holdings() or {}
            added = 0
            for item in (h.get('data') or []):
                sym = str(item.get('tradingSymbol') or '').upper().strip()
                if not sym or sym == 'N/A':
                    continue
                base = sym.split('-')[0].strip()
                if not base or not base.isalnum():
                    continue
                if base in (s.split('-')[0] for s in existing if s):
                    continue
                # Guess ticker and indicators
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
                    'entry_type': 'initial',
                }
                append_trade(self.history_path, trade)
                added += 1
            if added:
                logger.info(f"Reconciled {added} holding(s) into trade history")
        except Exception as e:
            logger.warning(f"Reconcile holdings failed: {e}")

    # ---------------------- Session ----------------------
    def login(self) -> bool:
        ok = self.auth.login()
        if ok:
            self.orders = KotakNeoOrders(self.auth)
            self.portfolio = KotakNeoPortfolio(self.auth)
        return ok

    def logout(self):
        self.auth.logout()

    # ---------------------- Portfolio helpers ----------------------
    def current_symbols_in_portfolio(self) -> List[str]:
        symbols = set()
        if not self.portfolio:
            return []
        holdings = self.portfolio.get_holdings() or {}
        for h in holdings.get('data', []) or []:
            sym = str(h.get('tradingSymbol') or '').upper()
            if sym:
                symbols.add(sym)
        # Include pending BUY orders too
        pend = self.orders.get_pending_orders() if self.orders else []
        for o in pend or []:
            if str(o.get('transactionType', '')).upper() == 'BUY':
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
        if isinstance(data, dict):
            avail = float(data.get('marginAvailable') or data.get('cash') or 0.0)
        try:
            from math import floor
            return max(0, floor(avail / float(price)))
        except Exception:
            return 0

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

    # ---------------------- New entries ----------------------
    def place_new_entries(self, recommendations: List[Recommendation]) -> Dict[str, int]:
        summary = {
            "attempted": 0,
            "placed": 0,
            "skipped_portfolio_limit": 0,
            "skipped_duplicates": 0,
            "skipped_missing_data": 0,
            "skipped_invalid_qty": 0,
        }
        if not self.orders or not self.portfolio:
            logger.error("Not logged in")
            return summary
        # No longer using history for duplicate skip; rely on live holdings and active orders
        for rec in recommendations:
            if self.portfolio_size() >= config.MAX_PORTFOLIO_SIZE:
                logger.info("Portfolio limit reached; skipping further entries")
                summary["skipped_portfolio_limit"] += 1
                break
            summary["attempted"] += 1
            broker_symbol = self.parse_symbol_for_broker(rec.ticker)
            # 1) Holding check
            if self.has_holding(broker_symbol):
                logger.info(f"Skipping {broker_symbol}: already in holdings")
                summary["skipped_duplicates"] += 1
                continue
            # 2) Active pending buy order check
            if self.has_active_buy_order(broker_symbol):
                logger.info(f"Skipping {broker_symbol}: active pending BUY order exists")
                summary["skipped_duplicates"] += 1
                continue

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
            # Balance check (CNC needs cash)
            affordable = self.get_affordable_qty(close)
            if affordable < 1:
                logger.warning(f"Skipping {rec.ticker}: insufficient funds for 1 share at {close}")
                summary["skipped_invalid_qty"] += 1
                continue
            if qty > affordable:
                logger.info(f"Reducing qty from {qty} to affordable {affordable} based on available funds")
                qty = affordable

            # Try common series suffixes for NSE cash (order of likelihood)
            # Try common series suffixes for NSE cash (order of likelihood)
            series_suffixes = ["-EQ", "-BE", "-BL", "-BZ"]
            resp = None
            placed_symbol = None
            for suf in series_suffixes:
                place_symbol = broker_symbol if broker_symbol.endswith(suf) else f"{broker_symbol}{suf}"
                trial = self.orders.place_market_buy(
                    symbol=place_symbol,
                    quantity=qty,
                    variety=config.DEFAULT_VARIETY,
                    exchange=config.DEFAULT_EXCHANGE,
                    product=config.DEFAULT_PRODUCT,
                )
                if isinstance(trial, dict) and ('data' in trial or 'order' in trial or 'raw' in trial) and 'error' not in trial and 'Not_Ok'.lower() not in str(trial).lower():
                    resp = trial
                    placed_symbol = place_symbol
                    break
            # Only persist successful orders to history
            resp_valid = isinstance(resp, dict) and ('data' in resp or 'order' in resp or 'raw' in resp) and 'error' not in resp and 'not_ok' not in str(resp).lower()
            if resp_valid:
                summary["placed"] += 1
                logger.info(f"Order placed for {placed_symbol or broker_symbol}; will record once visible in holdings")
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
            ticker = entries[0].get('ticker', f"{symbol}.NS")
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
            # If reset_ready and rsi drops below 30 again, we can re-enable levels for new cycle
            if rsi < 30 and any(e.get('reset_ready') for e in entries):
                for e in entries:
                    e['levels_taken'] = {"30": True, "20": False, "10": False}
                    e['reset_ready'] = False
                levels = entries[0]['levels_taken']

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
                    resp_valid = isinstance(resp, dict) and ('data' in resp or 'order' in resp or 'raw' in resp) and 'error' not in resp and 'not_ok' not in str(resp).lower()
                    if resp_valid:
                        # Do not record immediately; wait for holdings
                        logger.info(f"Re-entry order placed for {symbol}; will record once visible in holdings")
                        summary["reentries"] += 1
                    else:
                        logger.error(f"Re-entry order placement failed for {symbol}")

        # Save any in-memory modifications (exits/reset flags)
        save_history(self.history_path, data)
        return summary

    # ---------------------- Orchestrator ----------------------
    def run(self):
        if not self.is_trading_weekday():
            logger.info("Non-trading weekday; skipping auto trade run")
            return
        if not self.market_was_open_today():
            logger.info("Detected market holiday/closed day; skipping run")
            return
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
                f"skipped_dup={new_summary['skipped_duplicates']}, skipped_limit={new_summary['skipped_portfolio_limit']}; "
                f"Re/Exits: reentries={re_summary['reentries']}, exits={re_summary['exits']}, symbols={re_summary['symbols_evaluated']}"
            )
        finally:
            self.logout()
