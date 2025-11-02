#!/usr/bin/env python3
"""
Live Position Monitor
Monitors open positions during market hours and sends alerts
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger
from modules.kotak_neo_auto_trader.storage import load_history
from modules.kotak_neo_auto_trader.tracking_scope import get_tracked_symbols, get_tracking_entry
from modules.kotak_neo_auto_trader.telegram_notifier import get_telegram_notifier
from modules.kotak_neo_auto_trader.live_price_manager import get_live_price_manager
from core.data_fetcher import fetch_ohlcv_yf
from core.indicators import compute_indicators


@dataclass
class PositionStatus:
    """Status of a monitored position"""
    symbol: str
    ticker: str
    current_price: float
    entry_price: float
    quantity: int
    unrealized_pnl: float
    unrealized_pnl_pct: float
    rsi10: float
    ema9: float
    ema200: float
    distance_to_ema9_pct: float
    days_held: int
    exit_imminent: bool
    averaging_opportunity: bool
    alert_level: str  # 'info', 'warning', 'critical'
    alerts: List[str]


class PositionMonitor:
    """
    Monitors live positions during market hours.
    
    Features:
    - Checks position health hourly
    - Monitors exit condition proximity
    - Detects averaging opportunities
    - Sends Telegram alerts
    - Tracks unrealized P&L
    """
    
    def __init__(
        self,
        history_path: str = "data/trades_history.json",
        telegram_notifier=None,
        enable_alerts: bool = True,
        live_price_manager=None,
        enable_realtime_prices: bool = True
    ):
        """
        Initialize position monitor.
        
        Args:
            history_path: Path to trades history JSON
            telegram_notifier: TelegramNotifier instance
            enable_alerts: Enable Telegram alerts
            live_price_manager: LivePriceManager instance (optional)
            enable_realtime_prices: Use real-time prices from WebSocket
        """
        self.history_path = history_path
        self.telegram = telegram_notifier or get_telegram_notifier()
        self.enable_alerts = enable_alerts
        self.enable_realtime_prices = enable_realtime_prices
        
        # Live price manager (for real-time LTP)
        if enable_realtime_prices:
            self.price_manager = live_price_manager or get_live_price_manager(
                enable_websocket=True,
                enable_yfinance_fallback=True
            )
        else:
            self.price_manager = None
        
        # Alert thresholds
        self.large_move_threshold = 3.0  # 3% price move
        self.exit_proximity_threshold = 2.0  # Within 2% of EMA9
        self.rsi_exit_warning = 45.0  # Alert when RSI > 45 (near 50)
    
    def monitor_all_positions(self) -> Dict[str, Any]:
        """
        Monitor all open positions and send alerts.
        
        Returns:
            Dict with monitoring results
        """
        logger.info("=" * 70)
        logger.info("LIVE POSITION MONITORING")
        logger.info("=" * 70)
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("")
        
        # Get open positions from history
        history = load_history(self.history_path)
        open_positions = self._get_open_positions(history)
        
        if not open_positions:
            logger.info("No open positions to monitor")
            return {
                'monitored': 0,
                'alerts_sent': 0,
                'exit_imminent': 0,
                'averaging_opportunities': 0
            }
        
        logger.info(f"Monitoring {len(open_positions)} position(s)")
        logger.info("")
        
        # Subscribe to live prices for all open positions
        if self.price_manager:
            symbols = list(open_positions.keys())
            try:
                self.price_manager.subscribe_to_positions(symbols)
                logger.info(f"✓ Subscribed to live prices for {len(symbols)} positions")
            except Exception as e:
                logger.warning(f"Live price subscription failed: {e}")
        
        results = {
            'monitored': 0,
            'alerts_sent': 0,
            'exit_imminent': 0,
            'averaging_opportunities': 0,
            'positions': []
        }
        
        # Monitor each position
        for symbol, entries in open_positions.items():
            try:
                status = self._check_position_status(symbol, entries)
                
                if status:
                    results['positions'].append(status)
                    results['monitored'] += 1
                    
                    # Count alerts
                    if status.exit_imminent:
                        results['exit_imminent'] += 1
                    
                    if status.averaging_opportunity:
                        results['averaging_opportunities'] += 1
                    
                    # Log status
                    self._log_position_status(status)
                    
                    # Send alerts if needed
                    if status.alerts and self.enable_alerts:
                        self._send_position_alerts(status)
                        results['alerts_sent'] += 1
                
            except Exception as e:
                logger.error(f"Error monitoring {symbol}: {e}")
        
        # Summary
        logger.info("")
        logger.info("=" * 70)
        logger.info("MONITORING SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Positions Monitored: {results['monitored']}")
        logger.info(f"Exit Imminent: {results['exit_imminent']}")
        logger.info(f"Averaging Opportunities: {results['averaging_opportunities']}")
        logger.info(f"Alerts Sent: {results['alerts_sent']}")
        logger.info("=" * 70)
        
        return results
    
    def _get_open_positions(self, history: Dict) -> Dict[str, List[Dict]]:
        """Get all open positions grouped by symbol."""
        from collections import defaultdict
        
        open_positions = defaultdict(list)
        trades = history.get('trades', [])
        
        for trade in trades:
            if trade.get('status') == 'open':
                symbol = trade.get('symbol')
                if symbol:
                    open_positions[symbol].append(trade)
        
        return dict(open_positions)
    
    def _check_position_status(
        self,
        symbol: str,
        entries: List[Dict]
    ) -> Optional[PositionStatus]:
        """Check status of a position and generate alerts."""
        
        # Get ticker
        ticker = entries[0].get('ticker')
        if not ticker or ticker == '.NS':
            ticker = f"{symbol}.NS"
        
        # Get current market data
        try:
            df = fetch_ohlcv_yf(ticker, days=200, interval='1d', add_current_day=True)
            if df is None or df.empty:
                logger.warning(f"No data for {symbol}")
                return None
            
            df = compute_indicators(df)
            latest = df.iloc[-1]
            
            # Use real-time LTP if available, else fall back to close price
            if self.price_manager:
                current_price = self.price_manager.get_ltp(symbol, ticker)
                if current_price is None:
                    logger.warning(f"Could not get real-time LTP for {symbol}, using close price")
                    current_price = float(latest['close'])
                else:
                    logger.debug(f"Using real-time LTP for {symbol}: ₹{current_price}")
            else:
                current_price = float(latest['close'])
            
            rsi10 = float(latest['rsi10'])
            
            # Calculate EMA9 with real-time LTP
            # Append current_price to the series and recalculate EMA9
            close_series = df['close'].copy()
            if self.price_manager and current_price != float(latest['close']):
                # Add real-time price as latest data point
                import pandas as pd
                close_series = pd.concat([close_series, pd.Series([current_price])])
            
            ema9 = float(close_series.ewm(span=9).mean().iloc[-1])
            ema200 = float(latest.get('ema200', 0))
            
        except Exception as e:
            logger.error(f"Failed to get data for {symbol}: {e}")
            return None
        
        # Calculate position metrics
        total_qty = sum(e.get('qty', 0) for e in entries)
        total_cost = sum(e.get('entry_price', 0) * e.get('qty', 0) for e in entries)
        avg_entry_price = total_cost / total_qty if total_qty > 0 else 0
        
        current_value = current_price * total_qty
        unrealized_pnl = current_value - total_cost
        unrealized_pnl_pct = (unrealized_pnl / total_cost * 100) if total_cost > 0 else 0
        
        # Calculate distance to EMA9
        distance_to_ema9_pct = ((current_price - ema9) / ema9 * 100) if ema9 > 0 else 0
        
        # Calculate days held
        entry_time_str = entries[0].get('entry_time', '')
        try:
            entry_time = datetime.fromisoformat(entry_time_str)
            days_held = (datetime.now() - entry_time).days
        except:
            days_held = 0
        
        # Generate alerts
        alerts = []
        alert_level = 'info'
        exit_imminent = False
        averaging_opportunity = False
        
        # Check exit conditions
        if current_price >= ema9:
            alerts.append(f"🎯 EXIT: Price (₹{current_price:.2f}) >= EMA9 (₹{ema9:.2f})")
            exit_imminent = True
            alert_level = 'critical'
        elif distance_to_ema9_pct > 0 and distance_to_ema9_pct < self.exit_proximity_threshold:
            alerts.append(f"⚠️ EXIT APPROACHING: Price {distance_to_ema9_pct:.1f}% below EMA9")
            exit_imminent = True
            alert_level = 'warning'
        
        if rsi10 > 50:
            alerts.append(f"🎯 EXIT: RSI10 ({rsi10:.1f}) > 50")
            exit_imminent = True
            alert_level = 'critical'
        elif rsi10 > self.rsi_exit_warning:
            alerts.append(f"⚠️ EXIT APPROACHING: RSI10 ({rsi10:.1f}) near 50")
            exit_imminent = True
            alert_level = 'warning'
        
        # Check averaging opportunities
        levels = entries[0].get('levels_taken', {"30": True, "20": False, "10": False})
        
        if rsi10 < 20 and levels.get('30') and not levels.get('20'):
            alerts.append(f"🔄 AVERAGING OPPORTUNITY: RSI10 ({rsi10:.1f}) < 20")
            averaging_opportunity = True
            if alert_level == 'info':
                alert_level = 'warning'
        
        if rsi10 < 10 and levels.get('20') and not levels.get('10'):
            alerts.append(f"🔄 AVERAGING OPPORTUNITY: RSI10 ({rsi10:.1f}) < 10")
            averaging_opportunity = True
            if alert_level == 'info':
                alert_level = 'warning'
        
        # Check large price movements
        if abs(unrealized_pnl_pct) > self.large_move_threshold:
            direction = "📈 GAIN" if unrealized_pnl_pct > 0 else "📉 LOSS"
            alerts.append(
                f"{direction}: {abs(unrealized_pnl_pct):.1f}% "
                f"(₹{abs(unrealized_pnl):,.0f})"
            )
            if alert_level == 'info':
                alert_level = 'warning'
        
        # Create status
        status = PositionStatus(
            symbol=symbol,
            ticker=ticker,
            current_price=current_price,
            entry_price=avg_entry_price,
            quantity=total_qty,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
            rsi10=rsi10,
            ema9=ema9,
            ema200=ema200,
            distance_to_ema9_pct=distance_to_ema9_pct,
            days_held=days_held,
            exit_imminent=exit_imminent,
            averaging_opportunity=averaging_opportunity,
            alert_level=alert_level,
            alerts=alerts
        )
        
        return status
    
    def _log_position_status(self, status: PositionStatus) -> None:
        """Log position status to console."""
        logger.info(f"Position: {status.symbol}")
        logger.info(f"  Price: ₹{status.current_price:.2f} (Entry: ₹{status.entry_price:.2f})")
        logger.info(f"  Quantity: {status.quantity}")
        logger.info(f"  P&L: ₹{status.unrealized_pnl:,.0f} ({status.unrealized_pnl_pct:+.2f}%)")
        logger.info(f"  RSI10: {status.rsi10:.1f}")
        logger.info(f"  EMA9: ₹{status.ema9:.2f} (Distance: {status.distance_to_ema9_pct:+.1f}%)")
        logger.info(f"  Days Held: {status.days_held}")
        
        if status.alerts:
            logger.info(f"  Alerts ({status.alert_level.upper()}):")
            for alert in status.alerts:
                logger.info(f"    {alert}")
        
        logger.info("")
    
    def _send_position_alerts(self, status: PositionStatus) -> None:
        """Send Telegram alerts for position."""
        if not self.telegram or not self.telegram.enabled:
            return
        
        # Determine emoji based on alert level
        emoji = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'critical': '🚨'
        }.get(status.alert_level, 'ℹ️')
        
        # Build message
        message_lines = [
            f"{emoji} *POSITION ALERT*",
            "",
            f"📊 Symbol: *{status.symbol}*",
            f"💰 Current: ₹{status.current_price:.2f}",
            f"📦 Quantity: {status.quantity}",
            f"💵 P&L: ₹{status.unrealized_pnl:,.0f} ({status.unrealized_pnl_pct:+.2f}%)",
            "",
            f"📈 RSI10: {status.rsi10:.1f}",
            f"📉 EMA9: ₹{status.ema9:.2f}",
            f"📍 Distance to EMA9: {status.distance_to_ema9_pct:+.1f}%",
            "",
            "*Alerts:*"
        ]
        
        for alert in status.alerts:
            message_lines.append(f"  • {alert}")
        
        message_lines.append("")
        message_lines.append(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        message = "\n".join(message_lines)
        
        try:
            self.telegram.send_message(message)
            logger.info(f"  ✓ Telegram alert sent for {status.symbol}")
        except Exception as e:
            logger.error(f"  ✗ Failed to send Telegram alert: {e}")


def get_position_monitor(
    history_path: str = "data/trades_history.json",
    enable_alerts: bool = True,
    enable_realtime_prices: bool = True
) -> PositionMonitor:
    """
    Factory function to get position monitor instance.
    
    Args:
        history_path: Path to trades history
        enable_alerts: Enable Telegram alerts
        enable_realtime_prices: Use real-time prices from WebSocket
    
    Returns:
        PositionMonitor instance
    """
    telegram = get_telegram_notifier() if enable_alerts else None
    return PositionMonitor(
        history_path=history_path,
        telegram_notifier=telegram,
        enable_alerts=enable_alerts,
        enable_realtime_prices=enable_realtime_prices
    )
