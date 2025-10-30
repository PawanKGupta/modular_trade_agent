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
def test_kotak_session_cache_does_not_store_credentials(tmp_path):
    # Create instance and simulate a token then persist cache
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth

    env_path = tmp_path / "kotak_neo.env"
    env_path.write_text(
        "\n".join([
            "KOTAK_CONSUMER_KEY=ck_test",
            "KOTAK_CONSUMER_SECRET=cs_test",
            "KOTAK_MOBILE_NUMBER=9999999999",
            "KOTAK_PASSWORD=p@ssW0rd!",
            "KOTAK_TOTP_SECRET=totp_test",
            "KOTAK_MPIN=123456",
            "KOTAK_ENVIRONMENT=prod",
        ]),
        encoding="utf-8",
    )

    auth = KotakNeoAuth(config_file=str(env_path))
    # Set a fake token and save cache
    auth.session_token = "fake_session_token"
    auth._save_session_cache()  # writes modules/kotak_neo_auto_trader/session_cache.json

    cache_file = Path(__file__).resolve().parents[2] / "modules" / "kotak_neo_auto_trader" / "session_cache.json"
    assert cache_file.exists()

    cache = json.loads(cache_file.read_text(encoding="utf-8"))
    # Expected keys only; no password or secrets
    assert "session_token" in cache
    assert "created_at" in cache
    assert "expires_at" in cache
    assert "environment" in cache
    assert "mobile" in cache

    forbidden = {"password", "consumer_secret", "totp", "mpin"}
    assert not (forbidden & set(map(str.lower, cache.keys())))


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