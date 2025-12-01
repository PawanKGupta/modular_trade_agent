"""
Broker Credentials Management

Utilities for loading and decrypting broker credentials from the database.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from server.app.core.crypto import decrypt_blob
from src.infrastructure.persistence.settings_repository import SettingsRepository


def decrypt_broker_credentials(
    broker_creds_encrypted: bytes | None,
) -> dict[str, Any] | None:
    """
    Decrypt broker credentials from encrypted blob.

    Args:
        broker_creds_encrypted: Encrypted credentials blob from UserSettings

    Returns:
        Decrypted credentials dict, or None if decryption fails
    """
    if not broker_creds_encrypted:
        return None

    try:
        decrypted = decrypt_blob(broker_creds_encrypted)
        if not decrypted:
            return None

        creds_str = decrypted.decode("utf-8")
        creds_dict = json.loads(creds_str)

        return creds_dict
    except Exception:
        return None


def load_broker_credentials(
    user_id: int, db_session, settings_repo: SettingsRepository | None = None
) -> dict[str, Any] | None:
    """
    Load and decrypt broker credentials for a user.

    Args:
        user_id: User ID
        db_session: Database session
        settings_repo: Optional SettingsRepository instance (will create if not provided)

    Returns:
        Decrypted credentials dict, or None if not found or decryption fails
    """
    if settings_repo is None:
        settings_repo = SettingsRepository(db_session)

    settings = settings_repo.get_by_user_id(user_id)
    if not settings or not settings.broker_creds_encrypted:
        return None

    return decrypt_broker_credentials(settings.broker_creds_encrypted)


def create_temp_env_file(creds_dict: dict[str, Any]) -> str:
    """
    Create a temporary .env file from credentials dict for KotakNeoAuth.

    Args:
        creds_dict: Credentials dictionary with keys:
            - api_key (maps to KOTAK_CONSUMER_KEY)
            - api_secret (maps to KOTAK_CONSUMER_SECRET)
            - mobile_number (maps to KOTAK_MOBILE_NUMBER)
            - password (maps to KOTAK_PASSWORD)
            - mpin (maps to KOTAK_MPIN)
            - totp_secret (maps to KOTAK_TOTP_SECRET)
            - environment (maps to KOTAK_ENVIRONMENT)

    Returns:
        Path to temporary .env file
    """
    # Map database keys to env var names
    env_mapping = {
        "api_key": "KOTAK_CONSUMER_KEY",
        "api_secret": "KOTAK_CONSUMER_SECRET",
        "mobile_number": "KOTAK_MOBILE_NUMBER",
        "password": "KOTAK_PASSWORD",
        "mpin": "KOTAK_MPIN",
        "totp_secret": "KOTAK_TOTP_SECRET",
        "environment": "KOTAK_ENVIRONMENT",
    }

    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".env", delete=False, prefix="kotak_neo_"
    )
    temp_path = temp_file.name

    try:
        # Write credentials to temp file
        for db_key, env_var in env_mapping.items():
            value = creds_dict.get(db_key)
            if value:
                temp_file.write(f"{env_var}={value}\n")

        temp_file.flush()
        temp_file.close()

        return temp_path
    except Exception:
        # Clean up on error
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception:
            pass
        raise


def convert_creds_to_env_format(creds_dict: dict[str, Any]) -> dict[str, str]:
    """
    Convert credentials dict from database format to env var format.

    Args:
        creds_dict: Credentials dict with database keys (api_key, api_secret, etc.)

    Returns:
        Dict with env var names as keys (KOTAK_CONSUMER_KEY, etc.)
    """
    mapping = {
        "api_key": "KOTAK_CONSUMER_KEY",
        "api_secret": "KOTAK_CONSUMER_SECRET",
        "mobile_number": "KOTAK_MOBILE_NUMBER",
        "password": "KOTAK_PASSWORD",
        "mpin": "KOTAK_MPIN",
        "totp_secret": "KOTAK_TOTP_SECRET",
        "environment": "KOTAK_ENVIRONMENT",
    }

    env_creds = {}
    for db_key, env_var in mapping.items():
        value = creds_dict.get(db_key)
        if value:
            env_creds[env_var] = str(value)

    return env_creds
