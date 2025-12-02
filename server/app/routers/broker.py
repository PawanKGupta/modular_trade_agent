# ruff: noqa: B008, PLR0913, PLR0911, PLR0912, PLC0415
import ast
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.infrastructure.db.models import TradeMode, Users
from src.infrastructure.persistence.settings_repository import SettingsRepository

from ..core.crypto import decrypt_blob, encrypt_blob
from ..core.deps import get_current_user, get_db
from ..schemas.user import BrokerCredsInfo, BrokerCredsRequest, BrokerTestResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Try to import NeoAPI at module level (may not be available in all environments)
try:
    # Add project root to path for imports
    _project_root = Path(__file__).parent.parent.parent.parent.parent
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    from neo_api_client import NeoAPI  # noqa: PLC0415

    _NEO_API_AVAILABLE = True
except ImportError:
    _NEO_API_AVAILABLE = False
    NeoAPI = None  # type: ignore[assignment, misc]


@dataclass
class KotakNeoCreds:
    """Kotak Neo credentials for connection testing."""

    consumer_key: str
    consumer_secret: str
    mobile_number: str | None = None
    password: str | None = None
    mpin: str | None = None
    totp_secret: str | None = None
    environment: str = "prod"


def _test_kotak_neo_connection(creds: KotakNeoCreds) -> tuple[bool, str]:
    """
    Test Kotak Neo broker connection using existing auth mechanism.

    Returns:
        tuple[bool, str]: (success, message)
    """
    if not _NEO_API_AVAILABLE:
        # Log technical details server-side for administrators
        import sys

        python_version = sys.version_info
        if python_version >= (3, 12):
            install_cmd = (
                "pip install --no-deps git+https://github.com/Kotak-Neo/kotak-neo-api@67143c58f29da9572cdbb273199852682a0019d5#egg=neo-api-client"
            )
            technical_details = (
                f"Kotak Neo SDK (neo_api_client) not installed on server.\n"
                f"Python version: {python_version.major}.{python_version.minor}\n"
                f"Install command: {install_cmd}\n"
                f"Note: Using --no-deps to avoid numpy version conflicts.\n"
                f"See docker/INSTALL_KOTAK_SDK.md for detailed instructions."
            )
        else:
            install_cmd = (
                "pip install git+https://github.com/Kotak-Neo/kotak-neo-api@67143c58f29da9572cdbb273199852682a0019d5#egg=neo-api-client"
            )
            technical_details = (
                f"Kotak Neo SDK (neo_api_client) not installed on server.\n"
                f"Python version: {python_version.major}.{python_version.minor}\n"
                f"Install command: {install_cmd}\n"
                f"See docker/INSTALL_KOTAK_SDK.md for detailed instructions."
            )

        # Log technical details server-side (for administrators)
        logger.error(
            f"Kotak Neo SDK not available on server: {technical_details}",
            extra={"action": "test_broker_connection"},
        )

        # Return user-friendly error message (no installation instructions)
        user_message = (
            "Kotak Neo broker integration is not available on this server. "
            "Please contact your system administrator to install the required dependencies."
        )
        return (False, user_message)

    try:
        # Step 1: Initialize client (validates consumer_key/consumer_secret format)
        try:
            # Ensure all required parameters are strings, not None
            consumer_key = str(creds.consumer_key).strip() if creds.consumer_key else ""
            consumer_secret = str(creds.consumer_secret).strip() if creds.consumer_secret else ""
            environment = str(creds.environment).strip() if creds.environment else "prod"

            if not consumer_key or not consumer_secret:
                return False, "Consumer key and secret cannot be empty"

            client = NeoAPI(
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
                environment=environment,
                neo_fin_key="neotradeapi",
            )

            # Validate client was created successfully
            if client is None:
                return False, "Failed to create client: SDK returned None"

        except TypeError as te:
            error_msg = str(te) if te else "Type error"
            if "NoneType" in error_msg or "concatenate" in error_msg.lower():
                return (
                    False,
                    "SDK initialization error: Invalid consumer_key or consumer_secret format. "
                    "Please check your credentials.",
                )
            return False, f"SDK type error during initialization: {error_msg}"
        except Exception as e:
            error_str = str(e) if e is not None else "Unknown error"
            return False, f"Failed to initialize client: {error_str}"

        # Step 2: If full credentials provided, test login
        has_full_creds = (
            creds.mobile_number and creds.password and (creds.mpin or creds.totp_secret)
        )
        if not has_full_creds:
            msg = (
                "Client initialized successfully "
                "(full login test requires mobile, password, and MPIN)"
            )
            return True, msg

        # Full login test
        return _test_kotak_neo_login(client, creds)

    except Exception as e:
        error_str = str(e) if e is not None else "Unknown error"
        return False, f"Connection test failed: {error_str}"


