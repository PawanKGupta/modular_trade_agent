import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure models are imported so Base.metadata is populated
import src.infrastructure.db.models  # noqa: F401

from .base import Base  # Declarative base

DB_URL = os.getenv("DB_URL", "sqlite:///./data/app.db")
is_sqlite = DB_URL.startswith("sqlite")
is_memory = is_sqlite and (":memory:" in DB_URL or DB_URL.rstrip("/") in {"sqlite://", "sqlite:/"})

# Safety check: Prevent tests from using production database
# Tests should NEVER use this shared engine - they should create their own test engines
if not is_memory and "pytest" in sys.modules:
    # Check for common production database paths
    cwd = os.getcwd()
    real_db_paths = [
        os.path.abspath(os.path.join(cwd, "data", "app.db")),
        os.path.abspath(os.path.join(cwd, "app.db")),
        os.path.abspath(os.path.join(cwd, "app.dev.db")),
    ]

    if DB_URL.startswith("sqlite:///"):
        db_path = DB_URL.replace("sqlite:///", "", 1)
        abs_db_path = os.path.abspath(db_path)
        if abs_db_path in real_db_paths:
            raise RuntimeError(
                f"CRITICAL: Tests are attempting to use production database: {DB_URL}. "
                "This will destroy your data! Set DB_URL='sqlite:///:memory:' before running tests. "
                "The conftest.py fixture should handle this automatically."
            )

if is_memory:
    # In-memory SQLite across threads requires StaticPool and check_same_thread=False
    engine = create_engine(
        DB_URL,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
elif is_sqlite:
    # File-based SQLite: allow cross-thread usage for TestClient, increase timeout
    engine = create_engine(
        DB_URL,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
else:
    # PostgreSQL/Production: Optimized pool settings for multi-threaded scheduler
    # Each active service uses 2 connections: main thread + scheduler thread
    engine = create_engine(
        DB_URL,
        echo=False,
        future=True,
        pool_size=15,  # Max persistent connections (up from default 5)
        max_overflow=30,  # Extra connections when pool exhausted (up from default 10)
        pool_timeout=30,  # Wait 30s for connection before timeout
        pool_recycle=3600,  # Recycle connections every hour (prevent stale connections)
        pool_pre_ping=False,  # Disabled: psycopg2 raises "set_session cannot be used inside a transaction" during ping
    )
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


# Best-effort ensure tables exist early, helpful for tests that don't trigger app lifespan
try:
    Base.metadata.create_all(bind=engine)
except Exception:
    # Non-fatal; FastAPI lifespan in server/app/main.py will also create on startup
    pass


def get_session():
    """
    Provide a transactional scope around a series of operations.

    Handles transaction lifecycle automatically:
    - Commits on success (if no explicit commit was made)
    - Rolls back on exceptions
    - Always closes the session

    This prevents "idle in transaction" connection leaks when exceptions occur.
    """
    db = SessionLocal()
    try:
        # Force connection checkout and clear any leftover transaction state
        # (e.g. "prepared" state from a previous request that failed during commit).
        # Session doesn't get a connection until first use; rollback() alone may be a no-op.
        try:
            db.execute(text("SELECT 1"))
            db.rollback()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        yield db
        # Success path: commit transaction if still active
        try:
            db.commit()
        except Exception:
            # If commit fails (e.g., already committed), rollback and re-raise
            try:
                db.rollback()
            except Exception:
                pass  # Ignore rollback errors (transaction might already be closed)
            raise
    except Exception:
        # Exception path: rollback transaction to prevent "idle in transaction" state
        try:
            db.rollback()
        except Exception:
            # Ignore rollback errors (transaction might already be closed or connection lost)
            # The original exception will still be raised
            pass
        raise
    finally:
        # Always close the session to return connection to pool
        # This ensures connections are never left open
        try:
            db.close()
        except Exception:
            # Ignore close errors (session might already be closed)
            # This is safe - if close fails, the connection will be recycled by the pool
            pass
