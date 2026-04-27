from src.infrastructure.payments.razorpay_gateway import verify_webhook_signature


def test_verify_webhook_signature_roundtrip():
    body = b'{"event":"payment.captured"}'
    secret = "whsec_test"
    import hashlib
    import hmac

    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, expected, secret) is True
    assert verify_webhook_signature(body, "bad", secret) is False
