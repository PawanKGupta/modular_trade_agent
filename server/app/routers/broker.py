# ruff: noqa: B008, PLR0913, PLR0911, PLR0912, PLC0415
import ast
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.application.services.broker_credentials import (
    create_temp_env_file,
    decrypt_broker_credentials,
)
from src.infrastructure.db.models import Orders, TradeMode, Users
from src.infrastructure.persistence.settings_repository import SettingsRepository

from ..core.crypto import decrypt_blob, encrypt_blob
from ..core.deps import get_current_user, get_db
from ..routers.paper_trading import (
    ClosedPosition,
    PaperTradingAccount,
    PaperTradingHolding,
    PaperTradingPortfolio,
    PaperTradingTransaction,
    TradeHistory,
    _upsert_pnl_from_closed_positions,
)
from ..schemas.user import BrokerCredsInfo, BrokerCredsRequest, BrokerTestResponse
from .broker_history_impl import _fifo_match_orders

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_or_create_auth_session(
    user_id: int, temp_env_file: str, db: Session, force_new: bool = False
) -> object:
    """
    Get or create shared authenticated broker session for a user.

    Uses shared session manager to ensure ONE client object per user
    is used by all services (unified service, web API, individual services).
    When session expires, it's recreated once and everyone uses the new one.

    Args:
        user_id: User ID
        temp_env_file: Path to temporary env file with broker credentials
        db: Database session (unused, kept for compatibility)
        force_new: If True, force creation of new session (clears existing)

    Returns:
        Authenticated KotakNeoAuth instance
    """
    from modules.kotak_neo_auto_trader.shared_session_manager import (
        get_shared_session_manager,
    )

    session_manager = get_shared_session_manager()
    logger.debug(f"[SHARED_SESSION] Requesting session for user {user_id} (force_new={force_new})")
    auth = session_manager.get_or_create_session(user_id, temp_env_file, force_new=force_new)

    if auth:
        is_auth = auth.is_authenticated()
        client = auth.get_client()
        logger.info(
            f"[SHARED_SESSION] Broker API session for user {user_id}: "
            f"force_new={force_new}, is_authenticated={is_auth}, "
            f"client={'available' if client else 'None'}"
        )
    else:
        logger.error(
            f"[SHARED_SESSION] Failed to get/create session for user {user_id} "
            f"(force_new={force_new})"
        )

    if not auth:
        raise HTTPException(
            status_code=503,
            detail=("Failed to connect to broker. Please check your credentials and try again."),
        )

    return auth


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
    Test Kotak Neo broker connection using REST authentication APIs.

    Returns:
        tuple[bool, str]: (success, message)
    """
    # Map existing fields to new REST API expectations:
    # - api_key/consumer_key -> Authorization header
    # - api_secret/consumer_secret -> UCC (client code)
    api_key = str(creds.consumer_key).strip() if creds.consumer_key else ""
    ucc = str(creds.consumer_secret).strip() if creds.consumer_secret else ""

    if not api_key or not ucc:
        return False, "API key and UCC (api_secret) cannot be empty"

    # If only basic keys are provided, just validate presence/format (no network call),
    # matching previous behavior where we only initialized the SDK client.
    has_full_creds = bool(creds.mobile_number and (creds.mpin or creds.totp_secret))
    if not has_full_creds:
        msg = (
            "API key and UCC validated locally "
            "(full login test requires mobile number and MPIN or TOTP secret)"
        )
        return True, msg

    try:
        # Step 1: tradeApiLogin (view token) using mobileNumber + UCC + TOTP
        if creds.totp_secret:
            try:
                import pyotp  # type: ignore[import]

                totp = pyotp.TOTP(creds.totp_secret.strip()).now()
            except ImportError:
                return (
                    False,
                    "TOTP secret provided but pyotp is not installed on the server. "
                    "Install pyotp or use MPIN-only flows.",
                )
        else:
            return False, "TOTP secret is required for REST login test"

        url_login = "https://mis.kotaksecurities.com/login/1.0/tradeApiLogin"
        headers_login = {
            "Authorization": api_key,
            "neo-fin-key": "neotradeapi",
            "Content-Type": "application/json",
        }
        payload_login = {
            "mobileNumber": str(creds.mobile_number).strip(),
            "ucc": ucc,
            "totp": totp,
        }

        resp_login = requests.post(
            url_login,
            headers=headers_login,
            data=json.dumps(payload_login),
            timeout=10.0,
        )
        data_login = resp_login.json()
        if resp_login.status_code != 200 or data_login.get("status") == "error":
            msg = data_login.get("message") or "Login failed (Step 1)"
            return False, f"Login failed: {msg}"

        view_data = data_login.get("data") or {}
        view_sid = view_data.get("sid")
        view_token = view_data.get("token")
        if not view_sid or not view_token:
            return False, "Login failed: missing sid/token in Step 1 response"

        # Step 2: tradeApiValidate (MPIN -> trade token + baseUrl)
        if not creds.mpin:
            return False, "MPIN is required for full REST login test"

        url_validate = "https://mis.kotaksecurities.com/login/1.0/tradeApiValidate"
        headers_validate = {
            "Authorization": api_key,
            "neo-fin-key": "neotradeapi",
            "Content-Type": "application/json",
            "sid": view_sid,
            "Auth": view_token,
        }
        payload_validate = {"mpin": str(creds.mpin).strip()}

        resp_validate = requests.post(
            url_validate,
            headers=headers_validate,
            data=json.dumps(payload_validate),
            timeout=10.0,
        )
        data_validate = resp_validate.json()
        if resp_validate.status_code != 200 or data_validate.get("status") == "error":
            msg = data_validate.get("message") or "Login failed (Step 2)"
            return False, f"MPIN validation failed: {msg}"

        trade_data = data_validate.get("data") or {}
        base_url = trade_data.get("baseUrl")
        trade_token = trade_data.get("token")
        if not base_url or not trade_token:
            return False, "MPIN validation failed: missing baseUrl/token"

        # Optional: lightweight sanity check using a simple GET with Authorization only,
        # similar to the tested example (script-details endpoint).
        try:
            test_url = f"{base_url.rstrip('/')}/script-details/1.0/masterscrip/file-paths"
            resp_test = requests.get(
                test_url,
                headers={"Authorization": api_key},
                timeout=10.0,
            )
            if resp_test.status_code != 200:
                logger.warning(
                    "REST auth succeeded but script-details sanity check returned HTTP %s",
                    resp_test.status_code,
                )
        except Exception as test_err:  # noqa: BLE001
            # Do not fail the whole test on this; main login already passed.
            logger.warning(
                "REST auth succeeded but script-details sanity check failed: %s",
                test_err,
            )

        return True, "REST login and MPIN validation successful"

    except Exception as e:  # noqa: BLE001
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
        trade_mode=TradeMode.BROKER,  # Switch to broker mode when credentials are saved
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

    # Test connection only - do NOT save broker mode or credentials
    # Broker mode will be set only when user clicks "Save Credentials"
    # This allows users to test without committing to broker mode

    return BrokerTestResponse(ok=success, message=message)


@router.get("/status", response_model=dict)
def broker_status(
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> dict[str, str | None]:
    """
    Get broker connection status.

    For Kotak Neo, this checks if a valid session exists without triggering login/OTP.
    Only updates status if session check fails.
    """
    repo = SettingsRepository(db)
    settings = repo.ensure_default(current.id)

    # If not in broker mode or no broker configured, return stored status
    if settings.trade_mode != TradeMode.BROKER or not settings.broker_creds_encrypted:
        return {"broker": settings.broker, "status": settings.broker_status}

    # Check cached auth session first (if available from previous API calls)
    # This avoids creating new auth instances on every status check
    from modules.kotak_neo_auto_trader.shared_session_manager import (
        get_shared_session_manager,
    )

    session_manager = get_shared_session_manager()
    auth = session_manager.get_session(current.id)

    if auth and auth.is_authenticated():
        # Cached session is valid - return Connected status
        if settings.broker_status != "Connected":
            settings = repo.update(settings, broker_status="Connected")
            db.commit()
        return {"broker": settings.broker, "status": "Connected"}

    # No cached session - just return stored status without creating new auth instance
    # This prevents "KotakNeoAuth initialized" log spam from status polling
    # The status will be updated by portfolio/orders endpoints when they succeed/fail
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


@router.get("/portfolio", response_model=PaperTradingPortfolio)
def get_broker_portfolio(  # noqa: PLR0915, PLR0912, B008
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Get broker portfolio for the current user.

    Fetches holdings from the connected broker and converts them to the same
    format as paper trading portfolio for consistency.
    """
    try:
        # Get user settings
        settings_repo = SettingsRepository(db)
        settings = settings_repo.get_by_user_id(current.id)
        if not settings:
            raise HTTPException(
                status_code=404, detail="User settings not found. Please configure your account."
            )

        # Check if broker mode
        if settings.trade_mode != TradeMode.BROKER:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Broker portfolio is only available in broker mode. "
                    f"Current mode: {settings.trade_mode.value}"
                ),
            )

        # Check if broker credentials exist
        if not settings.broker_creds_encrypted:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Broker credentials not configured. "
                    "Please configure broker credentials in settings."
                ),
            )

        # Decrypt broker credentials
        broker_creds = decrypt_broker_credentials(settings.broker_creds_encrypted)
        if not broker_creds:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Failed to decrypt broker credentials. "
                    "Please reconfigure your broker credentials."
                ),
            )

        # Create temporary env file for KotakNeoAuth
        temp_env_file = create_temp_env_file(broker_creds)

        try:
            # Import broker components
            from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter import (  # noqa: E501
                BrokerServiceUnavailableError,
            )
            from modules.kotak_neo_auto_trader.infrastructure.broker_factory import (
                BrokerFactory,
            )

            # Get or create authenticated session (handles unified service conflicts)
            logger.info(f"[BROKER_PORTFOLIO] Getting/creating auth session for user {current.id}")
            auth = _get_or_create_auth_session(current.id, temp_env_file, db)

            # Log session state
            is_auth = auth.is_authenticated()
            client = auth.get_client()
            logger.info(
                f"[BROKER_PORTFOLIO] Session state for user {current.id}: "
                f"is_authenticated={is_auth}, client={'available' if client else 'None'}"
            )

            # Check for stale session: is_authenticated() is True but client is None
            # This can happen when session expires but is_authenticated() hasn't been updated yet
            if is_auth and not client:
                logger.warning(
                    f"[BROKER_PORTFOLIO] Stale session detected for user {current.id}: "
                    f"is_authenticated={is_auth} but client is None. "
                    "Clearing cache and forcing re-authentication"
                )
                from modules.kotak_neo_auto_trader.shared_session_manager import (
                    get_shared_session_manager,
                )

                session_manager = get_shared_session_manager()
                session_manager.clear_session(current.id)
                logger.info(
                    f"[BROKER_PORTFOLIO] Cleared stale session for user {current.id}, "
                    "creating new session"
                )
                # Force new session creation
                auth = _get_or_create_auth_session(current.id, temp_env_file, db, force_new=True)
                if not auth or not auth.is_authenticated():
                    logger.error(
                        f"[BROKER_PORTFOLIO] Re-authentication failed for user {current.id}"
                    )
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Broker session expired and re-authentication failed. "
                            "Please refresh the page to reconnect."
                        ),
                    )
                logger.info(
                    f"[BROKER_PORTFOLIO] Re-authentication successful for user {current.id}"
                )
                # Update session state after re-auth
                is_auth = auth.is_authenticated()
                client = auth.get_client()
                logger.info(
                    f"[BROKER_PORTFOLIO] Updated session state for user {current.id}: "
                    f"is_authenticated={is_auth}, client={'available' if client else 'None'}"
                )

            # Create broker gateway
            broker = BrokerFactory.create_broker("kotak_neo", auth_handler=auth)

            # Connect to broker (only if not already connected)
            # broker.connect() calls auth.login() which triggers OTP,
            # so manually set client if already authenticated
            if not is_auth:
                logger.info(
                    f"[BROKER_PORTFOLIO] User {current.id} not authenticated, attempting connection"
                )
                if not broker.connect():
                    logger.error(
                        f"[BROKER_PORTFOLIO] Failed to connect broker gateway for user {current.id}"
                    )
                    raise HTTPException(
                        status_code=503,
                        detail="Failed to connect to broker gateway. Please try again later.",
                    )
                logger.info(
                    f"[BROKER_PORTFOLIO] Successfully connected broker gateway "
                    f"for user {current.id}"
                )
            else:
                # Auth is already authenticated, manually set client to avoid re-login
                # This prevents OTP spam while ensuring broker is properly initialized
                # Trust the cached auth - only re-authenticate if API calls actually fail
                logger.debug(
                    f"[BROKER_PORTFOLIO] Auth already authenticated for user {current.id}, "
                    "manually initializing broker client"
                )
                if client:
                    # Client is available - use it directly without calling connect()
                    broker._client = client
                    broker._connected = True
                    logger.info(f"[BROKER_PORTFOLIO] Using existing client for user {current.id}")
                else:
                    # Client is None - this shouldn't happen if is_authenticated() is True
                    # But if it does, clear cache and force re-authentication
                    logger.warning(
                        f"[BROKER_PORTFOLIO] Session inconsistency detected for user {current.id}: "
                        f"is_authenticated={is_auth} but client is None. "
                        "Clearing cache and forcing re-authentication"
                    )
                    from modules.kotak_neo_auto_trader.shared_session_manager import (
                        get_shared_session_manager,
                    )

                    session_manager = get_shared_session_manager()
                    session_manager.clear_session(current.id)
                    logger.info(
                        f"[BROKER_PORTFOLIO] Cleared expired session for user {current.id}, "
                        "creating new session"
                    )
                    # Force new session creation
                    auth = _get_or_create_auth_session(
                        current.id, temp_env_file, db, force_new=True
                    )
                    if not auth or not auth.is_authenticated():
                        logger.error(
                            f"[BROKER_PORTFOLIO] Re-authentication failed for user {current.id}"
                        )
                        raise HTTPException(
                            status_code=503,
                            detail=(
                                "Broker session expired and re-authentication failed. "
                                "Please refresh the page to reconnect."
                            ),
                        )
                    logger.info(
                        f"[BROKER_PORTFOLIO] Re-authentication successful for user {current.id}"
                    )
                    # Update broker with new auth
                    broker = BrokerFactory.create_broker("kotak_neo", auth_handler=auth)
                    if not broker.connect():
                        logger.error(
                            f"[BROKER_PORTFOLIO] Failed to reconnect broker gateway "
                            f"after re-auth for user {current.id}"
                        )
                        raise HTTPException(
                            status_code=503,
                            detail="Failed to reconnect to broker gateway. Please try again later.",
                        )
                    logger.info(
                        f"[BROKER_PORTFOLIO] Successfully reconnected broker gateway "
                        f"for user {current.id}"
                    )

            # Get holdings from broker
            # This will automatically handle re-authentication if session expired
            logger.info(f"[BROKER_PORTFOLIO] Fetching holdings for user {current.id}")
            try:
                holdings = broker.get_holdings()
                logger.info(
                    f"[BROKER_PORTFOLIO] Successfully fetched {len(holdings)} holdings "
                    f"for user {current.id}"
                )
            except Exception as holdings_error:
                logger.error(
                    f"[BROKER_PORTFOLIO] Error fetching holdings for user {current.id}: "
                    f"{holdings_error}",
                    exc_info=True,
                )
                raise

            # Get account limits/margins for available cash
            try:
                account_limits = broker.get_account_limits()
                # Extract available cash from account limits (returns Money objects)
                available_cash_money = account_limits.get("available_cash") or account_limits.get(
                    "net"
                )
                if available_cash_money and hasattr(available_cash_money, "amount"):
                    available_cash = float(available_cash_money.amount)
                else:
                    available_cash = 0.0
            except Exception as e:
                # If account limits not available, set to 0
                available_cash = 0.0
                logger.warning(f"Could not fetch account limits for broker portfolio: {e}")

            # Convert broker holdings to paper trading format
            portfolio_holdings = []
            portfolio_value = 0.0
            unrealized_pnl_total = 0.0

            # Use broker's current price directly (faster, no external API calls)
            # Broker API already provides current_price, so we don't need yfinance
            for holding in holdings:
                if holding.quantity == 0:
                    continue

                # Use broker's current price directly (avoids slow yfinance API calls)
                symbol = holding.symbol
                current_price = float(holding.current_price.amount)

                # Calculate values
                avg_price = float(holding.average_price.amount)
                cost_basis = avg_price * holding.quantity
                market_value = current_price * holding.quantity
                pnl = market_value - cost_basis
                pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0

                portfolio_value += market_value
                unrealized_pnl_total += pnl

                # Fetch reentry details from database positions table
                reentry_count = 0
                reentries_list = None
                entry_rsi = None
                initial_entry_price = None

                try:
                    from src.infrastructure.persistence.positions_repository import (
                        PositionsRepository,
                    )

                    positions_repo = PositionsRepository(db)
                    # After migration, positions have full symbols (e.g., "RELIANCE-EQ")
                    # Try exact match first (broker may return full symbol)
                    full_symbol = symbol.upper().replace(".NS", "").replace(".BO", "")
                    position = positions_repo.get_by_symbol(current.id, full_symbol)

                    # Fallback: If not found and symbol has segment suffix, try base symbol matching
                    # This handles cases where broker returns base symbol but position has full
                    # symbol (e.g., RELIANCE vs RELIANCE-EQ)
                    if not position and "-" in full_symbol:
                        from modules.kotak_neo_auto_trader.utils.symbol_utils import (
                            extract_base_symbol,
                        )

                        base_symbol = extract_base_symbol(full_symbol).upper()
                        # Query all positions and find one matching base symbol
                        all_positions = positions_repo.list(current.id)
                        for pos in all_positions:
                            if extract_base_symbol(pos.symbol).upper() == base_symbol:
                                position = pos
                                break
                    if position:
                        reentry_count = position.reentry_count or 0
                        entry_rsi = position.entry_rsi
                        initial_entry_price = position.initial_entry_price

                        # Parse reentries JSON field
                        if position.reentries:
                            if isinstance(position.reentries, dict):
                                # New format: {"reentries": [...], "current_cycle": ...}
                                reentries_list = position.reentries.get("reentries", [])
                            elif isinstance(position.reentries, list):
                                # Old format: direct array
                                reentries_list = position.reentries
                            else:
                                reentries_list = []
                        else:
                            reentries_list = []

                        logger.debug(
                            f"Found reentry data for {symbol} "
                            f"(full_symbol: {full_symbol}): "
                            f"count={reentry_count}, "
                            f"reentries={len(reentries_list) if reentries_list else 0}"
                        )
                    else:
                        logger.debug(
                            f"No position found for {symbol} "
                            f"(full_symbol: {full_symbol}) in database"
                        )
                except Exception as e:
                    logger.debug(f"Could not fetch reentry details for {symbol}: {e}")

                portfolio_holdings.append(
                    PaperTradingHolding(
                        symbol=symbol,
                        quantity=holding.quantity,
                        average_price=avg_price,
                        current_price=current_price,
                        cost_basis=cost_basis,
                        market_value=market_value,
                        pnl=pnl,
                        pnl_percentage=pnl_pct,
                        target_price=None,  # Broker holdings don't have target prices
                        distance_to_target=None,
                        reentry_count=reentry_count,
                        reentries=reentries_list,
                        entry_rsi=entry_rsi,
                        initial_entry_price=initial_entry_price,
                    )
                )

            # Calculate account totals
            total_value = available_cash + portfolio_value
            # For broker mode, we don't track initial_capital or realized_pnl separately
            # Use available_cash as initial capital estimate
            initial_capital_estimate = available_cash + portfolio_value - unrealized_pnl_total
            realized_pnl = 0.0  # Broker API doesn't provide this directly

            total_pnl = realized_pnl + unrealized_pnl_total
            return_pct = (
                (total_pnl / initial_capital_estimate * 100)
                if initial_capital_estimate > 0
                else 0.0
            )

            # Create account object
            account = PaperTradingAccount(
                initial_capital=initial_capital_estimate,
                available_cash=available_cash,
                total_pnl=total_pnl,
                realized_pnl=realized_pnl,
                unrealized_pnl=unrealized_pnl_total,
                portfolio_value=portfolio_value,
                total_value=total_value,
                return_percentage=return_pct,
            )

            # Get recent orders (empty for now - can be enhanced later)
            recent_orders = []

            # Order statistics (empty for now - can be enhanced later)
            order_statistics = {
                "total_orders": 0,
                "buy_orders": 0,
                "sell_orders": 0,
                "completed_orders": 0,
                "pending_orders": 0,
                "cancelled_orders": 0,
                "rejected_orders": 0,
                "success_rate": 0.0,
            }

            return PaperTradingPortfolio(
                account=account,
                holdings=portfolio_holdings,
                recent_orders=recent_orders,
                order_statistics=order_statistics,
            )

        finally:
            # Clean up temporary env file
            try:
                Path(temp_env_file).unlink(missing_ok=True)
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temp env file: {cleanup_error}")

    except HTTPException:
        raise
    except BrokerServiceUnavailableError as e:
        # Broker service is unavailable (maintenance, downtime, etc.)
        # Use the actual error message from the API if available, otherwise use default
        error_message = e.message if hasattr(e, "message") else str(e)
        logger.warning(f"Broker service unavailable for user {current.id}: {error_message}")
        raise HTTPException(
            status_code=503,
            detail=error_message,
        ) from e
    except Exception as e:
        logger.exception(f"Error fetching broker portfolio for user {current.id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch broker portfolio: {str(e)}"
        ) from e


