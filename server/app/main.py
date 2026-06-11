import asyncio
import contextlib
import logging
import os
import socket
import sys
import traceback
import uuid
from logging.handlers import RotatingFileHandler

# Single-process unified runner (optional). Default disabled to avoid double-start with user-triggered runs.
RUN_UNIFIED_IN_API = os.getenv("RUN_UNIFIED_IN_API", "0") not in ("0", "false", "False")
UNIFIED_USER_IDS = [
    int(uid.strip())
    for uid in os.getenv("UNIFIED_USER_IDS", "").split(",")
    if uid.strip().isdigit()
]
# IPv4 resolution control (scoped + configurable)
_original_getaddrinfo = socket.getaddrinfo
_FORCE_IPV4 = os.getenv("FORCE_IPV4", "1") not in ("0", "false", "False")
_BROKER_HOSTS_IPV4_ONLY = {
    "gw-napi.kotaksecurities.com",
}
_BROKER_IPV4_HOST = os.getenv("BROKER_IPV4_HOST", "gw-napi.kotaksecurities.com")
_BROKER_IPV4_PORT = int(os.getenv("BROKER_IPV4_PORT", "443"))
_BROKER_IPV4_TIMEOUT = float(os.getenv("BROKER_IPV4_TIMEOUT", "3.0"))


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """
    Force IPv4-only DNS resolution for broker hosts when enabled.
    """
    if not _FORCE_IPV4:
        return _original_getaddrinfo(host, port, family, type, proto, flags)

    if host in _BROKER_HOSTS_IPV4_ONLY:
        return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    return _original_getaddrinfo(host, port, family, type, proto, flags)


# Apply IPv4-only resolution globally for FastAPI server (scoped to broker hosts)
socket.getaddrinfo = _ipv4_getaddrinfo


def _check_broker_ipv4_connectivity() -> bool:
    """
    Quick IPv4 connectivity probe to the broker host.
    Logs a warning if IPv4 is forced but not reachable.
    """
    if not _FORCE_IPV4:
        return True
    try:
        with socket.create_connection(
            (_BROKER_IPV4_HOST, _BROKER_IPV4_PORT), timeout=_BROKER_IPV4_TIMEOUT
        ):
            return True
    except Exception as exc:  # pragma: no cover - warning path validated in tests
        logging.getLogger(__name__).warning(
            "IPv4 connectivity check to broker host failed: %s:%s (%s). "
            "Set FORCE_IPV4=0 to disable IPv4-only if your network requires IPv6.",
            _BROKER_IPV4_HOST,
            _BROKER_IPV4_PORT,
            exc,
        )
        return False


