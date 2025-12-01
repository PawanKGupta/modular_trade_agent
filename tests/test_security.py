from server.app.core.security import hash_password, verify_password


def test_hash_and_verify_password_truncation_handling():
    long_pw = "x" * 200
    hashed = hash_password(long_pw)
    assert isinstance(hashed, str)
    assert verify_password(long_pw, hashed) is True
