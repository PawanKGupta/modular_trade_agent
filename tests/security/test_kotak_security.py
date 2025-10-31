import os
import json
from pathlib import Path
import tempfile
import shutil
import pytest

# Security tests for Kotak Neo auth/token handling

@pytest.mark.security
def test_kotak_env_credentials_not_leaked_in_logs(monkeypatch, caplog):
    # Ensure no pre-existing env interferes with dotenv loading
    for k in [
        "KOTAK_CONSUMER_KEY","KOTAK_CONSUMER_SECRET","KOTAK_MOBILE_NUMBER","KOTAK_PASSWORD",
        "KOTAK_TOTP_SECRET","KOTAK_MPIN","KOTAK_ENVIRONMENT"
    ]:
        monkeypatch.delenv(k, raising=False)

    # Prepare a temp .env with dummy secrets
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        env_path = tmp_dir / "kotak_neo.env"
        env_content = (
            "KOTAK_CONSUMER_KEY=ck_test\n"
            "KOTAK_CONSUMER_SECRET=cs_test\n"
            "KOTAK_MOBILE_NUMBER=9999999999\n"
            "KOTAK_PASSWORD=p@ssW0rd!\n"
            "KOTAK_TOTP_SECRET=totp_test\n"
            "KOTAK_ENVIRONMENT=sandbox\n"
            "KOTAK_MPIN=123456\n"
        )
        env_path.write_text(env_content, encoding="utf-8")

        # Import locally to avoid polluting global env
        from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

        caplog.set_level("INFO")
        auth = KotakNeoAuth(config_file=str(env_path))

        # Ensure secrets loaded
        assert auth.consumer_key == "ck_test"
        assert auth.consumer_secret == "cs_test"
        assert auth.password == "p@ssW0rd!"
        assert auth.mpin == "123456"

        # Ensure get_session_token is guarded
        assert auth.get_session_token() is None

        # Secrets should not appear in INFO logs
        assert "p@ssW0rd!" not in caplog.text
        assert "cs_test" not in caplog.text
        assert "totp_test" not in caplog.text

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.security
def test_kotak_session_cache_removed_in_v2_1():
    """
    Test that session caching has been removed in v2.1 continuous service.
    Session caching is no longer needed as the service maintains a single
    persistent session throughout its lifetime.
    """
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    
    # Verify session caching methods have been removed
    assert not hasattr(KotakNeoAuth, '_save_session_cache')
    assert not hasattr(KotakNeoAuth, '_try_use_cached_session')
    
    # Verify force_relogin still exists (needed for JWT expiry recovery)
    assert hasattr(KotakNeoAuth, 'force_relogin')


@pytest.mark.security
def test_kotak_missing_credentials_raises_valueerror(monkeypatch, tmp_path):
    # Ensure no pre-existing env interferes with dotenv loading
    for k in [
        "KOTAK_CONSUMER_KEY","KOTAK_CONSUMER_SECRET","KOTAK_MOBILE_NUMBER","KOTAK_PASSWORD",
        "KOTAK_TOTP_SECRET","KOTAK_MPIN","KOTAK_ENVIRONMENT"
    ]:
        monkeypatch.delenv(k, raising=False)

    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

    env_path = tmp_path / "kotak_neo.env"
    # Missing MPIN/TOTP should cause ValueError per implementation
    env_path.write_text(
        "\n".join([
            "KOTAK_CONSUMER_KEY=ck_test",
            "KOTAK_CONSUMER_SECRET=cs_test",
            "KOTAK_MOBILE_NUMBER=9999999999",
            "KOTAK_PASSWORD=p@ssW0rd!",
            # No TOTP or MPIN
        ]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        KotakNeoAuth(config_file=str(env_path))