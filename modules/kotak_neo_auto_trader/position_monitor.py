#!/usr/bin/env python3
"""
Live Position Monitor
Monitors open positions during market hours and sends alerts
"""

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.live_price_manager import get_live_price_manager  # noqa: E402
from modules.kotak_neo_auto_trader.services import (  # noqa: E402
    get_indicator_service,
    get_position_loader,
    get_price_service,
)
from modules.kotak_neo_auto_trader.telegram_notifier import get_telegram_notifier  # noqa: E402
from utils.logger import logger  # noqa: E402

# Constants
RSI_EXIT_THRESHOLD = 50.0
RSI_AVERAGING_LEVEL_20 = 20.0
RSI_AVERAGING_LEVEL_10 = 10.0


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
    alerts: list[str]


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
        enable_realtime_prices: bool = True,
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

        # Live price manager (for real-time LTP) - kept for backward compatibility
        if enable_realtime_prices:
            self.price_manager = live_price_manager or get_live_price_manager(
                enable_websocket=True, enable_yfinance_fallback=True
            )
        else:
            self.price_manager = None

        # Initialize unified services
        self.price_service = get_price_service(
            live_price_manager=self.price_manager, enable_caching=True
        )
        self.indicator_service = get_indicator_service(
            price_service=self.price_service, enable_caching=True
        )
        # Initialize PositionLoader (Phase 2.2: Portfolio & Position Services)
        self.position_loader = get_position_loader(
            history_path=self.history_path, enable_caching=True
        )

        # Alert thresholds
        self.large_move_threshold = 3.0  # 3% price move
        self.exit_proximity_threshold = 2.0  # Within 2% of EMA9
        self.rsi_exit_warning = 45.0  # Alert when RSI > 45 (near 50)

    def monitor_all_positions(self) -> dict[str, Any]:
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

        # Get open positions using PositionLoader (Phase 2.2)
        open_positions = self.position_loader.get_positions_by_symbol()

        if not open_positions:
            logger.info("No open positions to monitor")
            return {
                "monitored": 0,
                "alerts_sent": 0,
                "exit_imminent": 0,
                "averaging_opportunities": 0,
            }

        logger.info(f"Monitoring {len(open_positions)} position(s)")
        logger.info("")

        # Subscribe to live prices for all open positions
        symbols = list(open_positions.keys())
        if symbols:
            # Phase 4.1: Use PriceService for centralized subscription with deduplication
            try:
                subscribed = self.price_service.subscribe_to_symbols(
                    symbols, service_id="position_monitor"
                )
                if subscribed:
                    logger.info(
                        f"[OK] Subscribed to live prices for {len(symbols)} positions "
                        f"(via PriceService - deduplication enabled)"
                    )
                elif self.price_manager:
                    # Fallback to direct price_manager subscription
                    try:
                        self.price_manager.subscribe_to_positions(symbols)
                        logger.info(f"[OK] Subscribed to live prices for {len(symbols)} positions")
                    except Exception as e:
                        logger.warning(f"Live price subscription failed: {e}")
            except Exception as e:
                logger.warning(f"Live price subscription failed: {e}")

        results = {
            "monitored": 0,
            "alerts_sent": 0,
            "exit_imminent": 0,
            "averaging_opportunities": 0,
            "positions": [],
        }

        # Monitor each position
        for symbol, entries in open_positions.items():
            try:
                status = self._check_position_status(symbol, entries)

                if status:
                    results["positions"].append(status)
                    results["monitored"] += 1

                    # Count alerts
                    if status.exit_imminent:
                        results["exit_imminent"] += 1

                    if status.averaging_opportunity:
                        results["averaging_opportunities"] += 1

                    # Log status
                    self._log_position_status(status)

                    # Send alerts if needed
                    if status.alerts and self.enable_alerts:
                        self._send_position_alerts(status)
                        results["alerts_sent"] += 1

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

    def _get_open_positions(self, history: dict) -> dict[str, list[dict]]:
        """
        Get all open positions grouped by symbol.

        DEPRECATED: Use position_loader.get_positions_by_symbol() instead.
        This method is kept for backward compatibility and delegates to PositionLoader.
        """
        return self.position_loader.get_positions_by_symbol()

    def _check_position_status(self, symbol: str, entries: list[dict]) -> PositionStatus | None:
        """Check status of a position and generate alerts."""

        # Get ticker
        ticker = entries[0].get("ticker")
        if not ticker or ticker == ".NS":
            ticker = f"{symbol}.NS"

        # Get current market data using unified services
        try:
            # Use PriceService for historical data
            df = self.price_service.get_price(ticker, days=200, interval="1d", add_current_day=True)
            if df is None or df.empty:
                logger.warning(f"No data for {symbol}")
                return None

            # Use IndicatorService for indicator calculations
            df = self.indicator_service.calculate_all_indicators(df)
            if df is None or df.empty:
                logger.warning(f"Failed to calculate indicators for {symbol}")
                return None

            latest = df.iloc[-1]

            # Use PriceService for real-time LTP
            current_price = self.price_service.get_realtime_price(
                symbol=symbol, ticker=ticker, broker_symbol=None
            )

            # Fallback to close price if real-time price unavailable
            if current_price is None:
                current_price = float(latest["close"])
                logger.debug(
                    f"Could not get real-time LTP for {symbol}, "
                    f"using close price: Rs {current_price}"
                )
            else:
                logger.debug(f"Using real-time LTP for {symbol}: Rs {current_price}")

            # Get RSI10 from calculated indicators
            rsi10 = float(latest.get("rsi10", 0))

            # Calculate EMA9 with real-time LTP using IndicatorService
            # This matches the exact logic from the original implementation
            if self.enable_realtime_prices and current_price != float(latest["close"]):
                # Use real-time EMA9 calculation when real-time price differs from close
                ema9 = self.indicator_service.calculate_ema9_realtime(
                    ticker=ticker, broker_symbol=None, current_ltp=current_price
                )
                if ema9 is None:
                    # Fallback to historical EMA9 if real-time calculation fails
                    ema9 = float(latest.get("ema9", 0))
            else:
                # Use historical EMA9 from indicators
                ema9 = float(latest.get("ema9", 0))

            ema200 = float(latest.get("ema200", 0))

        except Exception as e:
            logger.error(f"Failed to get data for {symbol}: {e}")
            return None

        # Calculate position metrics
        total_qty = sum(e.get("qty", 0) for e in entries)
        total_cost = sum(e.get("entry_price", 0) * e.get("qty", 0) for e in entries)
        avg_entry_price = total_cost / total_qty if total_qty > 0 else 0

        current_value = current_price * total_qty
        unrealized_pnl = current_value - total_cost
        unrealized_pnl_pct = (unrealized_pnl / total_cost * 100) if total_cost > 0 else 0

        # Calculate distance to EMA9
        distance_to_ema9_pct = ((current_price - ema9) / ema9 * 100) if ema9 > 0 else 0

        # Calculate days held
        entry_time_str = entries[0].get("entry_time", "")
        try:
            entry_time = datetime.fromisoformat(entry_time_str)
            days_held = (datetime.now() - entry_time).days
        except (ValueError, TypeError):
            days_held = 0

        # Generate alerts
        alerts = []
        alert_level = "info"
        exit_imminent = False
        averaging_opportunity = False

        # Check exit conditions
        if current_price >= ema9:
            alerts.append(f"EXIT: Price (Rs {current_price:.2f}) >= EMA9 (Rs {ema9:.2f})")
            exit_imminent = True
            alert_level = "critical"
        elif distance_to_ema9_pct > 0 and distance_to_ema9_pct < self.exit_proximity_threshold:
            alerts.append(f"EXIT APPROACHING: Price {distance_to_ema9_pct:.1f}% below EMA9")
            exit_imminent = True
            alert_level = "warning"

        if rsi10 > RSI_EXIT_THRESHOLD:
            alerts.append(f"EXIT: RSI10 ({rsi10:.1f}) > {RSI_EXIT_THRESHOLD}")
            exit_imminent = True
            alert_level = "critical"
        elif rsi10 > self.rsi_exit_warning:
            alerts.append(f"EXIT APPROACHING: RSI10 ({rsi10:.1f}) near {RSI_EXIT_THRESHOLD}")
            exit_imminent = True
            alert_level = "warning"

        # Check averaging opportunities
        levels = entries[0].get("levels_taken", {"30": True, "20": False, "10": False})

        if rsi10 < RSI_AVERAGING_LEVEL_20 and levels.get("30") and not levels.get("20"):
            alerts.append(f"AVERAGING OPPORTUNITY: RSI10 ({rsi10:.1f}) < {RSI_AVERAGING_LEVEL_20}")
            averaging_opportunity = True
            if alert_level == "info":
                alert_level = "warning"

        if rsi10 < RSI_AVERAGING_LEVEL_10 and levels.get("20") and not levels.get("10"):
            alerts.append(f"AVERAGING OPPORTUNITY: RSI10 ({rsi10:.1f}) < {RSI_AVERAGING_LEVEL_10}")
            averaging_opportunity = True
            if alert_level == "info":
                alert_level = "warning"

        # Check large price movements
        if abs(unrealized_pnl_pct) > self.large_move_threshold:
            direction = "GAIN" if unrealized_pnl_pct > 0 else "LOSS"
            alerts.append(
                f"{direction}: {abs(unrealized_pnl_pct):.1f}% (Rs {abs(unrealized_pnl):,.0f})"
            )
            if alert_level == "info":
                alert_level = "warning"

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
            alerts=alerts,
        )

        return status

    def _log_position_status(self, status: PositionStatus) -> None:
        """Log position status to console."""
        logger.info(f"Position: {status.symbol}")
        logger.info(f"  Price: Rs {status.current_price:.2f} (Entry: Rs {status.entry_price:.2f})")
        logger.info(f"  Quantity: {status.quantity}")
        logger.info(f"  P&L: Rs {status.unrealized_pnl:,.0f} ({status.unrealized_pnl_pct:+.2f}%)")
        logger.info(f"  RSI10: {status.rsi10:.1f}")
        logger.info(f"  EMA9: Rs {status.ema9:.2f} (Distance: {status.distance_to_ema9_pct:+.1f}%)")
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

        # Determine emoji and severity based on alert level
        emoji_map = {"info": "", "warning": "", "critical": ""}
        severity_map = {"info": "INFO", "warning": "WARNING", "critical": "ERROR"}
        emoji = emoji_map.get(status.alert_level, "")
        severity = severity_map.get(status.alert_level, "INFO")

        # Build message
        message_lines = [
            f"{emoji} *Position Alert*",
            "",
            f"Symbol: *{status.symbol}*",
            f"Current: Rs {status.current_price:.2f}",
            f"Quantity: {status.quantity}",
            f"P&L: Rs {status.unrealized_pnl:,.0f} ({status.unrealized_pnl_pct:+.2f}%)",
            "",
            f"RSI10: {status.rsi10:.1f}",
            f"EMA9: Rs {status.ema9:.2f}",
            f"? Distance to EMA9: {status.distance_to_ema9_pct:+.1f}%",
            "",
            "*Alerts:*",
        ]

        for alert in status.alerts:
            message_lines.append(f"  - {alert}")

        message_text = "\n".join(message_lines)

        try:
            # Use notify_system_alert for consistent formatting and context
            self.telegram.notify_system_alert(
                alert_type="POSITION_ALERT",
                message_text=message_text,
                severity=severity,
                user_id=None,  # Position monitor doesn't have user context
            )
            logger.info(f"  [OK] Telegram alert sent for {status.symbol}")
        except Exception as e:
            logger.error(f"  [FAIL] Failed to send Telegram alert: {e}")


def get_position_monitor(
    history_path: str = "data/trades_history.json",
    enable_alerts: bool = True,
    enable_realtime_prices: bool = True,
    live_price_manager=None,
) -> PositionMonitor:
    """
    Factory function to get position monitor instance.

    Args:
        history_path: Path to trades history
        enable_alerts: Enable Telegram alerts
        enable_realtime_prices: Use real-time prices from WebSocket
        live_price_manager: Optional shared LivePriceCache/LivePriceManager instance
                           to avoid duplicate auth sessions (backward compatible)

    Returns:
        PositionMonitor instance
    """
    telegram = get_telegram_notifier() if enable_alerts else None
    return PositionMonitor(
        history_path=history_path,
        telegram_notifier=telegram,
        enable_alerts=enable_alerts,
        live_price_manager=live_price_manager,  # Pass through if provided
        enable_realtime_prices=enable_realtime_prices,
    )
