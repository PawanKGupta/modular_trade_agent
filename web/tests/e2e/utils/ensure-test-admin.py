#!/usr/bin/env python3
"""
Ensure test admin user exists in e2e database
This script checks if the test admin user exists, and creates it if it doesn't
"""

import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Set database URL for e2e tests
os.environ["DB_URL"] = os.environ.get("E2E_DB_URL", "sqlite:///./data/e2e.db")

# Imports must come after path setup - noqa comments suppress lint warnings
from src.infrastructure.db.base import Base  # noqa: E402
from src.infrastructure.db.models import UserRole, Users  # noqa: E402
from src.infrastructure.db.session import SessionLocal, engine  # noqa: E402
from src.infrastructure.persistence.settings_repository import SettingsRepository  # noqa: E402
from src.infrastructure.persistence.user_repository import UserRepository  # noqa: E402

# Columns added after early E2E DBs; missing any model column means schema is stale.
_E2E_SCHEMA_PROBE_TABLE = Users.__table__


def _e2e_sqlite_path(db_url: str) -> Path:
    rel_path = db_url.replace("sqlite:///", "", 1)
    return Path(rel_path) if Path(rel_path).is_absolute() else project_root / rel_path


def _sqlite_schema_is_stale() -> bool:
    from sqlalchemy import inspect  # noqa: PLC0415

    inspector = inspect(engine)
    if not inspector.has_table(_E2E_SCHEMA_PROBE_TABLE.name):
        return False
    db_columns = {col["name"] for col in inspector.get_columns(_E2E_SCHEMA_PROBE_TABLE.name)}
    model_columns = {col.name for col in _E2E_SCHEMA_PROBE_TABLE.columns}
    return not model_columns.issubset(db_columns)


def migrate_e2e_schema() -> None:
    """Ensure the E2E database schema matches current SQLAlchemy models."""
    e2e_db_url = os.environ["DB_URL"]

    if e2e_db_url.startswith("sqlite:///"):
        db_path = _e2e_sqlite_path(e2e_db_url)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path.exists() and _sqlite_schema_is_stale():
            print(f"[INFO] Rebuilding stale E2E database: {db_path}")
            engine.dispose()
            db_path.unlink()
        Base.metadata.create_all(bind=engine)
        return

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(project_root),
        env={**os.environ, "DB_URL": e2e_db_url},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError("Alembic migration failed for E2E database")


def ensure_test_admin():
    """Ensure test admin user exists"""
    migrate_e2e_schema()

    db = SessionLocal()
    try:
        # Test admin credentials (must match test-config.ts)
        test_admin_email = os.environ.get("TEST_ADMIN_EMAIL", "testadmin@rebound.com")
        test_admin_password = os.environ.get("TEST_ADMIN_PASSWORD", "testadmin@123")

        # Check if test admin exists
        user = db.query(Users).filter(Users.email == test_admin_email).first()

        if user:
            print(f"[OK] Test admin user already exists: {test_admin_email} (ID: {user.id})")
            # Ensure user is admin
            repo = UserRepository(db)
            if user.role != UserRole.ADMIN:
                print("[INFO] Updating user role to admin...")
                repo.update_user(user, role=UserRole.ADMIN)
                print("[OK] User role updated to admin")

            # Ensure user is active
            if not user.is_active:
                print("[INFO] Activating user...")
                repo.update_user(user, is_active=True)

            if user.email_verified_at is None:
                print("[INFO] Marking test admin email as verified...")
                repo.mark_email_verified(user)

            # Ensure settings exist
            SettingsRepository(db).ensure_default(user.id)
            print("[OK] Test admin user verified and ready")
            return user

        # Create test admin user
        print(f"[INFO] Creating test admin user: {test_admin_email}")
        repo = UserRepository(db)
        user = repo.create_user(
            email=test_admin_email,
            password=test_admin_password,
            name="Test Admin",
            role=UserRole.ADMIN,
        )
        repo.mark_email_verified(user)

        # Create default settings
        SettingsRepository(db).ensure_default(user.id)
        print(f"[OK] Test admin user created successfully: {test_admin_email} (ID: {user.id})")

        return user
    except Exception as e:
        print(f"[ERROR] Failed to ensure test admin user: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    ensure_test_admin()
