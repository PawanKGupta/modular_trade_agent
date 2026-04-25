import hashlib
import hmac

from src.infrastructure.payments.razorpay_gateway import verify_checkout_payment_signature


def test_verify_checkout_signature_matches_razorpay_algorithm():
    secret = "test_secret_123"
    order_id = "order_test_1"
    payment_id = "pay_test_1"
    expected = hmac.new(
        secret.encode("utf-8"), f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()
    assert (
        verify_checkout_payment_signature(order_id, payment_id, expected, key_secret=secret) is True
    )
    assert (
        verify_checkout_payment_signature(order_id, payment_id, "0" * 64, key_secret=secret)
        is False
    )


def test_rejects_tampered_order_id():
    secret = "s"
    assert verify_checkout_payment_signature("order1", "pay1", "abc", key_secret=secret) is False
