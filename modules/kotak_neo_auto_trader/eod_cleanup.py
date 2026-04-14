#!/usr/bin/env python3
"""
End-of-Day (EOD) Cleanup Module
Performs end-of-day reconciliation, cleanup, and summary generation.

SOLID Principles:
- Single Responsibility: Only handles EOD operations
- Open/Closed: Extensible for different cleanup strategies
- Dependency Inversion: Abstract module dependencies

Phase 2 Feature: End-of-day cleanup and summary
"""

# Use existing project logger
import sys
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

from .manual_order_matcher import ManualOrderMatcher, get_manual_order_matcher
from .order_status_verifier import OrderStatusVerifier
from .order_tracker import OrderTracker, get_order_tracker
from .telegram_notifier import TelegramNotifier, get_telegram_notifier

# Import Phase 1 and Phase 2 modules
from .tracking_scope import TrackingScope, get_tracking_scope


class EODCleanup:
    """
    Performs end-of-day cleanup and reconciliation tasks.
    Generates daily summary and prepares system for next trading day.
    """

    def __init__(
        self,
        broker_client,
        tracking_scope: TrackingScope | None = None,
        order_tracker: OrderTracker | None = None,
        order_verifier: OrderStatusVerifier | None = None,
        manual_matcher: ManualOrderMatcher | None = None,
        telegram_notifier: TelegramNotifier | None = None,
        user_id: int | None = None,
    ):
        """
        Initialize EOD cleanup manager.

        Args:
            broker_client: Broker API client
            tracking_scope: TrackingScope instance
            order_tracker: OrderTracker instance
            order_verifier: OrderStatusVerifier instance
            manual_matcher: ManualOrderMatcher instance
            telegram_notifier: TelegramNotifier instance
            user_id: Optional user ID for notification preferences
        """
        self.broker_client = broker_client
        self.tracking_scope = tracking_scope or get_tracking_scope()
        self.order_tracker = order_tracker or get_order_tracker()
        self.order_verifier = order_verifier
        self.manual_matcher = manual_matcher or get_manual_order_matcher()
        self.telegram_notifier = telegram_notifier or get_telegram_notifier()
        self.user_id = user_id

    def run_eod_cleanup(self) -> dict[str, Any]:
        """
        Execute complete end-of-day cleanup workflow.

        Returns:
            Dict with cleanup results and statistics
        """
        logger.info("=" * 70)
        logger.info("STARTING END-OF-DAY CLEANUP")
        logger.info("=" * 70)

        start_time = datetime.now()

        results = {
            "start_time": start_time.isoformat(),
            "date": start_time.strftime("%Y-%m-%d"),
            "steps_completed": [],
            "steps_failed": [],
            "statistics": {},
        }

        # Step 1: Final order status verification
        logger.info("\n[Step 1/6] Final order status verification...")
        try:
            verification_results = self._verify_all_pending_orders()
            results["statistics"]["verification"] = verification_results
            results["steps_completed"].append("verification")
            logger.info("[OK] Order verification complete")
        except Exception as e:
            logger.error(f"[FAIL] Order verification failed: {e}", exc_info=True)
            results["steps_failed"].append("verification")

        # Step 2: Manual trade reconciliation
        logger.info("\n[Step 2/6] Manual trade reconciliation...")
        try:
            reconciliation_results = self._reconcile_manual_trades()
            results["statistics"]["reconciliation"] = reconciliation_results
            results["steps_completed"].append("reconciliation")
            logger.info("[OK] Manual trade reconciliation complete")
        except Exception as e:
            logger.error(f"[FAIL] Manual trade reconciliation failed: {e}", exc_info=True)
            results["steps_failed"].append("reconciliation")

        # Step 3: Cleanup stale pending orders
        logger.info("\n[Step 3/6] Cleaning up stale orders...")
        try:
            cleanup_results = self._cleanup_stale_orders()
            results["statistics"]["cleanup"] = cleanup_results
            results["steps_completed"].append("cleanup")
            logger.info("[OK] Stale order cleanup complete")
        except Exception as e:
            logger.error(f"[FAIL] Stale order cleanup failed: {e}", exc_info=True)
            results["steps_failed"].append("cleanup")

        # Step 4: Generate daily statistics
        logger.info("\n[Step 4/6] Generating daily statistics...")
        try:
            daily_stats = self._generate_daily_statistics()
            results["statistics"]["daily"] = daily_stats
            results["steps_completed"].append("statistics")
            logger.info("[OK] Daily statistics generated")
        except Exception as e:
            logger.error(f"[FAIL] Statistics generation failed: {e}", exc_info=True)
            results["steps_failed"].append("statistics")

        # Step 5: Send Telegram summary
        logger.info("\n[Step 5/6] Sending Telegram summary...")
        try:
            telegram_sent = self._send_telegram_summary(results["statistics"])
            results["telegram_sent"] = telegram_sent
            results["steps_completed"].append("telegram")
            logger.info("[OK] Telegram summary sent")
        except Exception as e:
            logger.error(f"[FAIL] Telegram summary failed: {e}", exc_info=True)
            results["steps_failed"].append("telegram")

        # Step 6: Archive completed tracking entries
        logger.info("\n[Step 6/6] Archiving completed entries...")
        try:
            archive_results = self._archive_completed_entries()
            results["statistics"]["archive"] = archive_results
            results["steps_completed"].append("archive")
            logger.info("[OK] Archiving complete")
        except Exception as e:
            logger.error(f"[FAIL] Archiving failed: {e}", exc_info=True)
            results["steps_failed"].append("archive")

        # Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        results["end_time"] = end_time.isoformat()
        results["duration_seconds"] = duration
        results["success"] = len(results["steps_failed"]) == 0

        logger.info("\n" + "=" * 70)
        logger.info("END-OF-DAY CLEANUP COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Duration: {duration:.2f}s")
        logger.info(f"Steps Completed: {len(results['steps_completed'])}/6")
        logger.info(f"Steps Failed: {len(results['steps_failed'])}/6")

        if results["steps_failed"]:
            logger.warning(f"Failed steps: {', '.join(results['steps_failed'])}")
        else:
            logger.info("[OK] All steps completed successfully")

        return results

    def _verify_all_pending_orders(self) -> dict[str, Any]:
        """
        Final verification of all pending orders.

        EOD cleanup always performs verification to ensure latest order status
        before end of day, regardless of when OrderStatusVerifier last ran.
        This is a critical final check and should not be skipped.
        """
        if not self.order_verifier:
            logger.warning("Order verifier not available, skipping")
            return {"skipped": True}

        # EOD cleanup always verifies - this is a critical final check
        # Check if OrderStatusVerifier ran very recently (within 1 minute) to log info
        last_check = self.order_verifier.get_last_check_time()
        if last_check:
            time_since_check = datetime.now() - last_check
            minutes_since_check = time_since_check.total_seconds() / 60

            if minutes_since_check < 1.0:
                logger.info(
                    f"OrderStatusVerifier ran {minutes_since_check:.1f} minutes ago, "
                    f"but EOD cleanup will verify anyway for final status check"
                )

        # Always perform verification for EOD cleanup
        counts = self.order_verifier.verify_pending_orders()

        logger.info(
            f"Final verification: "
            f"{counts['checked']} checked, "
            f"{counts['executed']} executed, "
            f"{counts['rejected']} rejected, "
            f"{counts['still_pending']} still pending"
        )

        return counts

    def _reconcile_manual_trades(self) -> dict[str, Any]:
        """Reconcile manual trades with tracked symbols."""
        try:
            # Fetch current holdings from broker
            holdings_response = self.broker_client.get_holdings()

            holdings: list[dict[str, Any]] = []
            if isinstance(holdings_response, list):
                holdings = holdings_response
            elif isinstance(holdings_response, dict):
                data = holdings_response.get("data")
                if isinstance(data, list):
                    holdings = data
                elif isinstance(data, dict):
                    holdings = [data]
                elif isinstance(holdings_response.get("holdings"), list):
                    holdings = holdings_response.get("holdings") or []
                else:
                    # Common broker response when there are no holdings.
                    # Treat as empty instead of erroring EOD cleanup.
                    logger.info(
                        "Holdings response did not include list payload; "
                        "continuing reconciliation with empty holdings."
                    )
                    holdings = []
            else:
                logger.error(f"Unexpected holdings response format: {type(holdings_response)}")
                return {"error": "Invalid response format"}

            logger.info(f"Fetched {len(holdings)} holdings from broker for reconciliation")

            # Reconcile with tracking scope
            reconciliation = self.manual_matcher.reconcile_holdings_with_tracking(holdings)

            # Detect position closures - wrap in try-catch to handle errors gracefully
            try:
                closed_positions = self.manual_matcher.detect_position_closures(holdings)
                reconciliation["closed_positions"] = closed_positions
            except Exception as e:
                logger.warning(f"Error detecting position closures: {e}")
                reconciliation["closed_positions"] = []

            # Log summary
            summary = self.manual_matcher.get_reconciliation_summary(reconciliation)
            logger.info("\n" + summary)

            return reconciliation

        except Exception as e:
            logger.error(f"Manual trade reconciliation error: {e}", exc_info=True)
            return {"error": str(e)}

    def _cleanup_stale_orders(self) -> dict[str, Any]:
        """
        Remove stale pending orders that are older than the end of market hours
        of the next trading day (excluding holidays and weekends).

        Logic:
        - For each order, calculate the market close time of the next trading day
          after the order was placed
        - If current time is after that calculated time, the order is stale and removed
        - Excludes weekends (Saturday, Sunday) and holidays

        Returns:
            Dict with cleanup results
        """
        try:
            from .utils.trading_day_utils import get_next_trading_day_close
        except ImportError:
            logger.error("trading_day_utils not available, falling back to 24-hour cleanup")
            # Fallback to old logic if utility not available
            cutoff_time = datetime.now() - timedelta(hours=24)
            pending_orders = self.order_tracker.get_pending_orders(status_filter="PENDING")
            if not pending_orders:
                return {"removed": 0, "remaining": 0, "cutoff_time": cutoff_time.isoformat()}

            removed_count = 0
            for order in pending_orders:
                placed_at_str = order.get("placed_at")
                if not placed_at_str:
                    continue
                try:
                    placed_at = datetime.fromisoformat(placed_at_str)
                    if placed_at < cutoff_time:
                        order_id = order["order_id"]
                        symbol = order["symbol"]
                        logger.warning(
                            f"Removing stale order (fallback): {symbol} (order_id: {order_id})"
                        )
                        self.order_tracker.remove_pending_order(order_id)
                        removed_count += 1
                except Exception as e:
                    logger.error(f"Error parsing placed_at time: {e}")

            remaining = len(self.order_tracker.get_pending_orders(status_filter="PENDING"))
            logger.info(
                f"Cleanup (fallback): Removed {removed_count} stale order(s), {remaining} remaining"
            )
            return {
                "removed": removed_count,
                "remaining": remaining,
                "cutoff_time": cutoff_time.isoformat(),
                "method": "fallback_24h",
            }

        # Get current time (prefer timezone-aware IST)
        try:
            from src.infrastructure.db.timezone_utils import IST, ist_now

            current_time = ist_now()
            # Normalize to IST for consistent comparison
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=IST)
            elif current_time.tzinfo != IST:
                current_time = current_time.astimezone(IST)
        except ImportError:
            current_time = datetime.now()

        pending_orders = self.order_tracker.get_pending_orders(status_filter="PENDING")

        if not pending_orders:
            logger.info("No pending orders to clean up")
            return {"removed": 0, "remaining": 0}

        removed_count = 0
        removed_details = []

        for order in pending_orders:
            placed_at_str = order.get("placed_at")

            if not placed_at_str:
                continue

            try:
                placed_at = datetime.fromisoformat(placed_at_str)

                # Normalize placed_at to match current_time's timezone awareness
                # This ensures we can safely subtract them later
                if current_time.tzinfo is None and placed_at.tzinfo is not None:
                    # current_time is naive, make placed_at naive too
                    placed_at = placed_at.replace(tzinfo=None)
                elif current_time.tzinfo is not None and placed_at.tzinfo is None:
                    # current_time is aware, make placed_at aware too (assume IST)
                    try:
                        from src.infrastructure.db.timezone_utils import IST

                        placed_at = placed_at.replace(tzinfo=IST)
                    except ImportError:
                        # If IST not available, convert to current_time's timezone
                        placed_at = placed_at.replace(tzinfo=current_time.tzinfo)
                elif current_time.tzinfo is not None and placed_at.tzinfo is not None:
                    # Both are aware, ensure same timezone
                    if current_time.tzinfo != placed_at.tzinfo:
                        placed_at = placed_at.astimezone(current_time.tzinfo)

                # Calculate next trading day market close from when order was placed
                # get_next_trading_day_close handles both naive and timezone-aware datetimes
                # and returns timezone-aware datetime in IST
                next_trading_day_close = get_next_trading_day_close(placed_at)

                # Normalize for comparison (both should be timezone-aware in IST)
                # If current_time is naive, convert next_trading_day_close to naive for comparison
                if current_time.tzinfo is None and next_trading_day_close.tzinfo is not None:
                    next_trading_day_close = next_trading_day_close.replace(tzinfo=None)
                elif current_time.tzinfo is not None and next_trading_day_close.tzinfo is not None:
                    # Both are timezone-aware, ensure same timezone
                    if current_time.tzinfo != next_trading_day_close.tzinfo:
                        next_trading_day_close = next_trading_day_close.astimezone(
                            current_time.tzinfo
                        )

                # If current time is after next trading day market close, order is stale
                if current_time > next_trading_day_close:
                    # Stale order - remove it
                    order_id = order["order_id"]
                    symbol = order["symbol"]

                    age_hours = (current_time - placed_at).total_seconds() / 3600
                    days_old = (current_time.date() - placed_at.date()).days

                    logger.warning(
                        f"Removing stale order: {symbol} (order_id: {order_id}, "
                        f"placed: {placed_at.strftime('%Y-%m-%d %H:%M:%S')}, "
                        f"next trading day close: {next_trading_day_close.strftime('%Y-%m-%d %H:%M:%S')}, "
                        f"age: {age_hours:.1f}h / {days_old}d)"
                    )

                    self.order_tracker.remove_pending_order(order_id)
                    removed_count += 1
                    removed_details.append(
                        {
                            "symbol": symbol,
                            "order_id": order_id,
                            "placed_at": placed_at.isoformat(),
                            "next_trading_day_close": next_trading_day_close.isoformat(),
                        }
                    )

            except Exception as e:
                logger.error(f"Error processing order for cleanup: {e}", exc_info=True)

        remaining = len(self.order_tracker.get_pending_orders(status_filter="PENDING"))

        logger.info(
            f"Cleanup: Removed {removed_count} stale order(s) "
            f"(older than next trading day market close), {remaining} remaining"
        )

        return {
            "removed": removed_count,
            "remaining": remaining,
            "method": "next_trading_day_close",
            "removed_details": removed_details,
        }

    def _generate_daily_statistics(self) -> dict[str, Any]:
        """Generate comprehensive daily statistics."""
        stats = {}

        # Tracking statistics - wrap in try-catch to handle corrupted data gracefully
        try:
            all_symbols = self.tracking_scope.get_tracked_symbols(status="all")
            active_symbols = self.tracking_scope.get_tracked_symbols(status="active")
            completed_symbols = self.tracking_scope.get_tracked_symbols(status="completed")

            stats["tracking"] = {
                "total_symbols": len(all_symbols),
                "active_symbols": len(active_symbols),
                "completed_symbols": len(completed_symbols),
            }
        except Exception as e:
            logger.warning(f"Error generating tracking statistics: {e}. Using defaults.")
            stats["tracking"] = {
                "total_symbols": 0,
                "active_symbols": 0,
                "completed_symbols": 0,
            }

        # Order statistics - wrap in try-catch to handle errors gracefully
        try:
            all_pending = self.order_tracker.get_pending_orders()
            pending_orders = [o for o in all_pending if o.get("status") == "PENDING"]
            executed_orders = [o for o in all_pending if o.get("status") == "EXECUTED"]
            rejected_orders = [o for o in all_pending if o.get("status") == "REJECTED"]

            stats["orders"] = {
                "total_orders": len(all_pending),
                "pending": len(pending_orders),
                "executed": len(executed_orders),
                "rejected": len(rejected_orders),
            }
        except Exception as e:
            logger.warning(f"Error generating order statistics: {e}. Using defaults.")
            stats["orders"] = {
                "total_orders": 0,
                "pending": 0,
                "executed": 0,
                "rejected": 0,
            }

        logger.info(
            f"Daily stats: "
            f"{stats['tracking']['active_symbols']} active symbols, "
            f"{stats['orders']['executed']} executed, "
            f"{stats['orders']['rejected']} rejected, "
            f"{stats['orders']['pending']} pending"
        )

        return stats

    def _send_telegram_summary(self, statistics: dict[str, Any]) -> bool:
        """Send daily summary via Telegram."""
        if not self.telegram_notifier or not self.telegram_notifier.enabled:
            logger.info("Telegram notifier disabled, skipping summary")
            return False

        # Extract statistics
        daily_stats = statistics.get("daily", {})
        tracking_stats = daily_stats.get("tracking", {})
        order_stats = daily_stats.get("orders", {})
        reconciliation = statistics.get("reconciliation", {})

        # Send daily summary
        return self.telegram_notifier.notify_daily_summary(
            orders_placed=order_stats.get("total_orders", 0),
            orders_executed=order_stats.get("executed", 0),
            orders_rejected=order_stats.get("rejected", 0),
            orders_pending=order_stats.get("pending", 0),
            tracked_symbols=tracking_stats.get("active_symbols", 0),
            additional_stats={
                "Manual Buys": reconciliation.get("manual_buys_detected", 0),
                "Manual Sells": reconciliation.get("manual_sells_detected", 0),
                "Positions Closed": len(reconciliation.get("closed_positions", [])),
            },
            user_id=self.user_id,
        )

    def _archive_completed_entries(self) -> dict[str, Any]:
        """
        Archive completed tracking entries (optional future enhancement).
        For now, just counts them.

        Returns:
            Dict with archive results
        """
        try:
            completed_symbols = self.tracking_scope.get_tracked_symbols(status="completed")
            logger.info(f"Found {len(completed_symbols)} completed tracking entries")
        except Exception as e:
            logger.warning(f"Error retrieving completed entries: {e}. Using default count.")
            completed_symbols = []

        # Future: Could move to archive file or database
        # For now, they stay in the main file with status="completed"

        return {
            "completed_count": len(completed_symbols),
            "archived": False,  # Not implemented yet
            "note": "Archiving not yet implemented - entries remain with status=completed",
        }


