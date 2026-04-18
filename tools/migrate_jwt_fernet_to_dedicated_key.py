#!/usr/bin/env python3
# ruff: noqa: PLC0415, PLR0912, PLR0915, E501
"""
Re-encrypt at-rest secrets that were encrypted with the JWT-derived Fernet key.

If BROKER_SECRET_KEY / APP_DATA_ENCRYPTION_KEY were never set, encrypt_blob() used
material derived from JWT_SECRET. Adding a dedicated key later would make those
rows unreadable. This script decrypts with that legacy path and re-encrypts with a
new dedicated Fernet key you choose.

Targets:
  - usersettings.broker_creds_encrypted (Kotak broker creds)
  - billing_admin_settings Razorpay encrypted columns (if present)

Prerequisites (environment):
  - DB_URL: database URL (same DB that holds the blobs).
  - JWT_SECRET: must match the value used when the old ciphertext was written.
  - MIGRATION_TARGET_FERNET_KEY: output of Fernet.generate_key().decode() (the key you
    will set as BROKER_SECRET_KEY or APP_DATA_ENCRYPTION_KEY in production after this).

This process temporarily removes APP_DATA_ENCRYPTION_KEY and BROKER_SECRET_KEY from
os.environ so decrypt_blob() uses the JWT-derived key for the read phase.

Usage:
  export DB_URL=postgresql://...
  export JWT_SECRET=your-existing-jwt-secret
  export MIGRATION_TARGET_FERNET_KEY='...paste Fernet key...'
  python tools/migrate_jwt_fernet_to_dedicated_key.py --dry-run
  python tools/migrate_jwt_fernet_to_dedicated_key.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _pop_dedicated_key_env() -> dict[str, str | None]:
    """Remove dedicated Fernet env vars so decrypt uses JWT-derived material."""
    saved: dict[str, str | None] = {}
    for name in ("APP_DATA_ENCRYPTION_KEY", "BROKER_SECRET_KEY"):
        saved[name] = os.environ.pop(name, None)
    return saved


def _restore_env(saved: dict[str, str | None]) -> None:
    for name, val in saved.items():
        if val is not None:
            os.environ[name] = val


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Decrypt and report only; do not write or require MIGRATION_TARGET_FERNET_KEY",
    )
    args = parser.parse_args()

    if not os.getenv("JWT_SECRET") and not os.getenv("jwt_secret"):
        print(
            "ERROR: Set JWT_SECRET (or jwt_secret) to match the environment that wrote the blobs.",
            file=sys.stderr,
        )
        return 1

    target_key = (os.getenv("MIGRATION_TARGET_FERNET_KEY") or "").strip()
    if not args.dry_run and not target_key:
        print(
            "ERROR: Set MIGRATION_TARGET_FERNET_KEY to the new Fernet key for re-encryption.",
            file=sys.stderr,
        )
        return 1

    if not args.dry_run:
        try:
            from cryptography.fernet import Fernet

            Fernet(target_key.encode("utf-8"))
        except Exception as e:
            print(
                f"ERROR: MIGRATION_TARGET_FERNET_KEY is not a valid Fernet key: {e}",
                file=sys.stderr,
            )
            return 1

    # Import after env checks so session picks up DB_URL
    from sqlalchemy import inspect

    from server.app.core.crypto import decrypt_blob, encrypt_blob
    from src.infrastructure.db.models import BillingAdminSettings, UserSettings
    from src.infrastructure.db.session import SessionLocal

    saved_keys = _pop_dedicated_key_env()
    try:
        session = SessionLocal()
        try:
            broker_updated = 0
            broker_skipped = 0
            rows = (
                session.query(UserSettings)
                .filter(UserSettings.broker_creds_encrypted.isnot(None))
                .all()
            )
            for row in rows:
                blob = row.broker_creds_encrypted
                if not blob:
                    continue
                plain = decrypt_blob(blob)
                if plain is None:
                    print(
                        f"WARN: user_id={row.user_id} broker_creds_encrypted could not decrypt (skip)"
                    )
                    broker_skipped += 1
                    continue
                if args.dry_run:
                    print(
                        f"DRY: user_id={row.user_id} broker blob decrypt OK ({len(plain)} bytes plaintext)"
                    )
                    broker_updated += 1
                    continue
                os.environ["BROKER_SECRET_KEY"] = target_key
                row.broker_creds_encrypted = encrypt_blob(plain)
                del os.environ["BROKER_SECRET_KEY"]
                broker_updated += 1

            rz_key_updated = 0
            rz_wh_updated = 0
            rz_skipped = 0
            inspector = inspect(session.bind)
            if "billing_admin_settings" in inspector.get_table_names():
                billing = session.get(BillingAdminSettings, 1)
                if billing:
                    if billing.razorpay_key_secret_encrypted:
                        plain = decrypt_blob(billing.razorpay_key_secret_encrypted)
                        if plain is None:
                            print(
                                "WARN: billing razorpay_key_secret_encrypted could not decrypt (skip)"
                            )
                            rz_skipped += 1
                        elif args.dry_run:
                            print(f"DRY: razorpay_key_secret decrypt OK ({len(plain)} bytes)")
                            rz_key_updated += 1
                        else:
                            os.environ["BROKER_SECRET_KEY"] = target_key
                            billing.razorpay_key_secret_encrypted = encrypt_blob(plain)
                            del os.environ["BROKER_SECRET_KEY"]
                            rz_key_updated += 1
                    if billing.razorpay_webhook_secret_encrypted:
                        plain = decrypt_blob(billing.razorpay_webhook_secret_encrypted)
                        if plain is None:
                            print(
                                "WARN: billing razorpay_webhook_secret_encrypted could not decrypt (skip)"
                            )
                            rz_skipped += 1
                        elif args.dry_run:
                            print(f"DRY: razorpay_webhook_secret decrypt OK ({len(plain)} bytes)")
                            rz_wh_updated += 1
                        else:
                            os.environ["BROKER_SECRET_KEY"] = target_key
                            billing.razorpay_webhook_secret_encrypted = encrypt_blob(plain)
                            del os.environ["BROKER_SECRET_KEY"]
                            rz_wh_updated += 1

            if args.dry_run:
                session.rollback()
                print(
                    f"Dry run complete: broker rows ok={broker_updated} skipped={broker_skipped}; "
                    f"razorpay key={rz_key_updated} webhook={rz_wh_updated} skipped={rz_skipped}"
                )
                return 0

            session.commit()
            print(
                f"Migrated: broker rows={broker_updated} skipped={broker_skipped}; "
                f"razorpay key={rz_key_updated} webhook={rz_wh_updated} skipped={rz_skipped}"
            )
            print(
                "Next: set BROKER_SECRET_KEY or APP_DATA_ENCRYPTION_KEY in production to the "
                "same value as MIGRATION_TARGET_FERNET_KEY, then restart the app."
            )
            if broker_skipped or rz_skipped:
                print(
                    "WARN: Some rows were skipped; fix JWT_SECRET or investigate before relying on DB.",
                    file=sys.stderr,
                )
                return 2
            return 0
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    finally:
        _restore_env(saved_keys)


if __name__ == "__main__":
    raise SystemExit(main())
