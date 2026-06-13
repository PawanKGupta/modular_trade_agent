#!/usr/bin/env python3
"""Audit users.password_hash for legacy plaintext or unknown formats."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from server.app.core.security import is_passlib_password_hash
from src.infrastructure.db.models import Users
from src.infrastructure.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def audit_password_hashes(*, remediate: bool = False) -> int:
    """
    List users whose password_hash is not a recognized passlib hash.

    Returns:
        Count of legacy rows found.
    """
    from server.app.core.auth_tokens import generate_token, hash_token, reset_expiry
    from src.infrastructure.persistence.user_repository import UserRepository

    legacy_count = 0
    with SessionLocal() as db:
        users = db.query(Users).filter(Users.deleted_at.is_(None)).all()
        for user in users:
            pwh = user.password_hash or ""
            if is_passlib_password_hash(pwh):
                continue
            legacy_count += 1
            logger.warning(
                "Legacy password storage user_id=%s email=%s hash_prefix=%s",
                user.id,
                user.email,
                pwh[:20] if pwh else "(empty)",
            )
            if remediate:
                token = generate_token()
                UserRepository(db).set_password_reset_token(
                    user, hash_token(token), reset_expiry()
                )
                logger.info(
                    "Queued password reset for user_id=%s (token not emailed by script)",
                    user.id,
                )
    return legacy_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit legacy password_hash values")
    parser.add_argument(
        "--remediate",
        action="store_true",
        help="Set password reset tokens for legacy rows (does not send email)",
    )
    args = parser.parse_args()
    count = audit_password_hashes(remediate=args.remediate)
    if count:
        logger.error("Found %s legacy password_hash row(s)", count)
        return 1
    logger.info("All password hashes look valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
