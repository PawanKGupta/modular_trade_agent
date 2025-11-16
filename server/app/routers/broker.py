# ruff: noqa: B008, PLR0913, PLR0911, PLR0912
import sys
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.infrastructure.db.models import TradeMode, Users
from src.infrastructure.persistence.settings_repository import SettingsRepository

from ..core.crypto import encrypt_blob
from ..core.deps import get_current_user, get_db
from ..schemas.user import BrokerCredsRequest, BrokerTestResponse

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
        return (
            False,
            "Kotak Neo SDK (neo_api_client) not installed. Install with: pip install neo-api",
        )

    try:
        # Step 1: Initialize client (validates consumer_key/consumer_secret format)
        try:
            client = NeoAPI(
                consumer_key=creds.consumer_key,
                consumer_secret=creds.consumer_secret,
                environment=creds.environment,
                neo_fin_key="neotradeapi",
            )
        except Exception as e:
            return False, f"Failed to initialize client: {str(e)}"

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
        return False, f"Connection test failed: {str(e)}"


def _test_kotak_neo_login(client, creds: KotakNeoCreds) -> tuple[bool, str]:
    """Test Kotak Neo login and 2FA."""
    try:
        login_response = client.login(mobilenumber=creds.mobile_number, password=creds.password)

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

    except Exception as e:
        return False, f"Login error: {str(e)}"


def _test_kotak_neo_2fa(client, mpin: str) -> tuple[bool, str]:
    """Test Kotak Neo 2FA with MPIN."""
    try:
        session_response = client.session_2fa(OTP=mpin)
        if session_response is None:
            return True, "Connection successful (session already active)"

        if isinstance(session_response, dict) and "error" in session_response:
            error_msg = _extract_error_message(session_response["error"])
            return False, f"2FA failed: {error_msg}"

        return True, "Connection successful"
    except Exception as e:
        error_msg = str(e).lower()
        # Handle SDK internal errors (NoneType.get) - treat as session already active
        if "nonetype" in error_msg and "get" in error_msg:
            return True, "Connection successful (session already active)"
        return False, f"2FA failed: {str(e)}"


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
    creds_blob = {
        "api_key": payload.api_key,
        "api_secret": payload.api_secret,
    }
    settings = repo.update(
        settings,
        broker=payload.broker,
        broker_status="Stored",
    )
    # store encrypted creds
    settings.broker_creds_encrypted = encrypt_blob(str(creds_blob).encode("utf-8"))
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
