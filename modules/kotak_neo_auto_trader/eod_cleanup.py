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

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path

# Use existing project logger
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

# Import Phase 1 and Phase 2 modules
from .tracking_scope import TrackingScope, get_tracking_scope
from .order_tracker import OrderTracker, get_order_tracker
from .order_status_verifier import OrderStatusVerifier
from .manual_order_matcher import ManualOrderMatcher, get_manual_order_matcher
from .telegram_notifier import TelegramNotifier, get_telegram_notifier


class EODCleanup:
    """
    Performs end-of-day cleanup and reconciliation tasks.
    Generates daily summary and prepares system for next trading day.
    """

    def __init__(
        self,
        broker_client,
        tracking_scope: Optional[TrackingScope] = None,
        order_tracker: Optional[OrderTracker] = None,
        order_verifier: Optional[OrderStatusVerifier] = None,
        manual_matcher: Optional[ManualOrderMatcher] = None,
        telegram_notifier: Optional[TelegramNotifier] = None,
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
        """
        self.broker_client = broker_client
        self.tracking_scope = tracking_scope or get_tracking_scope()
        self.order_tracker = order_tracker or get_order_tracker()
        self.order_verifier = order_verifier
        self.manual_matcher = manual_matcher or get_manual_order_matcher()
        self.telegram_notifier = telegram_notifier or get_telegram_notifier()

    def run_eod_cleanup(self) -> Dict[str, Any]:
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

    def _verify_all_pending_orders(self) -> Dict[str, Any]:
        """Final verification of all pending orders."""
        if not self.order_verifier:
            logger.warning("Order verifier not available, skipping")
            return {"skipped": True}

        counts = self.order_verifier.verify_pending_orders()

        logger.info(
            f"Final verification: "
            f"{counts['checked']} checked, "
            f"{counts['executed']} executed, "
            f"{counts['rejected']} rejected, "
            f"{counts['still_pending']} still pending"
        )

        return counts

    def _reconcile_manual_trades(self) -> Dict[str, Any]:
        """Reconcile manual trades with tracked symbols."""
        try:
            # Fetch current holdings from broker
            holdings_response = self.broker_client.get_holdings()

            if isinstance(holdings_response, list):
                holdings = holdings_response
            elif isinstance(holdings_response, dict) and "data" in holdings_response:
                holdings = holdings_response["data"]
            else:
                logger.error(f"Unexpected holdings response format: {type(holdings_response)}")
                return {"error": "Invalid response format"}

            # Reconcile with tracking scope
            reconciliation = self.manual_matcher.reconcile_holdings_with_tracking(holdings)

            # Detect position closures
            closed_positions = self.manual_matcher.detect_position_closures(holdings)
            reconciliation["closed_positions"] = closed_positions

            # Log summary
            summary = self.manual_matcher.get_reconciliation_summary(reconciliation)
            logger.info("\n" + summary)

            return reconciliation

        except Exception as e:
            logger.error(f"Manual trade reconciliation error: {e}", exc_info=True)
            return {"error": str(e)}

    def _cleanup_stale_orders(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """
        Remove stale pending orders older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours before order is considered stale

        Returns:
            Dict with cleanup results
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        pending_orders = self.order_tracker.get_pending_orders(status_filter="PENDING")

        if not pending_orders:
            logger.info("No pending orders to clean up")
            return {"removed": 0, "remaining": 0}

        removed_count = 0

        for order in pending_orders:
            placed_at_str = order.get("placed_at")

            if not placed_at_str:
                continue

            try:
                placed_at = datetime.fromisoformat(placed_at_str)

                if placed_at < cutoff_time:
                    # Stale order - remove it
                    order_id = order["order_id"]
                    symbol = order["symbol"]

                    logger.warning(
                        f"Removing stale order: {symbol} (order_id: {order_id}, "
                        f"age: {(datetime.now() - placed_at).total_seconds() / 3600:.1f}h)"
                    )

                    self.order_tracker.remove_pending_order(order_id)
                    removed_count += 1

            except Exception as e:
                logger.error(f"Error parsing placed_at time: {e}")

        remaining = len(self.order_tracker.get_pending_orders(status_filter="PENDING"))

        logger.info(f"Cleanup: Removed {removed_count} stale order(s), {remaining} remaining")

        return {
            "removed": removed_count,
            "remaining": remaining,
            "cutoff_time": cutoff_time.isoformat(),
        }

    def _generate_daily_statistics(self) -> Dict[str, Any]:
        """Generate comprehensive daily statistics."""
        stats = {}

        # Tracking statistics
        all_symbols = self.tracking_scope.get_tracked_symbols(status="all")
        active_symbols = self.tracking_scope.get_tracked_symbols(status="active")
        completed_symbols = self.tracking_scope.get_tracked_symbols(status="completed")

        stats["tracking"] = {
            "total_symbols": len(all_symbols),
            "active_symbols": len(active_symbols),
            "completed_symbols": len(completed_symbols),
        }

        # Order statistics
        all_pending = self.order_tracker.get_pending_orders()
        pending_orders = [o for o in all_pending if o["status"] == "PENDING"]
        executed_orders = [o for o in all_pending if o["status"] == "EXECUTED"]
        rejected_orders = [o for o in all_pending if o["status"] == "REJECTED"]

        stats["orders"] = {
            "total_orders": len(all_pending),
            "pending": len(pending_orders),
            "executed": len(executed_orders),
            "rejected": len(rejected_orders),
        }

        logger.info(
            f"Daily stats: "
            f"{stats['tracking']['active_symbols']} active symbols, "
            f"{stats['orders']['executed']} executed, "
            f"{stats['orders']['rejected']} rejected, "
            f"{stats['orders']['pending']} pending"
        )

        return stats

    def _send_telegram_summary(self, statistics: Dict[str, Any]) -> bool:
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
        )

    def _archive_completed_entries(self) -> Dict[str, Any]:
        """
        Archive completed tracking entries (optional future enhancement).
        For now, just counts them.

        Returns:
            Dict with archive results
        """
        completed_symbols = self.tracking_scope.get_tracked_symbols(status="completed")

        logger.info(f"Found {len(completed_symbols)} completed tracking entries")

        # Future: Could move to archive file or database
        # For now, they stay in the main file with status="completed"

        return {
            "completed_count": len(completed_symbols),
            "archived": False,  # Not implemented yet
            "note": "Archiving not yet implemented - entries remain with status=completed",
        }


# Singleton instance
_eod_cleanup_instance: Optional[EODCleanup] = None


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
    broker_client, target_time: str = "18:00", callback: Optional[Callable] = None
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
    import time
    import threading

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
