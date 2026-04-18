"""
Background Jobs / Scheduler

Scheduled tasks for the trading application:
- MTM (Mark-to-Market) updates at market close
- Daily PnL calculations
- Data cleanup tasks
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from server.app.services.mtm_updater import update_mtm_for_all_users

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


def job_billing_reconcile():
    """Renewal reminders, grace expiry, and subscription housekeeping."""
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
        name="Daily billing reconciliation",
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
]
