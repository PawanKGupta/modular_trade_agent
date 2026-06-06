# ruff: noqa: PLC0415
"""
Background Jobs / Scheduler

Scheduled tasks for the trading application:
- MTM (Mark-to-Market) updates at market close
- Daily PnL calculations
- Data cleanup tasks
- Daily performance-fee billing reconcile (mark overdue invoices)
- Monthly performance-fee invoices (broker users) after month close
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from server.app.services.mtm_updater import update_mtm_for_all_users

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


def closed_month_to_bill(now_ist: datetime) -> tuple[int, int]:
    """Calendar month to invoice: the month that ended immediately before *now_ist* (IST)."""
    if now_ist.tzinfo is None:
        raise ValueError("now_ist must be timezone-aware")
    first_this_month = now_ist.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day_prev_month = first_this_month - timedelta(days=1)
    return last_day_prev_month.year, last_day_prev_month.month


# Global scheduler instance
scheduler = AsyncIOScheduler()


def job_billing_reconcile():
    """Mark past-due performance fee bills as overdue (no subscription renewal / grace sweeps)."""
    try:
        from src.application.services.billing_reconciliation_service import (
            BillingReconciliationService,
        )
        from src.infrastructure.db.session import SessionLocal

        with SessionLocal() as db:
            stats = BillingReconciliationService(db).run()
        logger.info("Billing reconcile: %s", stats)
    except Exception:
        logger.exception("Billing reconcile job failed")


def job_performance_bills_month_close():
    """Generate performance-fee bills for broker users for the calendar month that just ended."""
    try:
        from src.application.services.performance_billing_service import PerformanceBillingService
        from src.infrastructure.db.session import SessionLocal

        year, month = closed_month_to_bill(datetime.now(IST))
        with SessionLocal() as db:
            bills = PerformanceBillingService(db).close_month_for_all_broker_users(year, month)
        logger.info(
            "Performance bills month-close %04d-%02d: generated %d bill(s)",
            year,
            month,
            len(bills),
        )
    except Exception:
        logger.exception("Performance bills month-close job failed")


def start_scheduler():
    """
    Initialize and start the background job scheduler
    """
    if scheduler.running:
        logger.warning("Scheduler already running")
        return

    # MTM Update: Daily at 3:30 PM IST (market close)
    scheduler.add_job(
        job_mtm_update,
        trigger=CronTrigger(hour=15, minute=30, timezone="Asia/Kolkata"),
        id="mtm_daily_update",
        name="Daily MTM Update at Market Close",
        replace_existing=True,
    )

    scheduler.add_job(
        job_billing_reconcile,
        trigger=CronTrigger(hour=6, minute=0, timezone="Asia/Kolkata"),
        id="billing_reconcile_daily",
        name="Daily performance bill overdue sweep",
        replace_existing=True,
    )

    # Performance fee invoices: 00:30 IST on the 1st — bills the *previous* calendar month.
    scheduler.add_job(
        job_performance_bills_month_close,
        trigger=CronTrigger(day=1, hour=0, minute=30, timezone="Asia/Kolkata"),
        id="performance_bills_month_close",
        name="Monthly performance-fee bills (broker users)",
        replace_existing=True,
    )

    # Optional: Run MTM update on startup (disabled by default)
    # scheduler.add_job(
    #     job_mtm_update,
    #     trigger="date",
    #     run_date=datetime.now(),
    #     id="mtm_startup",
    #     name="MTM Update on Startup",
    # )

    scheduler.start()
    logger.info("Scheduler started with jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name} (ID: {job.id})")


def stop_scheduler():
    """
    Stop the background job scheduler
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


def job_mtm_update():
    """
    Scheduled job: Update MTM for all users
    """
    try:
        logger.info("Starting scheduled MTM update")
        results = update_mtm_for_all_users()

        total_updated = sum(stats.get("updated", 0) for stats in results.values())
        total_failed = sum(stats.get("failed", 0) for stats in results.values())
        total_skipped = sum(stats.get("skipped", 0) for stats in results.values())

        logger.info(
            f"MTM update completed: "
            f"{len(results)} users, "
            f"{total_updated} positions updated, "
            f"{total_failed} failed, "
            f"{total_skipped} skipped"
        )

    except Exception as e:
        logger.exception(f"Error in scheduled MTM update: {e}")


# Expose scheduler for manual job management
__all__ = [
    "scheduler",
    "start_scheduler",
    "stop_scheduler",
    "job_mtm_update",
    "job_billing_reconcile",
    "job_performance_bills_month_close",
    "closed_month_to_bill",
]
