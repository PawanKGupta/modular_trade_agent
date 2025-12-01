#!/usr/bin/env python3
"""
Ensure test admin user exists in e2e database
This script checks if the test admin user exists, and creates it if it doesn't
"""

import os
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


def ensure_test_admin():
    """Ensure test admin user exists"""
    # Ensure schema exists
    Base.metadata.create_all(bind=engine)

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
            if user.role != UserRole.ADMIN:
                print("[INFO] Updating user role to admin...")
                repo = UserRepository(db)
                repo.update_user(user, role=UserRole.ADMIN)
                print("[OK] User role updated to admin")

            # Ensure user is active
            if not user.is_active:
                print("[INFO] Activating user...")
                repo = UserRepository(db)
                repo.update_user(user, is_active=True)

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
