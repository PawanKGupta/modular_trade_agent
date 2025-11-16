#!/usr/bin/env python
"""
One-off script to create an admin user.

Usage (PowerShell):
  .\.venv\Scripts\python.exe scripts\create_admin.py `
    --email admin@example.com `
    --password "StrongPassword123!" `
    --name "Admin"

Environment:
  - DB_URL may be set to point at the desired database (default from app config/session)
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.infrastructure.db.base import Base  # noqa: E402
from src.infrastructure.db.models import UserRole, Users  # noqa: E402
from src.infrastructure.db.session import SessionLocal, engine  # noqa: E402
from src.infrastructure.persistence.user_repository import UserRepository  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an admin user.")
    parser.add_argument("--email", required=True, help="Admin email")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--name", default=None, help="Admin name (optional)")
    args = parser.parse_args()

    # Ensure tables exist
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[create_admin] Failed to ensure tables: {e}")
        return 2

    with SessionLocal() as db:
        # If already exists, just promote to admin and ensure active
        existing = db.query(Users).filter(Users.email == args.email).first()
        repo = UserRepository(db)
        if existing:
            if existing.role != UserRole.ADMIN or existing.is_active is False:
                repo.update_user(
                    existing,
                    role=UserRole.ADMIN,
                    name=args.name if args.name else existing.name,
                    is_active=True,
                )
                print(f"[create_admin] Updated existing user to admin: {args.email}")
            else:
                print(f"[create_admin] User already admin: {args.email}")
            return 0

        repo.create_user(
            email=args.email,
            password=args.password,
            name=args.name,
            role=UserRole.ADMIN,
        )
        print(f"[create_admin] Created admin user: {args.email}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
