"""Resolve Razorpay API + webhook credentials from env (override) or encrypted DB columns."""

from __future__ import annotations

from sqlalchemy.orm import Session

from server.app.core.config import settings
from server.app.core.crypto import decrypt_blob
from src.infrastructure.db.models import BillingAdminSettings
from src.infrastructure.payments.razorpay_gateway import RazorpayGateway
from src.infrastructure.persistence.billing_repository import BillingRepository


def _decrypt_utf8(blob: bytes | None) -> str | None:
    if not blob:
        return None
    plain = decrypt_blob(blob)
    if plain is None:
        return None
    s = plain.decode("utf-8").strip()
    return s or None


def resolve_razorpay_key_id(admin_row: BillingAdminSettings) -> str | None:
    """Non-secret key id: env wins, else DB column (unless razorpay_use_db_only)."""
    if not settings.razorpay_use_db_only:
        env = (settings.razorpay_key_id or "").strip()
        if env:
            return env
    dbv = (admin_row.razorpay_key_id or "").strip()
    return dbv or None


def resolve_razorpay_key_secret(admin_row: BillingAdminSettings) -> str | None:
    """API secret: env wins, else decrypted DB blob (unless razorpay_use_db_only)."""
    if not settings.razorpay_use_db_only:
        env = (settings.razorpay_key_secret or "").strip()
        if env:
            return env
    return _decrypt_utf8(admin_row.razorpay_key_secret_encrypted)


def resolve_razorpay_webhook_secret(admin_row: BillingAdminSettings) -> str | None:
    if not settings.razorpay_use_db_only:
        env = (settings.razorpay_webhook_secret or "").strip()
        if env:
            return env
    return _decrypt_utf8(admin_row.razorpay_webhook_secret_encrypted)


def get_razorpay_gateway(db: Session) -> RazorpayGateway:
    admin = BillingRepository(db).get_admin_settings()
    return RazorpayGateway(
        resolve_razorpay_key_id(admin),
        resolve_razorpay_key_secret(admin),
    )


def resolve_razorpay_webhook_secret_from_db(db: Session) -> str | None:
    admin = BillingRepository(db).get_admin_settings()
    return resolve_razorpay_webhook_secret(admin)


def razorpay_admin_meta(admin_row: BillingAdminSettings) -> dict[str, bool | str | None]:
    """Safe fields for GET /admin/billing/settings (no secrets)."""
    key_id = resolve_razorpay_key_id(admin_row)
    preview: str | None = None
    if key_id:
        preview = key_id if len(key_id) <= 12 else f"{key_id[:8]}…{key_id[-4:]}"  # noqa: PLR2004
    return {
        "razorpay_key_id_preview": preview,
        "razorpay_api_configured": bool(key_id and resolve_razorpay_key_secret(admin_row)),
        "razorpay_webhook_configured": bool(resolve_razorpay_webhook_secret(admin_row)),
        "razorpay_use_db_only": settings.razorpay_use_db_only,
        "razorpay_key_secret_from_env": bool(
            (not settings.razorpay_use_db_only) and (settings.razorpay_key_secret or "").strip()
        ),
        "razorpay_webhook_secret_from_env": bool(
            (not settings.razorpay_use_db_only) and (settings.razorpay_webhook_secret or "").strip()
        ),
        "razorpay_key_secret_stored_in_db": bool(admin_row.razorpay_key_secret_encrypted),
        "razorpay_webhook_secret_stored_in_db": bool(admin_row.razorpay_webhook_secret_encrypted),
    }
