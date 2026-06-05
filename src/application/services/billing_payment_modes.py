"""Online vs offline performance-fee payment configuration (admin-controlled)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.infrastructure.db.models import BillingAdminSettings
from src.infrastructure.persistence.billing_repository import BillingRepository

DEFAULT_OFFLINE_UPI_ID = "8565859556@apl"
DEFAULT_OFFLINE_INSTRUCTIONS = "Pay exact amount; add bill # and email in UPI note."

OFFLINE_PAYMENTS_DISABLED_DETAIL = (
    "Online checkout is off. Pay via the UPI/QR below, then tell us when paid."
)


def online_payments_enabled(settings: BillingAdminSettings) -> bool:
    return bool(settings.online_payments_enabled)


def offline_payment_info(settings: BillingAdminSettings) -> dict[str, str | bool | None]:
    """Public fields for the user billing page (no secrets)."""
    upi = (settings.offline_payment_upi_id or "").strip() or DEFAULT_OFFLINE_UPI_ID
    instructions = (settings.offline_payment_instructions or "").strip() or DEFAULT_OFFLINE_INSTRUCTIONS
    qr_url = (settings.offline_payment_qr_image_url or "").strip()
    return {
        "online_payments_enabled": online_payments_enabled(settings),
        "offline_upi_id": upi or None,
        "offline_instructions": instructions or None,
        "offline_qr_image_url": qr_url or None,
    }


def get_admin_settings(db: Session) -> BillingAdminSettings:
    return BillingRepository(db).get_admin_settings()
