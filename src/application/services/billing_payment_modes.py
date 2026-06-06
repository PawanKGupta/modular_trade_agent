"""Online vs offline performance-fee payment configuration (admin-controlled)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.application.services.billing_offline_qr_storage import offline_payment_qr_uploaded
from src.infrastructure.db.models import BillingAdminSettings
from src.infrastructure.persistence.billing_repository import BillingRepository

# User-facing HTTP detail when Razorpay checkout endpoints are disabled.
ONLINE_CHECKOUT_DISABLED_MESSAGE = (
    "Online checkout is off. Pay via the UPI/QR below, then tell us when paid."
)


def online_payments_enabled(settings: BillingAdminSettings) -> bool:
    return bool(settings.online_payments_enabled)


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def admin_offline_payment_settings(settings: BillingAdminSettings) -> dict[str, str | bool | None]:
    """Admin API / UI: raw DB field names (offline_payment_*)."""
    qr_uploaded = offline_payment_qr_uploaded()
    return {
        "online_payments_enabled": online_payments_enabled(settings),
        "offline_payment_upi_id": _strip_or_none(settings.offline_payment_upi_id),
        "offline_payment_instructions": _strip_or_none(settings.offline_payment_instructions),
        "offline_payment_qr_image_url": _strip_or_none(settings.offline_payment_qr_image_url),
        "offline_payment_qr_uploaded": qr_uploaded,
    }


def offline_payment_info(settings: BillingAdminSettings) -> dict[str, str | bool | None]:
    """User billing page: public fields with user-facing key names (offline_*)."""
    admin = admin_offline_payment_settings(settings)
    qr_uploaded = bool(admin["offline_payment_qr_uploaded"])
    external_qr_url = admin["offline_payment_qr_image_url"] if not qr_uploaded else None
    return {
        "online_payments_enabled": admin["online_payments_enabled"],
        "offline_upi_id": admin["offline_payment_upi_id"],
        "offline_instructions": admin["offline_payment_instructions"],
        "offline_qr_uploaded": qr_uploaded,
        "offline_qr_image_url": external_qr_url,
    }


def get_admin_settings(db: Session) -> BillingAdminSettings:
    return BillingRepository(db).get_admin_settings()
