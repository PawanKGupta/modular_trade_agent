import os
import sys

from sqlalchemy import create_engine
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
    engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


# Best-effort ensure tables exist early, helpful for tests that don't trigger app lifespan
try:
    Base.metadata.create_all(bind=engine)
except Exception:
    # Non-fatal; FastAPI lifespan in server/app/main.py will also create on startup
    pass


def get_session():
    """Provide a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
