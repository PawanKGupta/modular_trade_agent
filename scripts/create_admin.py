#!/usr/bin/env python3
"""
Script to create or promote an admin user in the database.

Usage:
    python scripts/create_admin.py --email admin@example.com \\
        --password "StrongPassword123!" --name "Admin"

If the user already exists, they will be promoted to admin and activated.
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.db.models import UserRole  # noqa: E402
from src.infrastructure.db.session import SessionLocal  # noqa: E402
from src.infrastructure.persistence.user_repository import UserRepository  # noqa: E402


def create_or_promote_admin(email: str, password: str, name: str | None = None) -> None:
    """Create or promote a user to admin."""
    db = SessionLocal()
    try:
        repo = UserRepository(db)
        existing = repo.get_by_email(email)

        if existing:
            # User exists - promote to admin and activate
            existing.role = UserRole.ADMIN
            existing.is_active = True
            if name:
                existing.name = name
            # Update password if provided
            if password:
                repo.set_password(existing, password)
            db.commit()
            print(f"✅ User {email} promoted to admin and activated")
        else:
            # Create new admin user
            user = repo.create_user(
                email=email,
                password=password,
                name=name or "Admin",
                role=UserRole.ADMIN,
            )
            db.commit()
            print(f"✅ Admin user created: {email} (ID: {user.id})")
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Create or promote an admin user")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--name", help="Admin name (optional)")
    parser.add_argument(
        "--db-url",
        help="Database URL (optional, defaults to DB_URL env var or sqlite:///./data/app.db)",
    )

    args = parser.parse_args()

    # Override DB_URL if provided
    if args.db_url:
        os.environ["DB_URL"] = args.db_url

    create_or_promote_admin(args.email, args.password, args.name)


if __name__ == "__main__":
    main()