# Singleton instance
_eod_cleanup_instance: EODCleanup | None = None


def get_eod_cleanup(broker_client, **kwargs) -> EODCleanup:
    """
    Get or create EOD cleanup singleton.

    Args:
        broker_client: Broker API client
        **kwargs: Additional arguments for EODCleanup

    Returns:
        EODCleanup instance
    """
    global _eod_cleanup_instance

    if _eod_cleanup_instance is None:
        _eod_cleanup_instance = EODCleanup(broker_client, **kwargs)

    return _eod_cleanup_instance


def schedule_eod_cleanup(
    broker_client, target_time: str = "18:00", callback: Callable | None = None
) -> None:
    """
    Schedule EOD cleanup to run at specific time daily.

    Args:
        broker_client: Broker API client
        target_time: Target time in HH:MM format (24-hour)
        callback: Optional callback after cleanup completes

    Note:
        This is a simple implementation. For production, consider using
        a proper scheduler like APScheduler or system cron.
    """
    import threading
    import time

    def wait_and_run():
        while True:
            now = datetime.now()
            target_hour, target_minute = map(int, target_time.split(":"))

            # Calculate next target time
            target_dt = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

            if target_dt <= now:
                # Target time has passed today, schedule for tomorrow
                target_dt += timedelta(days=1)

            wait_seconds = (target_dt - now).total_seconds()

            logger.info(
                f"EOD cleanup scheduled for {target_dt.strftime('%Y-%m-%d %H:%M:%S')} "
                f"(in {wait_seconds / 3600:.1f} hours)"
            )

            # Wait until target time
            time.sleep(wait_seconds)

            # Run cleanup
            try:
                logger.info(f"Triggering scheduled EOD cleanup at {datetime.now()}")
                eod_cleanup = get_eod_cleanup(broker_client)
                results = eod_cleanup.run_eod_cleanup()

                if callback:
                    callback(results)

            except Exception as e:
                logger.error(f"Scheduled EOD cleanup failed: {e}", exc_info=True)

    # Run in background thread
    thread = threading.Thread(target=wait_and_run, daemon=True)
    thread.start()

    logger.info(f"EOD cleanup scheduler started (target time: {target_time})")