def _test_kotak_neo_login(client, creds: KotakNeoCreds) -> tuple[bool, str]:
    """Test Kotak Neo login and 2FA."""
    try:
        # Validate credentials are not None or empty
        if not creds.mobile_number or not creds.password:
            return False, "Mobile number and password are required for login"

        mobile = str(creds.mobile_number).strip()
        password = str(creds.password).strip()

        if not mobile or not password:
            return False, "Mobile number and password cannot be empty"

        # Call login with explicit string conversion to avoid SDK internal None concatenation
        try:
            login_response = client.login(mobilenumber=mobile, password=password)
        except TypeError as te:
            # SDK might be trying to concatenate None with string internally
            error_msg = str(te) if te else "Type error in SDK"
            if "NoneType" in error_msg or "concatenate" in error_msg.lower():
                return (
                    False,
                    "SDK error: Invalid client state. "
                    "Ensure consumer_key and consumer_secret are valid "
                    "and client is properly initialized.",
                )
            return False, f"SDK type error: {error_msg}"
        except AttributeError as ae:
            # SDK might be missing required attributes
            error_msg = str(ae) if ae else "Attribute error in SDK"
            return (
                False,
                f"SDK attribute error: {error_msg}. Client may not be properly initialized.",
            )

        if login_response is None:
            return False, "Login failed: No response from server"

        if isinstance(login_response, dict) and "error" in login_response:
            error_msg = _extract_error_message(login_response["error"])
            return False, f"Login failed: {error_msg}"

        # Test 2FA (prefer MPIN over TOTP)
        if creds.mpin:
            return _test_kotak_neo_2fa(client, creds.mpin)
        if creds.totp_secret:
            return True, "Login successful (2FA with TOTP not fully tested)"

        return False, "2FA credentials (MPIN or TOTP) required"

    except TypeError as te:
        # Catch TypeError specifically (the "can only concatenate str" error)
        error_msg = str(te) if te else "Type error"
        if "NoneType" in error_msg or "concatenate" in error_msg.lower():
            return (
                False,
                "SDK internal error: Invalid client configuration. "
                "Please verify your consumer_key and consumer_secret are correct.",
            )
        return False, f"Type error: {error_msg}"
    except Exception as e:
        error_str = str(e) if e is not None else "Unknown error"
        return False, f"Login error: {error_str}"


def _test_kotak_neo_2fa(client, mpin: str) -> tuple[bool, str]:
    """Test Kotak Neo 2FA with MPIN."""
    try:
        if not mpin or not mpin.strip():
            return False, "MPIN is required for 2FA"

        mpin_str = str(mpin).strip()
        session_response = client.session_2fa(OTP=mpin_str)
        if session_response is None:
            return True, "Connection successful (session already active)"

        if isinstance(session_response, dict) and "error" in session_response:
            error_msg = _extract_error_message(session_response["error"])
            return False, f"2FA failed: {error_msg}"

        return True, "Connection successful"
    except Exception as e:
        error_str = str(e) if e is not None else "Unknown error"
        error_msg = error_str.lower()
        # Handle SDK internal errors (NoneType.get) - treat as session already active
        if "nonetype" in error_msg and "get" in error_msg:
            return True, "Connection successful (session already active)"
        return False, f"2FA failed: {error_str}"


def _extract_error_message(error: dict | list | str) -> str:
    """Extract error message from Kotak Neo API response."""
    if isinstance(error, list) and len(error) > 0:
        if isinstance(error[0], dict):
            return error[0].get("message", str(error[0]))
        return str(error[0])
    return str(error)


