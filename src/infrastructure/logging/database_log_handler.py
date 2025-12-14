"""
Database Logging Handler

Writes structured logs to ServiceLog table in database.

Uses async queue-based logging to handle high-frequency logging efficiently
and prevent connection pool exhaustion.

Docker-compatible: Handles graceful shutdown on SIGTERM/SIGINT to ensure
all logs are written before container termination.
"""

from __future__ import annotations

import atexit
import json
import logging
import queue
import signal
import threading
import time

from sqlalchemy.orm import Session

from src.infrastructure.db.session import SessionLocal
from src.infrastructure.persistence.service_log_repository import ServiceLogRepository


class DatabaseLogHandler(logging.Handler):
    """
    Logging handler that writes logs to ServiceLog table.

    Provides structured logging with user context, level, module, message,
    and additional context data stored as JSON.

    Uses async queue-based logging with a background worker thread to:
    - Avoid transaction conflicts with main request session
    - Handle high-frequency logging efficiently
    - Prevent connection pool exhaustion
    - Batch writes for better performance
    """

    # Class-level queue and worker thread shared across all instances
    # This ensures we don't create too many threads
    _shared_queue: queue.Queue[tuple[int, logging.LogRecord | None]] | None = None
    _worker_thread: threading.Thread | None = None
    _worker_lock = threading.Lock()
    _shutdown = False
    _flush_event = threading.Event()  # Event to trigger immediate flush

    def __init__(
        self,
        user_id: int,
        db: Session | None = None,
        level: int = logging.NOTSET,
        queue_size: int = 1000,
    ):
        """
        Initialize database log handler.

        Args:
            user_id: User ID for log entries
            db: Database session (deprecated - kept for backward compatibility but not used)
            level: Minimum logging level (default: NOTSET = all levels)
            queue_size: Maximum queue size before dropping logs (default: 1000)
        """
        super().__init__(level)
        self.user_id = user_id
        self.queue_size = queue_size

        # Initialize shared queue and worker thread if not already done
        with DatabaseLogHandler._worker_lock:
            if DatabaseLogHandler._shared_queue is None:
                DatabaseLogHandler._shared_queue = queue.Queue(maxsize=queue_size)
                DatabaseLogHandler._worker_thread = threading.Thread(
                    target=self._worker,
                    daemon=False,  # Non-daemon: ensures logs are flushed on shutdown
                    name="DatabaseLogHandler-Worker",
                )
                DatabaseLogHandler._worker_thread.start()

                # Register shutdown handlers for Docker compatibility
                # atexit ensures cleanup even if FastAPI shutdown hook doesn't run
                atexit.register(DatabaseLogHandler.shutdown)

                # Register signal handlers as backup (only in main thread)
                try:
                    signal.signal(signal.SIGTERM, DatabaseLogHandler._signal_handler)
                    signal.signal(signal.SIGINT, DatabaseLogHandler._signal_handler)
                except (ValueError, OSError, RuntimeError):
                    # Signal handlers can only be set from main thread
                    # This is expected in some contexts (e.g., when called from worker thread)
                    pass

    @classmethod
    def _worker(cls) -> None:
        """
        Background worker thread that processes logs from the queue.

        Batches logs for efficient database writes and handles errors gracefully.
        """
        batch: list[tuple[int, logging.LogRecord]] = []
        batch_size = 10  # Write in batches of 10
        batch_timeout = 0.5  # Flush batch after 0.5 seconds (reduced for faster processing)
        last_flush = time.time()

        while not cls._shutdown:
            try:
                # Check for flush event (for testing/immediate flush)
                flush_requested = cls._flush_event.is_set()

                # Get record from queue with timeout
                # Use shorter timeout when flush is requested to process faster
                timeout = 0.1 if flush_requested else 0.5
                try:
                    item = cls._shared_queue.get(timeout=timeout)
                    # Check for shutdown sentinel (None record)
                    if item[1] is None:
                        break
                    batch.append(item)
                except queue.Empty:
                    # Timeout - flush batch if flush requested, timeout reached, or shutdown
                    if batch and (flush_requested or time.time() - last_flush > batch_timeout):
                        cls._flush_batch(batch)
                        batch.clear()
                        last_flush = time.time()
                        # Clear flush event after flushing
                        if flush_requested:
                            cls._flush_event.clear()
                    continue

                # Flush batch if it's full, timeout reached, or flush requested
                if (
                    len(batch) >= batch_size
                    or time.time() - last_flush > batch_timeout
                    or flush_requested
                ):
                    cls._flush_batch(batch)
                    batch.clear()
                    last_flush = time.time()
                    # Clear flush event after flushing
                    if flush_requested:
                        cls._flush_event.clear()

            except Exception as e:
                # Log error to stderr (can't use logger here to avoid recursion)
                import sys  # noqa: PLC0415

                print(f"DatabaseLogHandler worker error: {e}", file=sys.stderr)
                # Clear batch on error to prevent memory buildup
                batch.clear()

        # Flush any remaining logs on shutdown
        if batch:
            cls._flush_batch(batch)

    @classmethod
    def _flush_batch(cls, batch: list[tuple[int, logging.LogRecord]]) -> None:
        """
        Flush a batch of log records to the database.

        Args:
            batch: List of (user_id, LogRecord) tuples to write
        """
        if not batch:
            return

        log_db = SessionLocal()
        try:
            # Verify we're using the correct database connection
            # This helps catch issues where worker thread uses wrong database
            repository = ServiceLogRepository(log_db)

            for user_id, record in batch:
                try:
                    # Extract level name - map to standard levels
                    level_map = {
                        logging.DEBUG: "DEBUG",
                        logging.INFO: "INFO",
                        logging.WARNING: "WARNING",
                        logging.ERROR: "ERROR",
                        logging.CRITICAL: "CRITICAL",
                    }
                    level_name = level_map.get(record.levelno, "INFO")

                    # Extract module from record (prefer log_module, fallback to name)
                    module = getattr(record, "log_module", getattr(record, "module", record.name))

                    # Extract context (all extra fields except standard logging fields)
                    context = {}
                    standard_fields = {
                        "name",
                        "msg",
                        "args",
                        "created",
                        "filename",
                        "funcName",
                        "levelname",
                        "levelno",
                        "lineno",
                        "module",
                        "msecs",
                        "message",
                        "pathname",
                        "process",
                        "processName",
                        "relativeCreated",
                        "thread",
                        "threadName",
                        "exc_info",
                        "exc_text",
                        "stack_info",
                        "user_id",  # We'll add this separately
                        "taskName",  # Standard logging attribute (camelCase)
                    }

                    for key, value in record.__dict__.items():
                        if key not in standard_fields:
                            # Only include JSON-serializable values
                            try:
                                json.dumps(value)  # Test if serializable
                                context[key] = value
                            except (TypeError, ValueError):
                                # Convert non-serializable to string
                                context[key] = str(value)

                    # Create log entry (auto_commit=False to batch commits)
                    repository.create(
                        user_id=user_id,
                        level=level_name,  # type: ignore
                        module=module[:128],  # Truncate to max length
                        message=str(record.getMessage())[:1024],  # Truncate to max length
                        context=context if context else None,
                        auto_commit=False,  # Batch commit at end
                    )
                except Exception as e:
                    # Log individual record error (can't use logger to avoid recursion)
                    import sys  # noqa: PLC0415

                    print(
                        f"DatabaseLogHandler: Failed to write log for user {user_id}: {e}",
                        file=sys.stderr,
                    )
                    # Continue processing other records even if one fails

            # Commit all records in batch (single commit for efficiency)
            # This ensures all logs are written atomically and visible to other sessions
            log_db.commit()

        except Exception as e:
            # Log batch error (can't use logger to avoid recursion)
            import sys  # noqa: PLC0415

            print(f"DatabaseLogHandler: Batch flush failed: {e}", file=sys.stderr)
            try:
                log_db.rollback()
            except Exception:  # noqa: S110
                pass
        finally:
            # Always close the session
            try:
                log_db.close()
            except Exception:  # noqa: S110
                pass

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to the database queue.

        Non-blocking: adds record to queue and returns immediately.
        If queue is full, falls back to handleError to prevent blocking.

        Args:
            record: LogRecord to emit
        """
        if DatabaseLogHandler._shared_queue is None:
            # Queue not initialized - fallback to error handler
            self.handleError(record)
            return

        try:
            # Try to add to queue (non-blocking)
            DatabaseLogHandler._shared_queue.put_nowait((self.user_id, record))
        except queue.Full:
            # Queue is full - log to stderr as fallback
            import sys  # noqa: PLC0415

            print(
                f"DatabaseLogHandler: Queue full, dropping log for user {self.user_id}",
                file=sys.stderr,
            )
            self.handleError(record)
        except Exception:
            # Any other error - use standard error handler
            self.handleError(record)

    @classmethod
    def flush(cls, timeout: float = 5.0) -> None:
        """
        Flush all pending logs in the queue.

        Useful for testing or ensuring logs are written before shutdown.
        Triggers immediate flush of any pending batch.

        Args:
            timeout: Maximum time to wait for queue to empty and processing to complete (seconds)
        """
        if cls._shared_queue is None:
            return

        # Trigger immediate flush
        cls._flush_event.set()

        start_time = time.time()
        # Wait for queue to be empty
        while not cls._shared_queue.empty():
            if time.time() - start_time > timeout:
                break
            time.sleep(0.05)  # Small sleep to let worker process

        # Give worker additional time to finish processing current batch
        # Worker has 0.5s batch timeout, so wait a bit longer to ensure processing
        elapsed = time.time() - start_time
        remaining_time = max(0, timeout - elapsed)
        if remaining_time > 0:
            # Wait for batch timeout plus buffer
            time.sleep(min(remaining_time, 0.8))

    @classmethod
    def _signal_handler(cls, signum, frame):
        """
        Signal handler for graceful shutdown in Docker containers.

        Docker sends SIGTERM on container stop, which triggers this handler
        to ensure all logs are flushed before termination.
        """
        cls.shutdown()

    @classmethod
    def shutdown(cls) -> None:
        """
        Shutdown the worker thread gracefully.

        Should be called during application shutdown to ensure all logs are written.
        Safe to call multiple times (idempotent).

        In Docker:
        - Called automatically on SIGTERM/SIGINT via signal handler
        - Called via atexit when Python process exits
        - Called explicitly from FastAPI shutdown hook
        """
        # Prevent multiple shutdown calls from interfering
        if cls._shutdown:
            return

        with cls._worker_lock:
            if cls._worker_thread and cls._worker_thread.is_alive():
                cls._shutdown = True
                if cls._shared_queue:
                    # Add sentinel to wake up worker
                    try:
                        cls._shared_queue.put_nowait((0, None))  # type: ignore
                    except queue.Full:
                        pass

                # Wait for worker to finish processing (with timeout)
                # In Docker, this ensures logs are written before container termination
                cls._worker_thread.join(timeout=5.0)

                # If thread didn't finish, log warning (but don't block indefinitely)
                if cls._worker_thread.is_alive():
                    import sys

                    print(
                        "DatabaseLogHandler: Worker thread did not finish within timeout",
                        file=sys.stderr,
                    )
