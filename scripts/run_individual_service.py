#!/usr/bin/env python3
"""
Run Individual Service Script

This script is used to run individual trading services (e.g., sell_monitor, premarket_retry)
as separate processes. It's called by IndividualServiceManager to spawn service processes.

Usage:
    python scripts/run_individual_service.py --user-id <user_id> --task <task_name>

Args:
    --user-id: User ID for the service
    --task: Task name (premarket_retry, sell_monitor, analysis, buy_orders, end_of_day)
"""

import argparse
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Imports after path modification (required for module resolution)
from src.application.services.individual_service_manager import (  # noqa: E402
    IndividualServiceManager,
)
from src.infrastructure.db.session import get_db  # noqa: E402
from src.infrastructure.logging import get_user_logger  # noqa: E402


def run_service_loop(user_id: int, task_name: str, db_session):  # noqa: PLR0912
    """
    Run the service in a continuous loop until stopped.

    Args:
        user_id: User ID
        task_name: Task name
        db_session: Database session
    """
    logger = get_user_logger(user_id=user_id, db=db_session, module="IndividualService")
    service_manager = IndividualServiceManager(db_session)

    logger.info(
        f"Starting individual service loop: {task_name}",
        action="start_service_loop",
        task_name=task_name,
    )

    try:
        # Mark service as running
        service_manager._status_repo.mark_running(user_id, task_name)
        db_session.commit()

        # Run the service loop
        # For continuous services like sell_monitor, this runs until stopped
        # For one-time tasks, this executes once and exits
        while True:
            # Check if service should stop
            status = service_manager._status_repo.get_status(user_id, task_name)
            if status and status.status == "stopped":
                logger.info(
                    f"Service {task_name} marked as stopped, exiting loop",
                    action="stop_service_loop",
                    task_name=task_name,
                )
                break

            # Execute the task
            try:
                # Use run_once to execute the task (it handles execution tracking)
                success, message, details = service_manager.run_once(
                    user_id, task_name, execution_type="scheduled"
                )
                if not success:
                    logger.error(
                        f"Task execution failed: {message}",
                        action="execute_task",
                        task_name=task_name,
                    )
                    # For continuous services, continue even on failure
                    # For one-time tasks, exit on failure
                    if task_name not in ["sell_monitor"]:
                        break
            except Exception as e:
                logger.error(
                    f"Error executing task {task_name}: {e}",
                    exc_info=e,
                    action="execute_task",
                    task_name=task_name,
                )
                # For continuous services, continue even on error
                # For one-time tasks, exit on error
                if task_name not in ["sell_monitor"]:
                    break

            # For continuous services, wait before next iteration
            # For one-time tasks, exit after first execution
            if task_name in ["sell_monitor"]:
                # Continuous service - wait 60 seconds before next iteration
                time.sleep(60)
            elif task_name in ["premarket_retry", "analysis", "buy_orders", "eod_cleanup"]:
                # One-time task - exit after execution
                logger.info(
                    f"One-time task {task_name} completed, exiting",
                    action="task_completed",
                    task_name=task_name,
                )
                break
            else:
                # Unknown task - exit
                logger.warning(
                    f"Unknown task type {task_name}, exiting",
                    action="unknown_task",
                    task_name=task_name,
                )
                break

    except KeyboardInterrupt:
        logger.info(
            f"Service {task_name} interrupted by user",
            action="interrupt_service",
            task_name=task_name,
        )
    except Exception as e:
        logger.error(
            f"Fatal error in service loop for {task_name}: {e}",
            exc_info=e,
            action="fatal_error",
            task_name=task_name,
        )
    finally:
        # Mark service as stopped
        try:
            service_manager._status_repo.mark_stopped(user_id, task_name)
            db_session.commit()
        except Exception as e:
            logger.error(
                f"Failed to mark service as stopped: {e}",
                exc_info=e,
                action="cleanup_error",
                task_name=task_name,
            )


def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(description="Run individual trading service")
    parser.add_argument("--user-id", type=int, required=True, help="User ID")
    parser.add_argument("--task", type=str, required=True, help="Task name")

    args = parser.parse_args()

    # Get database session
    db = next(get_db())

    try:
        logger = get_user_logger(user_id=args.user_id, db=db, module="IndividualService")
        logger.info(
            f"Starting individual service script: task={args.task}, user_id={args.user_id}",
            action="script_start",
            task_name=args.task,
        )

        # Run the service loop
        run_service_loop(args.user_id, args.task, db)

    except Exception as e:
        logger = get_user_logger(user_id=args.user_id, db=db, module="IndividualService")
        logger.error(
            f"Fatal error in individual service script: {e}",
            exc_info=e,
            action="script_error",
            task_name=args.task,
        )
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
