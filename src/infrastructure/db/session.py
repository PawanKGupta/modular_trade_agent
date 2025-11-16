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

# Safety check: Warn if tests might be using production database
# Tests should NEVER use this shared engine - they should create their own test engines
if not is_memory and "pytest" in sys.modules:
    import warnings

    real_db_path = os.path.abspath(os.path.join(os.getcwd(), "data", "app.db"))
    if DB_URL.startswith("sqlite:///"):
        db_path = DB_URL.replace("sqlite:///", "", 1)
        if os.path.abspath(db_path) == real_db_path:
            warnings.warn(
                f"WARNING: Tests are running with production database URL: {DB_URL}. "
                "Tests should set DB_URL='sqlite:///:memory:' before importing this module.",
                RuntimeWarning,
                stacklevel=2,
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
