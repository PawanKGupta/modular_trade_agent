"""Tests for online vs offline billing payment mode helpers."""

from src.application.services.billing_payment_modes import (
    OFFLINE_PAYMENTS_DISABLED_DETAIL,
    offline_payment_info,
    online_payments_enabled,
)
from src.infrastructure.persistence.billing_repository import BillingRepository


def test_online_payments_default_false(db_session):
    s = BillingRepository(db_session).get_admin_settings()
    assert online_payments_enabled(s) is False
    info = offline_payment_info(s)
    assert info["offline_upi_id"] == "8565859556@apl"


def test_offline_payment_info_payload(db_session):
    repo = BillingRepository(db_session)
    s = repo.update_admin_settings(
        online_payments_enabled=False,
        offline_payment_upi_id="merchant@paytm",
        offline_payment_instructions="Include bill # in note",
        offline_payment_qr_image_url="https://example.com/qr.png",
    )
    info = offline_payment_info(s)
    assert info["online_payments_enabled"] is False
    assert info["offline_upi_id"] == "merchant@paytm"
    assert "bill #" in (info["offline_instructions"] or "")
    assert info["offline_qr_image_url"] == "https://example.com/qr.png"


def test_online_enabled_after_admin_patch(db_session):
    s = BillingRepository(db_session).update_admin_settings(online_payments_enabled=True)
    assert online_payments_enabled(s) is True
    assert OFFLINE_PAYMENTS_DISABLED_DETAIL
