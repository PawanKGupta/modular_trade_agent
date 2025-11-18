import asyncio
import contextlib
import logging
import os
import sys
import traceback
import uuid
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect

from src.application.services.log_retention_service import LogRetentionService
from src.infrastructure.db.base import Base
from src.infrastructure.db.models import UserRole, Users
from src.infrastructure.db.session import SessionLocal, engine
from src.infrastructure.persistence.user_repository import UserRepository

from .core.config import settings
from .routers import (
    activity,
    admin,
    auth,
    broker,
    logs,
    ml,
    orders,
    paper_trading,
    pnl,
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

app = FastAPI(title="Trade Agent API", version="1.0.0", debug=True)

# Configure file logging to capture errors for analysis
LOG_DIR = os.path.abspath(os.path.join(ROOT_DIR, "logs"))
os.makedirs(LOG_DIR, exist_ok=True)
log_path = os.path.join(LOG_DIR, "server_api.log")
file_handler = RotatingFileHandler(log_path, maxBytes=2 * 1024 * 1024, backupCount=3)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
file_handler.setFormatter(formatter)
root_logger = logging.getLogger()
if not any(
    isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", "") == log_path
    for h in root_logger.handlers
):
    root_logger.addHandler(file_handler)
root_logger.setLevel(logging.INFO)

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
                    UserRepository(db).create_user(
                        email=settings.admin_email,
                        password=settings.admin_password,
                        name=settings.admin_name,
                        role=UserRole.ADMIN,
                    )
                except Exception as e:
                    print(f"[Startup] Failed to create admin user: {e}")
    except Exception as e:
        print(f"[Startup] Failed to ensure DB schema: {e}")
        raise


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
app.include_router(trading_config.router, prefix="/api/v1/user", tags=["trading-config"])
app.include_router(service.router, prefix="/api/v1/user", tags=["service"])
app.include_router(orders.router, prefix="/api/v1/user/orders", tags=["orders"])
app.include_router(pnl.router, prefix="/api/v1/user/pnl", tags=["pnl"])
app.include_router(broker.router, prefix="/api/v1/user/broker", tags=["broker"])
app.include_router(activity.router, prefix="/api/v1/user/activity", tags=["activity"])
app.include_router(targets.router, prefix="/api/v1/user/targets", tags=["targets"])
app.include_router(paper_trading.router, prefix="/api/v1/user/paper-trading", tags=["paper-trading"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(ml.router, prefix="/api/v1", tags=["admin-ml"])
app.include_router(logs.router, prefix="/api/v1", tags=["logs"])
app.include_router(signals.router, prefix="/api/v1/signals", tags=["signals"])


async def _log_retention_worker():
    """Periodically purge old logs/errors based on retention policy."""
    while True:
        try:
            with SessionLocal() as db:
                LogRetentionService(db).purge_older_than(settings.log_retention_days)
        except Exception:
            logging.exception("Log retention cleanup failed")
        await asyncio.sleep(24 * 60 * 60)


@app.on_event("startup")
async def start_log_retention_worker():
    app.state.log_retention_task = asyncio.create_task(_log_retention_worker())


@app.on_event("shutdown")
async def stop_log_retention_worker():
    task = getattr(app.state, "log_retention_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
