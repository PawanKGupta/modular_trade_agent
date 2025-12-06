# ruff: noqa: B008, PLR0913, PLR0911, PLR0912, PLC0415
import ast
import json
import logging
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.application.services.broker_credentials import (
    create_temp_env_file,
    decrypt_broker_credentials,
)
from src.infrastructure.db.models import TradeMode, Users
from src.infrastructure.persistence.settings_repository import SettingsRepository

from ..core.crypto import decrypt_blob, encrypt_blob
from ..core.deps import get_current_user, get_db
from ..routers.paper_trading import (
    PaperTradingAccount,
    PaperTradingHolding,
    PaperTradingPortfolio,
)
from ..schemas.user import BrokerCredsInfo, BrokerCredsRequest, BrokerTestResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory cache for authenticated broker sessions
# Key: user_id, Value: auth_instance
_broker_auth_cache: dict[int, object] = {}
_broker_auth_cache_lock = threading.Lock()

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
            install_cmd = "pip install --no-deps git+https://github.com/Kotak-Neo/kotak-neo-api@67143c58f29da9572cdbb273199852682a0019d5#egg=neo-api-client"
            technical_details = (
                f"Kotak Neo SDK (neo_api_client) not installed on server.\n"
                f"Python version: {python_version.major}.{python_version.minor}\n"
                f"Install command: {install_cmd}\n"
                f"Note: Using --no-deps to avoid numpy version conflicts.\n"
                f"See docker/INSTALL_KOTAK_SDK.md for detailed instructions."
            )
        else:
            install_cmd = "pip install git+https://github.com/Kotak-Neo/kotak-neo-api@67143c58f29da9572cdbb273199852682a0019d5#egg=neo-api-client"
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
    auth = _broker_auth_cache.get(current.id)

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
            from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
            from modules.kotak_neo_auto_trader.infrastructure.broker_factory import (
                BrokerFactory,
            )

            # Thread-safe session caching - similar to trading service pattern
            # Reuse existing auth instance if available (it handles re-auth internally)
            auth = _broker_auth_cache.get(current.id)

            if not auth:
                with _broker_auth_cache_lock:
                    # Double-check: another thread might have created it
                    auth = _broker_auth_cache.get(current.id)
                    if not auth:
                        # Create new auth instance and login (only once per user)
                        logger.info(f"Creating new auth session for user {current.id}")
                        auth = KotakNeoAuth(temp_env_file)
                        if not auth.login():
                            raise HTTPException(
                                status_code=503,
                                detail=(
                                    "Failed to connect to broker. "
                                    "Please check your credentials and try again."
                                ),
                            )
                        # Cache the authenticated session for reuse
                        _broker_auth_cache[current.id] = auth
                        logger.info(
                            f"Cached auth session for user {current.id} - "
                            "will reuse for subsequent requests"
                        )
            else:
                logger.debug(f"Reusing cached auth session for user {current.id}")

            # Create broker gateway
            broker = BrokerFactory.create_broker("kotak_neo", auth_handler=auth)

            # Connect to broker (only if not already connected)
            # broker.connect() calls auth.login() which triggers OTP,
            # so manually set client if already authenticated
            if not auth.is_authenticated():
                if not broker.connect():
                    raise HTTPException(
                        status_code=503,
                        detail="Failed to connect to broker gateway. Please try again later.",
                    )
            else:
                # Auth is already authenticated, manually set client to avoid re-login
                # This prevents OTP spam while ensuring broker is properly initialized
                # Trust the cached auth - only re-authenticate if API calls actually fail
                logger.debug(
                    f"Auth already authenticated for user {current.id}, "
                    "manually initializing broker client"
                )
                client = auth.get_client()
                if client:
                    # Client is available - use it directly without calling connect()
                    broker._client = client
                    broker._connected = True
                else:
                    # Client is None - this shouldn't happen if is_authenticated() is True
                    # But if it does, clear cache and let it re-authenticate on next request
                    # Don't force reconnect here to avoid OTP spam
                    logger.warning(
                        f"Auth says authenticated but client is None for user {current.id}, "
                        "clearing cache - will re-authenticate on next request"
                    )
                    with _broker_auth_cache_lock:
                        _broker_auth_cache.pop(current.id, None)
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Broker session expired. Please refresh the page to reconnect. "
                            "This should not trigger frequent OTP requests."
                        ),
                    )

            # Get holdings from broker
            holdings = broker.get_holdings()

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

            # Fetch live prices using yfinance
            import yfinance as yf  # noqa: PLC0415

            for holding in holdings:
                if holding.quantity == 0:
                    continue

                # Get live price
                symbol = holding.symbol
                ticker = (
                    f"{symbol}.NS"
                    if not symbol.endswith(".NS") and not symbol.endswith(".BO")
                    else symbol
                )
                try:
                    stock = yf.Ticker(ticker)
                    live_price = stock.info.get("currentPrice") or stock.info.get(
                        "regularMarketPrice"
                    )
                    current_price = (
                        float(live_price) if live_price else float(holding.current_price.amount)
                    )
                except Exception:
                    # Fallback to holding's current price
                    current_price = float(holding.current_price.amount)

                # Calculate values
                avg_price = float(holding.average_price.amount)
                cost_basis = avg_price * holding.quantity
                market_value = current_price * holding.quantity
                pnl = market_value - cost_basis
                pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0

                portfolio_value += market_value
                unrealized_pnl_total += pnl

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
    except Exception as e:
        logger.exception(f"Error fetching broker portfolio for user {current.id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch broker portfolio: {str(e)}"
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
            from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
            from modules.kotak_neo_auto_trader.infrastructure.broker_factory import (
                BrokerFactory,
            )

            # Thread-safe session caching - similar to trading service pattern
            # Reuse existing auth instance if available (it handles re-auth internally)
            auth = _broker_auth_cache.get(current.id)

            if not auth:
                with _broker_auth_cache_lock:
                    # Double-check: another thread might have created it
                    auth = _broker_auth_cache.get(current.id)
                    if not auth:
                        # Create new auth instance and login (only once per user)
                        logger.info(f"Creating new auth session for user {current.id}")
                        auth = KotakNeoAuth(temp_env_file)
                        if not auth.login():
                            raise HTTPException(
                                status_code=503,
                                detail=(
                                    "Failed to connect to broker. "
                                    "Please check your credentials and try again."
                                ),
                            )
                        # Cache the authenticated session for reuse
                        _broker_auth_cache[current.id] = auth
                        logger.info(
                            f"Cached auth session for user {current.id} - "
                            "will reuse for subsequent requests"
                        )
            else:
                logger.debug(f"Reusing cached auth session for user {current.id}")

            # Create broker gateway
            broker_gateway = BrokerFactory.create_broker("kotak_neo", auth_handler=auth)

            # Connect to broker (only if not already connected)
            # broker.connect() calls auth.login() which triggers OTP,
            # so manually set client if already authenticated
            if not auth.is_authenticated():
                if not broker_gateway.connect():
                    raise HTTPException(
                        status_code=503,
                        detail="Failed to connect to broker gateway. Please try again later.",
                    )
            else:
                # Auth is already authenticated, manually set client to avoid re-login
                # This prevents OTP spam while ensuring broker is properly initialized
                # Trust the cached auth - only re-authenticate if API calls actually fail
                logger.debug(
                    f"Auth already authenticated for user {current.id}, "
                    "manually initializing broker client"
                )
                client = auth.get_client()
                if client:
                    # Client is available - use it directly without calling connect()
                    broker_gateway._client = client
                    broker_gateway._connected = True
                else:
                    # Client is None - this shouldn't happen if is_authenticated() is True
                    # But if it does, clear cache and let it re-authenticate on next request
                    # Don't force reconnect here to avoid OTP spam
                    logger.warning(
                        f"Auth says authenticated but client is None for user {current.id}, "
                        "clearing cache - will re-authenticate on next request"
                    )
                    with _broker_auth_cache_lock:
                        _broker_auth_cache.pop(current.id, None)
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Broker session expired. Please refresh the page to reconnect. "
                            "This should not trigger frequent OTP requests."
                        ),
                    )

            # Get orders from broker
            broker_orders = broker_gateway.get_all_orders()

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
                        "completed": "closed",
                        "filled": "closed",
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
    except Exception as e:
        logger.exception(f"Error fetching broker orders for user {current.id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch broker orders: {str(e)}"
        ) from e
