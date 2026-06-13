#!/usr/bin/env python3
"""Audit users.password_hash for legacy plaintext or unknown formats.

Run from the project virtualenv (dependencies are not on system python3):

    .venv/bin/python tools/audit_password_hashes.py

Docker production:

    docker exec tradeagent-api python /app/tools/audit_password_hashes.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_PASSLIB_HASH_PREFIXES = (
    "$pbkdf2-sha256$",
    "$2a$",
    "$2b$",
    "$2y$",
    "$bcrypt-sha256$",
)


def is_passlib_password_hash(value: str) -> bool:
    """True when stored value looks like a passlib/bcrypt hash."""
    if not value:
        return False
    return any(value.startswith(p) for p in _PASSLIB_HASH_PREFIXES)


def _load_user_password_rows():
    """Load user id/email/password_hash without requiring the full ORM schema."""
    try:
        from sqlalchemy import text

        from src.infrastructure.db.session import SessionLocal
    except ImportError as exc:
        logger.error(
            "Missing Python dependencies (%s). Use: .venv/bin/python tools/audit_password_hashes.py",
            exc,
        )
        raise SystemExit(2) from exc

    with SessionLocal() as db:
        rows = db.execute(
            text("SELECT id, email, password_hash FROM users ORDER BY id")
        ).fetchall()
    return rows


def audit_password_hashes(*, remediate: bool = False) -> int:
    """
    List users whose password_hash is not a recognized passlib hash.

    Returns:
        Count of legacy rows found.
    """
    legacy_ids: list[tuple[int, str, str]] = []
    for row in _load_user_password_rows():
        user_id, email, pwh = row[0], row[1], row[2] or ""
        if is_passlib_password_hash(pwh):
            continue
        legacy_ids.append((user_id, email, pwh))
        logger.warning(
            "Legacy password storage user_id=%s email=%s hash_prefix=%s",
            user_id,
            email,
            pwh[:20] if pwh else "(empty)",
        )

    if remediate and legacy_ids:
        from server.app.core.auth_tokens import generate_token, hash_token, reset_expiry
        from src.infrastructure.db.models import Users
        from src.infrastructure.db.session import SessionLocal
        from src.infrastructure.persistence.user_repository import UserRepository

        with SessionLocal() as db:
            for user_id, _email, _pwh in legacy_ids:
                user = db.get(Users, user_id)
                if user is None:
                    continue
                token = generate_token()
                UserRepository(db).set_password_reset_token(
                    user, hash_token(token), reset_expiry()
                )
                logger.info(
                    "Queued password reset for user_id=%s (token not emailed by script)",
                    user_id,
                )

    return len(legacy_ids)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit legacy password_hash values")
    parser.add_argument(
        "--remediate",
        action="store_true",
        help="Set password reset tokens for legacy rows (does not send email)",
    )
    args = parser.parse_args()
    try:
        count = audit_password_hashes(remediate=args.remediate)
    except Exception as exc:
        logger.error("Audit failed: %s", exc)
        return 2
    if count:
        logger.error("Found %s legacy password_hash row(s)", count)
        return 1
    logger.info("All password hashes look valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
