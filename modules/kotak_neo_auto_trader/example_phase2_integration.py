#!/usr/bin/env python3
"""
Example: Phase 2 Integration with Auto Trade Engine

This example shows how to use the Auto Trade Engine with Phase 2 features:
- Automated order status verification (30-min checks)
- Telegram notifications for rejections/executions
- Manual trade detection and reconciliation
- End-of-day cleanup and summary

Configuration:
1. Set environment variables:
   export TELEGRAM_BOT_TOKEN="your_token"
   export TELEGRAM_CHAT_ID="your_chat_id"

2. Run the script:
   python -m modules.kotak_neo_auto_trader.example_phase2_integration
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
from utils.logger import logger


def example_basic_usage():
    """
    Example 1: Basic usage with all Phase 2 features enabled (default).
    """
    logger.info("=" * 70)
    logger.info("EXAMPLE 1: Basic Phase 2 Integration")
    logger.info("=" * 70)

    # Initialize engine (Phase 2 enabled by default)
    engine = AutoTradeEngine(
        env_file="kotak_neo.env",
        enable_verifier=True,  # Enable 30-min order checks
        enable_telegram=True,  # Enable Telegram notifications
        enable_eod_cleanup=True,  # Enable EOD cleanup
        verifier_interval=1800,  # Check every 30 minutes
    )

    # Login (automatically initializes Phase 2 modules)
    if engine.login():
        logger.info("[OK] Logged in successfully")
        logger.info("[OK] Phase 2 modules initialized")

        # Your trading logic here
        # - Place orders (automatically tracked)
        # - Order verifier monitors in background
        # - Telegram sends notifications
        # - Manual trades detected during reconciliation

        # Run main trading loop
        engine.run(keep_session=True)

        # Cleanup
        engine.logout()
        logger.info("[OK] Logged out successfully")
    else:
        logger.error("Login failed")


def example_telegram_test():
    """
    Example 2: Test Telegram connectivity before trading.
    """
    logger.info("=" * 70)
    logger.info("EXAMPLE 2: Test Telegram Connection")
    logger.info("=" * 70)

    from modules.kotak_neo_auto_trader.telegram_notifier import get_telegram_notifier

    # Check if credentials are set
    if not os.getenv("TELEGRAM_BOT_TOKEN") or not os.getenv("TELEGRAM_CHAT_ID"):
        logger.error("Telegram credentials not set!")
        logger.error("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables")
        return

    # Test connection
    notifier = get_telegram_notifier()

    if notifier.test_connection():
        logger.info("[OK] Telegram connection successful!")

        # Send test notifications
        notifier.notify_system_alert(
            alert_type="System Test",
            message_text="Phase 2 integration test successful!",
            severity="SUCCESS",
        )
    else:
        logger.error("[FAIL] Telegram connection failed")
        logger.error("Check your bot token and chat ID")


def example_manual_eod_cleanup():
    """
    Example 3: Manually trigger EOD cleanup (usually runs automatically at 6 PM).
    """
    logger.info("=" * 70)
    logger.info("EXAMPLE 3: Manual EOD Cleanup")
    logger.info("=" * 70)

    engine = AutoTradeEngine(env_file="kotak_neo.env")

    if engine.login():
        logger.info("[OK] Logged in")

        # Manually run EOD cleanup
        if engine.eod_cleanup:
            logger.info("Running EOD cleanup manually...")
            results = engine.eod_cleanup.run_eod_cleanup()

            logger.info(f"\n{'=' * 70}")
            logger.info("EOD Cleanup Results:")
            logger.info(f"  Success: {results['success']}")
            logger.info(f"  Duration: {results['duration_seconds']:.2f}s")
            logger.info(f"  Steps Completed: {len(results['steps_completed'])}/6")
            if results["steps_failed"]:
                logger.warning(f"  Failed Steps: {', '.join(results['steps_failed'])}")
            logger.info(f"{'=' * 70}\n")
        else:
            logger.warning("EOD cleanup not initialized")

        engine.logout()
    else:
        logger.error("Login failed")


def example_scheduled_eod_cleanup():
    """
    Example 4: Schedule automatic EOD cleanup at 6 PM daily.
    """
    logger.info("=" * 70)
    logger.info("EXAMPLE 4: Scheduled EOD Cleanup")
    logger.info("=" * 70)

    from modules.kotak_neo_auto_trader.eod_cleanup import schedule_eod_cleanup

    engine = AutoTradeEngine(env_file="kotak_neo.env")

    if engine.login():
        logger.info("[OK] Logged in")

        # Schedule EOD cleanup for 6 PM IST daily
        def eod_callback(results):
            """Called after each EOD cleanup."""
            logger.info(f"EOD cleanup completed: {results['success']}")
            if engine.telegram_notifier and engine.telegram_notifier.enabled:
                engine.telegram_notifier.notify_system_alert(
                    alert_type="EOD Cleanup",
                    message_text=f"Completed in {results['duration_seconds']:.1f}s",
                    severity="SUCCESS" if results["success"] else "WARNING",
                )

        schedule_eod_cleanup(
            broker_client=engine.orders,
            target_time="18:00",
            callback=eod_callback,  # 6 PM IST
        )

        logger.info("[OK] EOD cleanup scheduled for 18:00 IST daily")
        logger.info("  (runs in background thread)")

        # Keep program running (or integrate with your main loop)
        try:
            import time

            logger.info("\nPress Ctrl+C to stop...")
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("\nShutting down...")
            engine.logout()


def example_disable_phase2():
    """
    Example 5: Disable Phase 2 features (use only Phase 1).
    """
    logger.info("=" * 70)
    logger.info("EXAMPLE 5: Phase 1 Only (Disable Phase 2)")
    logger.info("=" * 70)

    # Disable all Phase 2 features
    engine = AutoTradeEngine(
        env_file="kotak_neo.env",
        enable_verifier=False,  # No automated checks
        enable_telegram=False,  # No notifications
        enable_eod_cleanup=False,  # No EOD cleanup
    )

    if engine.login():
        logger.info("[OK] Logged in (Phase 2 disabled)")
        logger.info("  - Order tracking: [OK] (Phase 1)")
        logger.info("  - Order verifier: [FAIL] (disabled)")
        logger.info("  - Telegram: [FAIL] (disabled)")
        logger.info("  - EOD cleanup: [FAIL] (disabled)")

        # Your trading logic here
        engine.run(keep_session=True)

        engine.logout()
    else:
        logger.error("Login failed")


def main():
    """Run examples."""
    import argparse

    parser = argparse.ArgumentParser(description="Phase 2 Integration Examples")
    parser.add_argument(
        "example",
        nargs="?",
        default="1",
        choices=["1", "2", "3", "4", "5"],
        help="Example to run (1-5)",
    )

    args = parser.parse_args()

    examples = {
        "1": ("Basic Phase 2 Integration", example_basic_usage),
        "2": ("Test Telegram Connection", example_telegram_test),
        "3": ("Manual EOD Cleanup", example_manual_eod_cleanup),
        "4": ("Scheduled EOD Cleanup", example_scheduled_eod_cleanup),
        "5": ("Phase 1 Only (Disable Phase 2)", example_disable_phase2),
    }

    title, func = examples[args.example]

    logger.info("\n" + "=" * 70)
    logger.info(f"Running Example {args.example}: {title}")
    logger.info("=" * 70 + "\n")

    try:
        func()
    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user")
    except Exception as e:
        logger.error(f"Example failed: {e}", exc_info=True)


if __name__ == "__main__":
    main()