@router.get("/system-holdings", response_model=PaperTradingPortfolio)
def get_broker_system_holdings(  # noqa: PLR0915, PLR0912, B008
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Get system-tracked holdings for the current user (broker mode).

    Returns only positions that the system tracks in the Positions table (open positions).
    Use this to see what the system considers "its" holdings vs all broker holdings.
    Does not require broker to be connected; when disconnected, current price is shown
    as avg price (P&L will be zero). When connected, current price is enriched from broker.
    """
    try:
        settings_repo = SettingsRepository(db)
        settings = settings_repo.get_by_user_id(current.id)
        if not settings:
            raise HTTPException(
                status_code=404, detail="User settings not found. Please configure your account."
            )
        if settings.trade_mode != TradeMode.BROKER:
            raise HTTPException(
                status_code=400,
                detail=(
                    "System holdings is only available in broker mode. "
                    f"Current mode: {settings.trade_mode.value}"
                ),
            )

        from src.infrastructure.persistence.positions_repository import PositionsRepository

        positions_repo = PositionsRepository(db)
        all_positions = positions_repo.list(current.id)
        open_positions = [p for p in all_positions if p.closed_at is None]

        # Optional: get current prices from broker if connected
        broker_price_by_symbol = {}
        if settings.broker_creds_encrypted:
            broker_creds = decrypt_broker_credentials(settings.broker_creds_encrypted)
            if broker_creds:
                temp_env_file = create_temp_env_file(broker_creds)
                try:
                    auth = _get_or_create_auth_session(current.id, temp_env_file, db)
                    if auth and auth.is_authenticated():
                        from modules.kotak_neo_auto_trader.infrastructure.broker_factory import (
                            BrokerFactory,
                        )

                        broker = BrokerFactory.create_broker("kotak_neo", auth_handler=auth)
                        holdings = broker.get_holdings()
                        for holding in holdings:
                            if holding.quantity == 0:
                                continue
                            sym = holding.symbol.upper().replace(".NS", "").replace(".BO", "")
                            if "-" not in sym:
                                sym = f"{sym}-EQ"
                            broker_price_by_symbol[sym] = float(holding.current_price.amount)
                            # Also map base symbol for positions that use full symbol
                            base = (
                                sym.replace("-EQ", "")
                                .replace("-BE", "")
                                .replace("-BL", "")
                                .replace("-BZ", "")
                            )
                            broker_price_by_symbol[base] = float(holding.current_price.amount)
                except Exception as e:
                    logger.debug(f"Could not fetch broker prices for system holdings: {e}")
                finally:
                    try:
                        Path(temp_env_file).unlink(missing_ok=True)
                    except Exception:
                        pass

        portfolio_holdings = []
        portfolio_value = 0.0
        unrealized_pnl_total = 0.0

        for pos in open_positions:
            current_price = (
                broker_price_by_symbol.get(pos.symbol.upper())
                or broker_price_by_symbol.get(
                    pos.symbol.upper()
                    .replace("-EQ", "")
                    .replace("-BE", "")
                    .replace("-BL", "")
                    .replace("-BZ", "")
                )
                or pos.avg_price
            )
            qty = int(pos.quantity)
            avg_price = float(pos.avg_price)
            cost_basis = avg_price * qty
            market_value = current_price * qty
            pnl = market_value - cost_basis
            pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0

            portfolio_value += market_value
            unrealized_pnl_total += pnl

            reentry_count = pos.reentry_count or 0
            reentries_list = None
            if pos.reentries:
                if isinstance(pos.reentries, dict):
                    reentries_list = pos.reentries.get("reentries", [])
                elif isinstance(pos.reentries, list):
                    reentries_list = pos.reentries
                else:
                    reentries_list = []

            portfolio_holdings.append(
                PaperTradingHolding(
                    symbol=pos.symbol,
                    quantity=qty,
                    average_price=avg_price,
                    current_price=current_price,
                    cost_basis=cost_basis,
                    market_value=market_value,
                    pnl=pnl,
                    pnl_percentage=pnl_pct,
                    target_price=None,
                    distance_to_target=None,
                    reentry_count=reentry_count,
                    reentries=reentries_list,
                    entry_rsi=float(pos.entry_rsi) if pos.entry_rsi is not None else None,
                    initial_entry_price=(
                        float(pos.initial_entry_price)
                        if pos.initial_entry_price is not None
                        else None
                    ),
                )
            )

        account = PaperTradingAccount(
            initial_capital=portfolio_value - unrealized_pnl_total,
            available_cash=0.0,
            total_pnl=unrealized_pnl_total,
            realized_pnl=0.0,
            unrealized_pnl=unrealized_pnl_total,
            portfolio_value=portfolio_value,
            total_value=portfolio_value,
            return_percentage=(
                (unrealized_pnl_total / (portfolio_value - unrealized_pnl_total) * 100)
                if (portfolio_value - unrealized_pnl_total) > 0
                else 0.0
            ),
        )

        return PaperTradingPortfolio(
            account=account,
            holdings=portfolio_holdings,
            recent_orders=[],
            order_statistics={
                "total_orders": 0,
                "buy_orders": 0,
                "sell_orders": 0,
                "completed_orders": 0,
                "pending_orders": 0,
                "cancelled_orders": 0,
                "rejected_orders": 0,
                "success_rate": 0.0,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching broker system holdings for user {current.id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch system holdings: {str(e)}"
        ) from e


@router.get("/orders", response_model=list[dict])
def get_broker_orders(  # noqa: PLR0915, PLR0912, B008
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Get broker orders for the current user.

    Fetches orders directly from the connected broker and returns them
    in a simplified format.
    """
    try:
        # Get user settings
        settings_repo = SettingsRepository(db)
        settings = settings_repo.get_by_user_id(current.id)
        if not settings:
            raise HTTPException(
                status_code=404, detail="User settings not found. Please configure your account."
            )

        # Check if broker mode
        if settings.trade_mode != TradeMode.BROKER:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Broker orders are only available in broker mode. "
                    f"Current mode: {settings.trade_mode.value}"
                ),
            )

        # Check if broker credentials exist
        if not settings.broker_creds_encrypted:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Broker credentials not configured. "
                    "Please configure broker credentials in settings."
                ),
            )

        # Decrypt broker credentials
        broker_creds = decrypt_broker_credentials(settings.broker_creds_encrypted)
        if not broker_creds:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Failed to decrypt broker credentials. "
                    "Please reconfigure your broker credentials."
                ),
            )

        # Create temporary env file for KotakNeoAuth
        temp_env_file = create_temp_env_file(broker_creds)

        try:
            # Import broker components
            from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter import (  # noqa: E501
                BrokerServiceUnavailableError,
            )
            from modules.kotak_neo_auto_trader.infrastructure.broker_factory import (
                BrokerFactory,
            )

            # Get or create authenticated session using shared session manager
            logger.info(f"[BROKER_ORDERS] Getting/creating auth session for user {current.id}")
            auth = _get_or_create_auth_session(current.id, temp_env_file, db)

            # Log session state
            is_auth = auth.is_authenticated()
            client = auth.get_client()
            logger.info(
                f"[BROKER_ORDERS] Session state for user {current.id}: "
                f"is_authenticated={is_auth}, client={'available' if client else 'None'}"
            )

            # Check for stale session: is_authenticated() is True but client is None
            # This can happen when session expires but is_authenticated() hasn't been updated yet
            if is_auth and not client:
                logger.warning(
                    f"[BROKER_ORDERS] Stale session detected for user {current.id}: "
                    f"is_authenticated={is_auth} but client is None. "
                    "Clearing cache and forcing re-authentication"
                )
                from modules.kotak_neo_auto_trader.shared_session_manager import (
                    get_shared_session_manager,
                )

                session_manager = get_shared_session_manager()
                session_manager.clear_session(current.id)
                logger.info(
                    f"[BROKER_ORDERS] Cleared stale session for user {current.id}, "
                    "creating new session"
                )
                # Force new session creation
                auth = _get_or_create_auth_session(current.id, temp_env_file, db, force_new=True)
                if not auth or not auth.is_authenticated():
                    logger.error(f"[BROKER_ORDERS] Re-authentication failed for user {current.id}")
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Broker session expired and re-authentication failed. "
                            "Please refresh the page to reconnect."
                        ),
                    )
                logger.info(f"[BROKER_ORDERS] Re-authentication successful for user {current.id}")
                # Update session state after re-auth
                is_auth = auth.is_authenticated()
                client = auth.get_client()
                logger.info(
                    f"[BROKER_ORDERS] Updated session state for user {current.id}: "
                    f"is_authenticated={is_auth}, client={'available' if client else 'None'}"
                )

            # Create broker gateway
            broker_gateway = BrokerFactory.create_broker("kotak_neo", auth_handler=auth)

            # Connect to broker (only if not already connected)
            # broker.connect() calls auth.login() which triggers OTP,
            # so manually set client if already authenticated
            if not is_auth:
                logger.info(
                    f"[BROKER_ORDERS] User {current.id} not authenticated, attempting connection"
                )
                if not broker_gateway.connect():
                    logger.error(
                        f"[BROKER_ORDERS] Failed to connect broker gateway for user {current.id}"
                    )
                    raise HTTPException(
                        status_code=503,
                        detail="Failed to connect to broker gateway. Please try again later.",
                    )
                logger.info(
                    f"[BROKER_ORDERS] Successfully connected broker gateway for user {current.id}"
                )
            else:
                # Auth is already authenticated, manually set client to avoid re-login
                # This prevents OTP spam while ensuring broker is properly initialized
                # Trust the cached auth - only re-authenticate if API calls actually fail
                logger.debug(
                    f"[BROKER_ORDERS] Auth already authenticated for user {current.id}, "
                    "manually initializing broker client"
                )
                if client:
                    # Client is available - use it directly without calling connect()
                    broker_gateway._client = client
                    broker_gateway._connected = True
                    logger.info(f"[BROKER_ORDERS] Using existing client for user {current.id}")
                else:
                    # Client is None - this shouldn't happen if is_authenticated() is True
                    # But if it does, clear cache and force re-authentication
                    logger.warning(
                        f"[BROKER_ORDERS] Session inconsistency detected for user {current.id}: "
                        f"is_authenticated={is_auth} but client is None. "
                        "Clearing cache and forcing re-authentication"
                    )
                    from modules.kotak_neo_auto_trader.shared_session_manager import (
                        get_shared_session_manager,
                    )

                    session_manager = get_shared_session_manager()
                    session_manager.clear_session(current.id)
                    logger.info(
                        f"[BROKER_ORDERS] Cleared expired session for user {current.id}, "
                        "creating new session"
                    )
                    # Force new session creation
                    auth = _get_or_create_auth_session(
                        current.id, temp_env_file, db, force_new=True
                    )
                    if not auth or not auth.is_authenticated():
                        logger.error(
                            f"[BROKER_ORDERS] Re-authentication failed for user {current.id}"
                        )
                        raise HTTPException(
                            status_code=503,
                            detail=(
                                "Broker session expired and re-authentication failed. "
                                "Please refresh the page to reconnect."
                            ),
                        )
                    logger.info(
                        f"[BROKER_ORDERS] Re-authentication successful for user {current.id}"
                    )
                    # Update broker gateway with new auth
                    broker_gateway = BrokerFactory.create_broker("kotak_neo", auth_handler=auth)
                    if not broker_gateway.connect():
                        logger.error(
                            f"[BROKER_ORDERS] Failed to reconnect broker gateway "
                            f"after re-auth for user {current.id}"
                        )
                        raise HTTPException(
                            status_code=503,
                            detail="Failed to reconnect to broker gateway. Please try again later.",
                        )
                    logger.info(
                        f"[BROKER_ORDERS] Successfully reconnected broker gateway "
                        f"for user {current.id}"
                    )

            # Get orders from broker
            # This will automatically handle re-authentication if session expired
            logger.info(f"[BROKER_ORDERS] Fetching orders for user {current.id}")
            try:
                broker_orders = broker_gateway.get_all_orders()
                logger.info(
                    f"[BROKER_ORDERS] Successfully fetched {len(broker_orders)} orders "
                    f"for user {current.id}"
                )
            except Exception as orders_error:
                logger.error(
                    f"[BROKER_ORDERS] Error fetching orders for user {current.id}: {orders_error}",
                    exc_info=True,
                )
                raise

            # Convert broker orders to simplified format
            orders_list = []
            for order in broker_orders:
                try:
                    # Map broker order status to our status format
                    broker_status = (
                        order.status.value.lower()
                        if hasattr(order.status, "value")
                        else str(order.status).lower()
                    )
                    status_map = {
                        "pending": "pending",
                        "open": "pending",
                        "executed": "ongoing",
                        "complete": "closed",  # OrderStatus.COMPLETE.value.lower() = "complete"
                        "completed": "closed",  # Support both variants for compatibility
                        "filled": "closed",
                        "partially_filled": "ongoing",  # Partially executed orders
                        "trigger_pending": "pending",  # Trigger pending orders
                        "rejected": "failed",
                        "cancelled": "cancelled",
                        "failed": "failed",
                    }
                    mapped_status = status_map.get(broker_status, "pending")

                    # Determine side
                    side = "buy" if order.transaction_type.value == "BUY" else "sell"

                    orders_list.append(
                        {
                            "broker_order_id": (
                                order.order_id if hasattr(order, "order_id") else None
                            ),
                            "symbol": order.symbol,
                            "side": side,
                            "quantity": order.quantity,
                            "price": (
                                float(order.price.amount)
                                if hasattr(order, "price") and hasattr(order.price, "amount")
                                else None
                            ),
                            "status": mapped_status,
                            "created_at": (
                                order.created_at.isoformat()
                                if hasattr(order, "created_at") and order.created_at
                                else None
                            ),
                            "execution_price": (
                                float(order.executed_price.amount)
                                if hasattr(order, "executed_price")
                                and hasattr(order.executed_price, "amount")
                                else None
                            ),
                            "execution_qty": (
                                order.executed_quantity
                                if hasattr(order, "executed_quantity")
                                else None
                            ),
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to convert order to API format: {e}")
                    continue

            return orders_list

        finally:
            # Clean up temporary env file
            try:
                Path(temp_env_file).unlink(missing_ok=True)
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temp env file: {cleanup_error}")

    except HTTPException:
        raise
    except BrokerServiceUnavailableError as e:
        # Broker service is unavailable (maintenance, downtime, etc.)
        # Use the actual error message from the API if available, otherwise use default
        error_message = e.message if hasattr(e, "message") else str(e)
        logger.warning(f"Broker service unavailable for user {current.id}: {error_message}")
        raise HTTPException(
            status_code=503,
            detail=error_message,
        ) from e
    except Exception as e:
        logger.exception(f"Error fetching broker orders for user {current.id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch broker orders: {str(e)}"
        ) from e


@router.post("/session/clear")
def clear_broker_session(
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> dict[str, str]:
    """
    Clear broker session for testing purposes.

    This endpoint manually clears the broker session to simulate session expiration.
    Useful for testing re-authentication logic without waiting for actual session expiry.
    """
    try:
        from modules.kotak_neo_auto_trader.shared_session_manager import (
            get_shared_session_manager,
        )

        session_manager = get_shared_session_manager()
        session_manager.clear_session(current.id)
        logger.info(
            f"[BROKER_SESSION] Manually cleared session for user {current.id} (testing endpoint)"
        )
        return {
            "status": "success",
            "message": f"Broker session cleared for user {current.id}. "
            "Next API call will trigger re-authentication.",
        }
    except Exception as e:
        logger.error(f"[BROKER_SESSION] Error clearing session for user {current.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear broker session: {str(e)}",
        ) from e


@router.get("/history", response_model=TradeHistory)
def get_broker_trading_history(  # noqa: PLR0915, PLR0912
    from_date: Annotated[str | None, Query(description="Filter from date (ISO format)")] = None,
    to_date: Annotated[str | None, Query(description="Filter to date (ISO format)")] = None,
    raw: Annotated[
        bool, Query(description="Return raw transactions without FIFO matching")
    ] = False,
    limit: Annotated[int, Query(ge=1, le=10000, description="Limit results (max 10000)")] = 1000,
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
) -> TradeHistory:
    """
    Get complete broker trading history with transactions and closed positions.

    - **from_date**: Filter transactions from this date (ISO format)
    - **to_date**: Filter transactions up to this date (ISO format)
    - **raw**: If true, return raw transactions without FIFO matching
    - **limit**: Maximum number of transactions to return (default: 1000, max: 10000)

    Returns:
        - All broker transactions (buys and sells)
        - Closed positions with P&L (using FIFO matching if raw=false)
        - Statistics (win rate, avg profit, etc.)
    """
    try:
        # Get user settings
        settings_repo = SettingsRepository(db)
        settings = settings_repo.get_by_user_id(current.id)
        if not settings:
            raise HTTPException(
                status_code=404, detail="User settings not found. Please configure your account."
            )

        # Check if broker mode
        if settings.trade_mode != TradeMode.BROKER:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Broker history is only available in broker mode. "
                    f"Current mode: {settings.trade_mode.value}"
                ),
            )

        # Query orders from database
        from sqlalchemy import and_

        query = db.query(Orders).filter(
            and_(
                Orders.user_id == current.id,
                Orders.trade_mode == TradeMode.BROKER,
            )
        )

        # Apply date filters if provided
        if from_date:
            try:
                from datetime import datetime

                from_dt = datetime.fromisoformat(from_date)
                query = query.filter(Orders.placed_at >= from_dt)
            except Exception as e:
                logger.warning(f"Invalid from_date: {e}")

        if to_date:
            try:
                from datetime import datetime

                to_dt = datetime.fromisoformat(to_date)
                query = query.filter(Orders.placed_at <= to_dt)
            except Exception as e:
                logger.warning(f"Invalid to_date: {e}")

        # Order by placed_at ascending (oldest first) for FIFO matching
        orders = query.order_by(Orders.placed_at.asc()).limit(limit).all()

        # Convert orders to transaction format
        transactions = []
        for order in orders:
            side = "buy" if order.side.lower() == "buy" else "sell"
            # Use order_id if available, otherwise use broker_order_id,
            # otherwise use string representation of db id
            order_identifier = order.order_id or order.broker_order_id or str(order.id)
            # Use execution_price if available, fall back to avg_price, then None
            order_price = order.execution_price or order.avg_price
            transactions.append(
                {
                    "order_id": order_identifier,
                    "symbol": order.symbol,
                    "side": side,
                    "quantity": float(order.quantity),
                    "price": float(order_price) if order_price else None,
                    "avg_price": float(order_price) if order_price else None,
                    "execution_price": float(order_price) if order_price else None,
                    "placed_at": order.placed_at.isoformat() if order.placed_at else None,
                    "status": order.status.value.lower() if order.status else "unknown",
                }
            )

        # Create PaperTradingTransaction list for response
        transaction_list = [
            PaperTradingTransaction(
                order_id=t.get("order_id", ""),
                symbol=t.get("symbol", ""),
                transaction_type=t.get("side", "").upper(),  # BUY or SELL
                quantity=int(t.get("quantity", 0)),
                price=t.get("price", 0.0) or 0.0,
                order_value=(float(t.get("quantity", 0)) * (t.get("price") or 0.0)),  # qty * price
                charges=0.0,  # Placeholder; can be enhanced with broker charges
                timestamp=t.get("placed_at", ""),
            )
            for t in transactions
        ]

        # Get closed positions: either from DB or via FIFO matching
        closed_positions_list = []
        if raw:
            # Raw mode: only return transactions, no matching
            closed_positions_list = []
        else:
            # Apply FIFO matching to derive closed positions
            fifo_closed = _fifo_match_orders(transactions)
            for cp in fifo_closed:
                try:
                    from datetime import datetime

                    # Calculate holding days
                    holding_days = 0
                    if cp.get("opened_at") and cp.get("closed_at"):
                        try:
                            opened = datetime.fromisoformat(
                                cp.get("opened_at", "1970-01-01T00:00:00")
                            )
                            closed = datetime.fromisoformat(
                                cp.get("closed_at", "1970-01-01T00:00:00")
                            )
                            holding_days = (closed - opened).days
                        except Exception:
                            holding_days = 0

                    closed_positions_list.append(
                        ClosedPosition(
                            symbol=cp.get("symbol", ""),
                            quantity=int(cp.get("quantity", 0)),
                            entry_price=(
                                float(cp.get("avg_price", 0.0)) if cp.get("avg_price") else 0.0
                            ),
                            exit_price=(
                                float(cp.get("exit_price", 0.0)) if cp.get("exit_price") else 0.0
                            ),
                            buy_date=cp.get("opened_at", ""),
                            sell_date=cp.get("closed_at", ""),
                            holding_days=holding_days,
                            realized_pnl=(
                                float(cp.get("realized_pnl", 0.0))
                                if cp.get("realized_pnl")
                                else 0.0
                            ),
                            pnl_percentage=(
                                float(cp.get("realized_pnl_pct", 0.0))
                                if cp.get("realized_pnl_pct") is not None
                                else 0.0
                            ),
                            charges=0.0,  # Placeholder; can be enhanced with actual broker charges
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to convert closed position: {e}")
                    continue

        # Calculate statistics
        _upsert_pnl_from_closed_positions(current.id, closed_positions_list, db)

        total_trades = len(closed_positions_list)
        profitable_trades = sum(1 for cp in closed_positions_list if cp.realized_pnl > 0)
        losing_trades = sum(1 for cp in closed_positions_list if cp.realized_pnl < 0)
        breakeven_trades = sum(1 for cp in closed_positions_list if cp.realized_pnl == 0)
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0.0
        total_profit = sum(cp.realized_pnl for cp in closed_positions_list if cp.realized_pnl > 0)
        total_loss = sum(cp.realized_pnl for cp in closed_positions_list if cp.realized_pnl < 0)
        net_pnl = total_profit + total_loss
        avg_profit_per_trade = (total_profit / profitable_trades) if profitable_trades > 0 else 0.0
        avg_loss_per_trade = (total_loss / losing_trades) if losing_trades > 0 else 0.0

        statistics = {
            "total_trades": total_trades,
            "profitable_trades": profitable_trades,
            "losing_trades": losing_trades,
            "breakeven_trades": breakeven_trades,
            "win_rate": float(win_rate),
            "total_profit": float(total_profit),
            "total_loss": float(total_loss),
            "net_pnl": float(net_pnl),
            "avg_profit_per_trade": float(avg_profit_per_trade),
            "avg_loss_per_trade": float(avg_loss_per_trade),
        }

        return TradeHistory(
            transactions=transaction_list,
            closed_positions=closed_positions_list,
            statistics=statistics,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching broker trading history for user {current.id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch broker trading history: {str(e)}"
        ) from e