@router.post("/creds", response_model=dict)
def save_broker_creds(
    payload: BrokerCredsRequest,
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> dict[str, str]:
    repo = SettingsRepository(db)
    settings = repo.ensure_default(current.id)

    # Store all credentials (basic + full auth if provided)
    creds_blob = {
        "api_key": payload.api_key,
        "api_secret": payload.api_secret,
    }
    # Add full auth credentials if provided
    if payload.mobile_number:
        creds_blob["mobile_number"] = payload.mobile_number
    if payload.password:
        creds_blob["password"] = payload.password
    if payload.mpin:
        creds_blob["mpin"] = payload.mpin
    if payload.totp_secret:
        creds_blob["totp_secret"] = payload.totp_secret
    if payload.environment:
        creds_blob["environment"] = payload.environment

    settings = repo.update(
        settings,
        broker=payload.broker,
        broker_status="Stored",
    )
    # store encrypted creds
    settings.broker_creds_encrypted = encrypt_blob(json.dumps(creds_blob).encode("utf-8"))
    db.commit()
    return {"status": "ok"}


@router.post("/test", response_model=BrokerTestResponse)
def test_broker_connection(
    payload: BrokerCredsRequest,
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> BrokerTestResponse:
    """
    Test broker connection with provided credentials.

    For Kotak Neo:
    - Minimum: consumer_key and consumer_secret (validates client initialization)
    - Full test: Also provide mobile_number, password, and mpin/totp_secret (tests actual login)
    """
    if payload.broker != "kotak-neo":
        return BrokerTestResponse(ok=False, message=f"Unsupported broker: {payload.broker}")

    # Basic validation
    api_key = (payload.api_key or "").strip()
    api_secret = (payload.api_secret or "").strip()

    if not api_key or not api_secret:
        return BrokerTestResponse(ok=False, message="API key and secret are required")

    # Test connection using existing Kotak Neo auth mechanism
    creds = KotakNeoCreds(
        consumer_key=api_key,
        consumer_secret=api_secret,
        mobile_number=payload.mobile_number,
        password=payload.password,
        mpin=payload.mpin,
        totp_secret=payload.totp_secret,
        environment=payload.environment or "prod",
    )
    success, message = _test_kotak_neo_connection(creds)

    # Update settings if connection successful
    if success:
        repo = SettingsRepository(db)
        settings = repo.ensure_default(current.id)
        settings = repo.update(
            settings,
            trade_mode=TradeMode.BROKER,
            broker=payload.broker,
            broker_status="Connected",
        )
        db.commit()

    return BrokerTestResponse(ok=success, message=message)


@router.get("/status", response_model=dict)
def broker_status(
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> dict[str, str | None]:
    repo = SettingsRepository(db)
    settings = repo.ensure_default(current.id)
    return {"broker": settings.broker, "status": settings.broker_status}


@router.get("/creds/info", response_model=BrokerCredsInfo)
def get_broker_creds_info(
    show_full: Annotated[bool, Query(description="Show full credentials (not masked)")] = False,
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> BrokerCredsInfo:
    """
    Get information about stored broker credentials.
    By default returns masked versions. Set show_full=true to get full values.
    """

    repo = SettingsRepository(db)
    settings = repo.ensure_default(current.id)

    if not settings.broker_creds_encrypted:
        return BrokerCredsInfo(has_creds=False)

    # Decrypt and extract info
    try:
        decrypted = decrypt_blob(settings.broker_creds_encrypted)
        if not decrypted:
            return BrokerCredsInfo(has_creds=False)

        # Parse the stored credentials (stored as JSON)
        creds_str = decrypted.decode("utf-8")
        try:
            creds_dict = json.loads(creds_str)
        except json.JSONDecodeError:
            # Fallback to ast.literal_eval for old format
            if creds_str.startswith("{"):
                creds_dict = ast.literal_eval(creds_str)
            else:
                return BrokerCredsInfo(has_creds=False)

        api_key = creds_dict.get("api_key", "")
        api_secret = creds_dict.get("api_secret", "")

        # Mask credentials: show last 4 characters
        MASK_LENGTH = 4

        def mask_value(value: str) -> str:
            if not value or len(value) < MASK_LENGTH:
                return "****"
            return "****" + value[-MASK_LENGTH:]

        # Return full or masked based on query param
        if show_full:
            return BrokerCredsInfo(
                has_creds=True,
                api_key=api_key if api_key else None,
                api_secret=api_secret if api_secret else None,
                mobile_number=creds_dict.get("mobile_number"),
                password=creds_dict.get("password"),
                mpin=creds_dict.get("mpin"),
                totp_secret=creds_dict.get("totp_secret"),
                environment=creds_dict.get("environment", "prod"),
            )
        else:
            return BrokerCredsInfo(
                has_creds=True,
                api_key_masked=mask_value(api_key) if api_key else None,
                api_secret_masked=mask_value(api_secret) if api_secret else None,
            )
    except Exception:
        # If decryption fails, assume no valid creds
        return BrokerCredsInfo(has_creds=False)