class SafeRotatingFileHandler(RotatingFileHandler):
    """
    RotatingFileHandler that gracefully handles permission errors during rotation.

    In Docker containers with mounted volumes, log rotation can fail due to permission
    issues. This handler catches those errors and continues logging without breaking
    the application.
    """

    _rotation_warning_printed = False  # Class-level flag to suppress repeated warnings
    _rotation_disabled = False  # Class-level flag to disable rotation after first failure

    def __init__(self, *args, **kwargs):
        """Initialize handler and ensure log directory has proper permissions."""
        super().__init__(*args, **kwargs)
        # Check if we're in Docker and disable rotation immediately
        if self._is_docker_environment():
            SafeRotatingFileHandler._rotation_disabled = True
        # Ensure log file has write permissions
        self._ensure_permissions()

    @staticmethod
    def _is_docker_environment():
        """Check if running in Docker container."""
        try:
            # Check for Docker-specific files/environment
            if os.path.exists("/.dockerenv"):
                return True
            if os.path.exists("/proc/self/cgroup"):
                with open("/proc/self/cgroup") as f:
                    if "docker" in f.read():
                        return True
            if os.getenv("DOCKER_CONTAINER") == "true":
                return True
            return False
        except Exception:
            return False

    def _ensure_permissions(self):
        """Ensure log file and directory have proper write permissions."""
        try:
            import os
            import stat

            log_dir = os.path.dirname(self.baseFilename)
            # Ensure directory exists and is writable
            os.makedirs(log_dir, exist_ok=True)
            # Try to set directory permissions (may fail in Docker, that's OK)
            try:
                os.chmod(log_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH)
            except (OSError, PermissionError):
                pass  # Ignore permission errors - may not have chmod rights

            # If log file exists, ensure it's writable
            if os.path.exists(self.baseFilename):
                try:
                    os.chmod(
                        self.baseFilename, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
                    )
                except (OSError, PermissionError):
                    pass  # Ignore permission errors
        except Exception:
            pass  # If permission setting fails, continue anyway

    def _can_rotate(self):
        """Check if rotation is possible by testing file operations."""
        if SafeRotatingFileHandler._rotation_disabled:
            return False

        try:
            import os

            log_dir = os.path.dirname(self.baseFilename)
            # Test if we can create and rename files in the log directory
            test_file = os.path.join(log_dir, ".rotation_test")
            try:
                # Try to create a test file
                with open(test_file, "w") as f:
                    f.write("test")
                # Try to rename it
                test_renamed = test_file + ".renamed"
                os.rename(test_file, test_renamed)
                # Clean up
                if os.path.exists(test_renamed):
                    os.remove(test_renamed)
                return True
            except (OSError, PermissionError):
                # Clean up test file if it exists
                try:
                    if os.path.exists(test_file):
                        os.remove(test_file)
                except Exception:
                    pass
                return False
        except Exception:
            return False

    def doRollover(self):
        """
        Override doRollover to handle permission errors gracefully.
        """
        # Check if rotation is disabled or not possible
        if SafeRotatingFileHandler._rotation_disabled or not self._can_rotate():
            # Silently skip rotation - logging will continue to current file
            return

        try:
            # Check if rotation is actually needed
            if self.stream:
                try:
                    # Flush and close the stream before rotation
                    self.stream.flush()
                except Exception:
                    pass  # Ignore flush errors

            # Attempt rotation
            super().doRollover()
            # Reset flags on successful rotation
            SafeRotatingFileHandler._rotation_warning_printed = False
            SafeRotatingFileHandler._rotation_disabled = False
        except (OSError, PermissionError) as e:
            # Disable rotation for this session after first failure
            SafeRotatingFileHandler._rotation_disabled = True

            # Only print warning once to avoid log spam
            if not SafeRotatingFileHandler._rotation_warning_printed:
                try:
                    import sys

                    print(
                        f"Warning: Log rotation failed due to permission error: {e}. "
                        "Continuing to log to current file. Rotation disabled for this session.",
                        file=sys.stderr,
                    )
                    SafeRotatingFileHandler._rotation_warning_printed = True
                except Exception:
                    pass  # If even stderr fails, just continue silently
            # Don't re-raise - allow logging to continue to the current file
            # Try to ensure the stream is still open for writing
            try:
                if self.stream and self.stream.closed:
                    self.stream = self._open()
            except Exception:
                pass  # If we can't reopen, the next emit will handle it


from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect

from src.application.services.log_retention_service import LogRetentionService
from src.infrastructure.db.base import Base
from src.infrastructure.db.models import UserRole, Users
from src.infrastructure.db.session import SessionLocal, engine
from src.infrastructure.persistence.settings_repository import SettingsRepository
from src.infrastructure.persistence.user_repository import UserRepository

from .core.config import settings
from .routers import (
    admin,
    auth,
    billing_admin,
    billing_user,
    billing_webhooks,
    broker,
    export,
    logs,
    metrics,
    ml,
    monitoring,
    notification_preferences,
    notifications,
    orders,
    paper_trading,
    pnl,
    portfolio,
    reports,
    service,
    signals,
    targets,
    trading_config,
    user,
)

# Ensure project root is on sys.path so `src.*` imports work when running from server/
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

app = FastAPI(title="Rebound API", version="26.1.1", debug=True)
_unified_tasks = []

# Configure file logging to capture errors for analysis
LOG_DIR = os.path.abspath(os.path.join(ROOT_DIR, "logs"))
os.makedirs(LOG_DIR, exist_ok=True)
log_path = os.path.join(LOG_DIR, "server_api.log")


# Detect Docker environment - rotation often fails in Docker with mounted volumes
def _is_docker_environment():
    """Check if running in Docker container."""
    try:
        # Check for Docker-specific files/environment
        if os.path.exists("/.dockerenv"):
            return True
        if os.path.exists("/proc/self/cgroup"):
            with open("/proc/self/cgroup") as f:
                if "docker" in f.read():
                    return True
        if os.getenv("DOCKER_CONTAINER") == "true":
            return True
        return False
    except Exception:
        return False


# Test if rotation is possible before creating handler
# In Docker with mounted volumes, rotation may not be possible due to permissions
def _can_rotate_logs():
    """Test if log rotation is possible in the logs directory."""
    # In Docker, prefer simple handler to avoid permission issues
    if _is_docker_environment():
        return False

    try:
        test_file = os.path.join(LOG_DIR, ".rotation_test")
        test_renamed = test_file + ".renamed"
        try:
            # Try to create and rename a test file
            with open(test_file, "w") as f:
                f.write("test")
            os.rename(test_file, test_renamed)
            # Clean up
            if os.path.exists(test_renamed):
                os.remove(test_renamed)
            return True
        except (OSError, PermissionError):
            # Clean up test file if it exists
            try:
                if os.path.exists(test_file):
                    os.remove(test_file)
            except Exception:
                pass
            return False
    except Exception:
        return False


