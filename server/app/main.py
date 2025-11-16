import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect

from src.infrastructure.db.base import Base
from src.infrastructure.db.session import engine

from .core.config import settings
from .routers import admin, auth, signals, user

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
            print(
                "[Startup] Database schema not found. Creating tables via Base.metadata.create_all()"
            )
            Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[Startup] Failed to ensure DB schema: {e}")
        raise


@app.middleware("http")
async def log_exceptions(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        # Log full traceback for debugging 500s
        print("Unhandled exception:", exc)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(user.router, prefix="/api/v1/user", tags=["user"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(signals.router, prefix="/api/v1/signals", tags=["signals"])