# File logging is optional: bind-mounted logs/ is often owned by the host user (not UID
# 1000 `trader`). Console/docker logs still capture output (same pattern as utils/logger.py).
def _configure_root_file_logging() -> None:
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root_logger = logging.getLogger()
    try:
        if _can_rotate_logs():
            file_handler = SafeRotatingFileHandler(
                log_path, maxBytes=2 * 1024 * 1024, backupCount=3
            )
        else:
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        if not any(
            isinstance(h, (RotatingFileHandler, SafeRotatingFileHandler, logging.FileHandler))
            and getattr(h, "baseFilename", "") == log_path
            for h in root_logger.handlers
        ):
            root_logger.addHandler(file_handler)
    except OSError as exc:
        logging.getLogger(__name__).warning(
            "API file logging disabled (%s): %s", log_path, exc
        )
    root_logger.setLevel(logging.INFO)


_configure_root_file_logging()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
async def ensure_db_schema():
    """
    Ensure required tables exist on startup.
    For initial development, auto-create missing tables to avoid 'no such table' errors
    if migrations were not run. In production, prefer running Alembic migrations.
    """
    try:
        inspector = inspect(engine)
        if not inspector.has_table("users"):
            print("[Startup] Database schema missing; creating via metadata.create_all()")
            Base.metadata.create_all(bind=engine)
        # Bootstrap admin if database is empty and env variables are provided
        with SessionLocal() as db:
            users_count = db.query(Users).count()
            if users_count == 0 and settings.admin_email and settings.admin_password:
                try:
                    print(f"[Startup] No users found. Creating admin user {settings.admin_email}")
                    user = UserRepository(db).create_user(
                        email=settings.admin_email,
                        password=settings.admin_password,
                        name=settings.admin_name,
                        role=UserRole.ADMIN,
                    )
                    UserRepository(db).mark_email_verified(user)
                    # Create default settings for admin user (required for services to work)
                    print(f"[Startup] Creating default settings for admin user {user.id}")
                    SettingsRepository(db).ensure_default(user.id)
                    print("[Startup] Admin user and settings created successfully")
                except Exception as e:
                    print(f"[Startup] Failed to create admin user: {e}")

            # Orphan cleanup + auto-restore (DB + persisted snapshot on data volume)
            try:
                from src.application.services.service_restore_snapshot import (
                    cleanup_and_restore_services,
                )

                cleanup_and_restore_services(db)
            except Exception as cleanup_error:
                print(f"[Startup] Warning: Failed to cleanup/restore services: {cleanup_error}")
                traceback.print_exc()

    except Exception as e:
        print(f"[Startup] Failed to ensure DB schema: {e}")
        raise


@app.on_event("shutdown")
def persist_service_snapshot_on_shutdown():
    """Write running-service snapshot before process exit (survives on /app/data volume)."""
    try:
        from src.application.services.service_restore_snapshot import (
            persist_service_restore_snapshot,
        )
        from src.infrastructure.db.session import SessionLocal

        with SessionLocal() as db:
            persist_service_restore_snapshot(db, source="shutdown")
    except Exception as exc:
        print(f"[Shutdown] Warning: Failed to save service restore snapshot: {exc}")


@app.on_event("startup")
async def broker_ipv4_health_check():
    """Run a quick IPv4 connectivity probe to the broker host on startup."""
    _check_broker_ipv4_connectivity()


@app.on_event("startup")
async def start_unified_services():
    """
    Optionally start unified trading services inside the API process to ensure
    a single Kotak client/session owner (reduces OTP/login churn).
    """
    if not RUN_UNIFIED_IN_API:
        return

    # Lazy imports to avoid overhead when disabled
    try:
        import asyncio

        from modules.kotak_neo_auto_trader.run_trading_service import TradingService
        from modules.kotak_neo_auto_trader.shared_session_manager import (
            get_shared_session_manager,
        )
    except Exception as exc:
        print(f"[Startup] Unified service imports failed, skipping: {exc}")
        return

    # Determine which users to start; if none specified, skip to avoid unintended login
    user_ids = UNIFIED_USER_IDS
    if not user_ids:
        print(
            "[Startup] RUN_UNIFIED_IN_API is enabled but UNIFIED_USER_IDS is empty; skipping unified start."
        )
        return

    loop = asyncio.get_event_loop()
    for uid in user_ids:
        try:
            auth = get_shared_session_manager().get_or_create_session(
                user_id=uid, env_file="modules/kotak_neo_auto_trader/kotak_neo.env"
            )
            if not auth:
                print(
                    f"[Startup] Unified service: failed to obtain session for user {uid}, skipping."
                )
                continue

            service = TradingService(
                user_id=uid, env_file="modules/kotak_neo_auto_trader/kotak_neo.env"
            )
            service.auth = auth
            task = loop.create_task(service.run_async())
            _unified_tasks.append(task)
            print(f"[Startup] Unified service started in API process for user {uid}")
        except Exception as exc:
            print(f"[Startup] Unified service start failed for user {uid}: {exc}")


@app.middleware("http")
async def log_exceptions(request: Request, call_next):
    req_id = str(uuid.uuid4())
    request.state.request_id = req_id
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    except Exception as exc:
        # Log full traceback for debugging 500s
        print(f"Unhandled exception [{req_id}]:", exc)
        traceback.print_exc()
        return JSONResponse(
            status_code=500, content={"detail": "Internal Server Error", "request_id": req_id}
        )


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(user.router, prefix="/api/v1/user", tags=["user"])
app.include_router(billing_user.router, prefix="/api/v1/user", tags=["billing"])
app.include_router(trading_config.router, prefix="/api/v1/user", tags=["trading-config"])
app.include_router(service.router, prefix="/api/v1/user", tags=["service"])
app.include_router(orders.router, prefix="/api/v1/user/orders", tags=["orders"])
app.include_router(pnl.router, prefix="/api/v1/user/pnl", tags=["pnl"])
app.include_router(export.router, prefix="/api/v1/user/export", tags=["export"])
app.include_router(reports.router, prefix="/api/v1/user/reports", tags=["reports"])
app.include_router(broker.router, prefix="/api/v1/user/broker", tags=["broker"])
app.include_router(targets.router, prefix="/api/v1/user", tags=["targets"])
app.include_router(portfolio.router, prefix="/api/v1/user/portfolio", tags=["portfolio"])
app.include_router(
    paper_trading.router, prefix="/api/v1/user/paper-trading", tags=["paper-trading"]
)
app.include_router(
    notification_preferences.router, prefix="/api/v1/user", tags=["notification-preferences"]
)
app.include_router(notifications.router, prefix="/api/v1/user", tags=["notifications"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(billing_admin.router, prefix="/api/v1/admin", tags=["admin-billing"])
app.include_router(ml.router, prefix="/api/v1", tags=["admin-ml"])
app.include_router(logs.router, prefix="/api/v1", tags=["logs"])
app.include_router(signals.router, prefix="/api/v1/signals", tags=["signals"])
app.include_router(billing_webhooks.router, prefix="/api/v1/billing", tags=["billing-webhooks"])
app.include_router(monitoring.router, prefix="/api/v1/admin/monitoring", tags=["monitoring"])


async def _log_retention_worker():
    """Periodically purge old logs/errors based on retention policy."""
    while True:
        try:
            with SessionLocal() as db:
                LogRetentionService(db).purge_older_than(settings.log_retention_days)
        except Exception:
            logging.exception("Log retention cleanup failed")
        await asyncio.sleep(24 * 60 * 60)


async def _individual_subprocess_reaper_worker(interval_seconds: int = 45):
    """
    Poll spawned individual-service Popen handles and reap exited children.

    Keeps SQLite/Postgres task status aligned when processes exit outside stop_service
    and prevents zombie buildup on the API worker (waitpid runs via subprocess.Popen.poll).
    """
    from src.application.services.individual_service_manager import IndividualServiceManager

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            with SessionLocal() as db:
                n = IndividualServiceManager(db).cleanup_stopped_processes()
                if n:
                    logging.getLogger(__name__).info(
                        "Reaped %s stopped individual-service subprocess(es)", n
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Individual-service subprocess reap failed")


@app.on_event("startup")
async def start_log_retention_worker():
    app.state.log_retention_task = asyncio.create_task(_log_retention_worker())


@app.on_event("startup")
async def start_individual_subprocess_reaper():
    """Background reap for IndividualServiceManager child processes."""
    app.state.individual_subprocess_reaper_task = asyncio.create_task(
        _individual_subprocess_reaper_worker()
    )


@app.on_event("startup")
async def start_background_scheduler():
    """Start the background job scheduler for MTM updates and other scheduled tasks"""
    try:
        from server.app.jobs import start_scheduler

        start_scheduler()
        logging.info("Background scheduler started successfully")
    except Exception as e:
        logging.error(f"Failed to start background scheduler: {e}")


@app.on_event("shutdown")
async def stop_log_retention_worker():
    task = getattr(app.state, "log_retention_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    # File-based logging doesn't require shutdown


@app.on_event("shutdown")
async def stop_individual_subprocess_reaper():
    reap_task = getattr(app.state, "individual_subprocess_reaper_task", None)
    if reap_task:
        reap_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reap_task


@app.on_event("shutdown")
async def stop_background_scheduler():
    """Stop the background job scheduler"""
    try:
        from server.app.jobs import stop_scheduler

        stop_scheduler()
        logging.info("Background scheduler stopped")
    except Exception as e:
        logging.error(f"Failed to stop background scheduler: {e}")
