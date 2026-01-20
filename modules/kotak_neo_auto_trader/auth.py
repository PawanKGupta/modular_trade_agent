"""
Authentication Module for Kotak Neo API
Handles login, logout, and session management
"""

import os
import socket
import sys
import threading
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from dotenv import load_dotenv

# IPv4 resolution control (scoped + configurable)
_original_getaddrinfo = socket.getaddrinfo
_FORCE_IPV4 = os.getenv("FORCE_IPV4", "1") not in ("0", "false", "False")
_BROKER_HOSTS_IPV4_ONLY = {
    "gw-napi.kotaksecurities.com",
}


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """
    Force IPv4-only DNS resolution for broker hosts when enabled.
    """
    if not _FORCE_IPV4:
        return _original_getaddrinfo(host, port, family, type, proto, flags)

    # If host matches broker hosts, force AF_INET
    if host in _BROKER_HOSTS_IPV4_ONLY:
        return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    # Otherwise, use normal resolution
    return _original_getaddrinfo(host, port, family, type, proto, flags)


# Apply IPv4-only resolution globally (but scoped to broker host)
socket.getaddrinfo = _ipv4_getaddrinfo

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import security utils after path setup (E402: import after sys.path modification is intentional)
from modules.kotak_neo_auto_trader.utils.security_utils import (  # noqa: E402
    sanitize_log_message,
)
from utils.logger import logger  # noqa: E402


class KotakNeoAuth:
    """
    Authentication handler for Kotak Neo API
    """

    def __init__(self, config_file: str = "modules/kotak_neo_auto_trader/kotak_neo.env"):
        """
        Initialize authentication module

        Args:
            config_file (str): Path to environment configuration file
        """
        self.config_file = config_file
        self.client = None
        self.session_token = None
        self.is_logged_in = False

        # Phase -1: Session validity tracking
        # Track when session was created and its TTL (Time To Live)
        # JWT tokens from Kotak Neo API expire after ~1 hour
        # Use 55 minutes as safety margin to proactively re-auth before expiry
        self.session_created_at: float | None = None
        self.session_ttl: int = 3300  # 55 minutes (safety margin for 1-hour JWT)

        # Thread lock for thread-safe client access
        # Prevents race conditions when multiple threads use the same client
        self._client_lock = threading.Lock()

        # Use existing project logger
        self.logger = logger

        # Load credentials
        self._load_credentials()

        self.logger.info(f"KotakNeoAuth initialized with environment: {self.environment}")

    def _load_credentials(self):
        """Load credentials from environment file"""
        load_dotenv(self.config_file)

        # Ensure all credentials are strings (not None) to prevent SDK concatenation errors
        # os.getenv can return None if the variable is set to empty string in some cases
        self.consumer_key = str(os.getenv("KOTAK_CONSUMER_KEY", "") or "")
        self.consumer_secret = str(os.getenv("KOTAK_CONSUMER_SECRET", "") or "")
        self.mobile_number = str(os.getenv("KOTAK_MOBILE_NUMBER", "") or "")
        self.password = str(os.getenv("KOTAK_PASSWORD", "") or "")
        self.totp_secret = str(os.getenv("KOTAK_TOTP_SECRET", "") or "")
        self.mpin = str(os.getenv("KOTAK_MPIN", "") or "")
        self.environment = str(os.getenv("KOTAK_ENVIRONMENT", "prod") or "prod")

        # Validate required credentials (TOTP or MPIN accepted for 2FA)
        required_fields = [
            self.consumer_key,
            self.consumer_secret,
            self.mobile_number,
            self.password,
        ]

        if not all(required_fields) or (not self.totp_secret and not self.mpin):
            missing = [
                name
                for field, name in zip(
                    required_fields + [self.totp_secret or self.mpin],
                    [
                        "KOTAK_CONSUMER_KEY",
                        "KOTAK_CONSUMER_SECRET",
                        "KOTAK_MOBILE_NUMBER",
                        "KOTAK_PASSWORD",
                        "KOTAK_TOTP_SECRET or KOTAK_MPIN",
                    ],
                    strict=False,
                )
                if not field
            ]
            raise ValueError(f"Missing credentials: {', '.join(missing)}")

    def login(self) -> bool:
        """
        Perform complete login process.
        For long-running service, this is called ONCE at startup.
        """
        # Suppress stdout/stderr for entire login process to prevent token printing
        stdout_capture = StringIO()
        stderr_capture = StringIO()

        try:
            self.logger.info("Starting Kotak Neo API login process...")
            self.logger.info(f"Mobile: {self.mobile_number}")
            self.logger.info(f"Environment: {self.environment}")

            # Suppress output during entire login process
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # Initialize client
                self.client = self._initialize_client()
                if not self.client:
                    return False

                # Perform login + 2FA
                if not self._perform_login():
                    return False
                if not self._complete_2fa():
                    return False

                self.is_logged_in = True
                self.session_created_at = time.time()  # Phase -1: Track session creation time
                self.logger.info("Login completed successfully!")
                self.logger.info("Session will remain active for the entire trading day")
                return True

        except Exception as e:
            # Sanitize error message in case it contains token info
            # Handle case where str(e) might return None or fail
            try:
                error_str = str(e) if e is not None else "Unknown error"
                if error_str is None:
                    error_str = "Unknown error (exception string is None)"
                error_msg = sanitize_log_message(error_str)
            except Exception as sanitize_error:
                # Fallback if sanitization fails
                error_msg = f"Error during login (sanitization failed: {sanitize_error})"
            self.logger.error(f"Login failed with exception: {error_msg}")
            return False
        finally:
            # Check if there was any captured output and sanitize it (for debugging only)
            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()
            if stdout_output or stderr_output:
                combined_output = stdout_output + stderr_output
                sanitized = sanitize_log_message(combined_output)
                if sanitized and sanitized.strip():
                    # Only log at debug level and truncate to prevent token leakage
                    self.logger.debug(f"Login process output (sanitized): {sanitized[:200]}")

    def _initialize_client(self):
        """Initialize NeoAPI client"""
        try:
            from neo_api_client import NeoAPI  # noqa: PLC0415

            # Ensure all credentials are strings (not None) before passing to SDK
            # SDK may try to concatenate strings internally, causing TypeError if None
            consumer_key = str(self.consumer_key) if self.consumer_key is not None else ""
            consumer_secret = str(self.consumer_secret) if self.consumer_secret is not None else ""
            environment = str(self.environment) if self.environment is not None else "prod"

            if not consumer_key or not consumer_secret:
                self.logger.error(
                    "Client initialization failed: "
                    "consumer_key or consumer_secret is missing or empty"
                )
                return None

            # Output suppression is handled at login() level
            client = NeoAPI(
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
                environment=environment,
                neo_fin_key="neotradeapi",
            )

            self.logger.info("NeoAPI client initialized successfully")
            return client

        except TypeError as te:
            # Handle SDK internal errors where it tries to concatenate None with string
            error_msg = str(te) if te else "Type error in SDK"
            if "NoneType" in error_msg or "concatenate" in error_msg.lower():
                self.logger.error(
                    "Client initialization error: SDK received None value. "
                    "Please check that KOTAK_CONSUMER_KEY and "
                    "KOTAK_CONSUMER_SECRET are set correctly."
                )
            else:
                self.logger.error(f"Client initialization error (TypeError): {error_msg}")
            return None
        except Exception as init_error:
            self.logger.error(f"Client initialization failed: {init_error}")
            return None

    def _perform_login(self) -> bool:
        """Perform username/password login"""
        try:
            self.logger.info("Attempting login...")

            # Ensure credentials are strings (not None) before passing to SDK
            # SDK may try to concatenate strings internally, causing TypeError if None
            mobile = str(self.mobile_number) if self.mobile_number is not None else ""
            password = str(self.password) if self.password is not None else ""

            # Validate credentials before attempting login
            if not mobile or not password:
                self.logger.error("Login failed: Mobile number or password is missing or empty")
                return False

            # Additional validation: ensure client has valid credentials
            if not self.client:
                self.logger.error("Login failed: Client is not initialized")
                return False

            # Log credential status for debugging (without exposing actual values)
            self.logger.debug(
                f"Login attempt - Mobile length: {len(mobile)}, "
                f"Password length: {len(password)}, "
                f"Consumer key set: {bool(self.consumer_key)}, "
                f"Consumer secret set: {bool(self.consumer_secret)}"
            )

            # Output suppression is handled at login() level
            login_response = self.client.login(mobilenumber=mobile, password=password)

            if login_response is None:
                self.logger.error("Login failed: No response from server")
                return False

            if isinstance(login_response, dict) and "error" in login_response:
                error_msg = "Unknown error"
                try:
                    if (
                        isinstance(login_response["error"], list)
                        and len(login_response["error"]) > 0
                    ):
                        if isinstance(login_response["error"][0], dict):
                            error_msg = login_response["error"][0].get("message", "Unknown error")
                        else:
                            error_msg = str(login_response["error"][0])
                    else:
                        error_msg = str(login_response["error"])
                except Exception:
                    error_msg = "Unknown error (failed to parse error message)"
                self.logger.error(f"Login failed: {error_msg}")
                return False

            self.logger.info("Login successful, proceeding with 2FA...")
            return True

        except TypeError as te:
            # Handle SDK internal errors where it tries to concatenate None with string
            error_msg = str(te) if te else "Type error in SDK"
            if "NoneType" in error_msg or "concatenate" in error_msg.lower():
                # Log which credentials might be None for debugging
                cred_status = {
                    "mobile_number": "set" if mobile else "missing/empty",
                    "password": "set" if password else "missing/empty",
                    "consumer_key": "set" if self.consumer_key else "missing/empty",
                    "consumer_secret": "set" if self.consumer_secret else "missing/empty",
                }
                self.logger.error(
                    f"Login error: SDK received None value. "
                    f"Credential status: {cred_status}. "
                    "Please check that all credentials are set correctly in kotak_neo.env"
                )
            else:
                self.logger.error(f"Login error (TypeError): {error_msg}")
            return False
        except Exception as e:
            # Sanitize error message to avoid logging sensitive info
            try:
                error_str = str(e) if e is not None else "Unknown error"
                if error_str is None:
                    error_str = "Unknown error (exception string is None)"
                error_msg = sanitize_log_message(error_str)
            except Exception:
                error_msg = "Unknown error (failed to format error message)"
            self.logger.error(f"Login error: {error_msg}")
            return False

    def _complete_2fa(self) -> bool:  # noqa: PLR0911
        """
        Complete 2FA authentication using MPIN from env (recommended by Kotak Neo).

        Handles various response formats and SDK exceptions gracefully.
        """
        if not self.mpin:
            self.logger.error("MPIN not configured; set KOTAK_MPIN in kotak_neo.env for 2FA")
            return False

        if not self.client:
            self.logger.error("No client available for 2FA")
            return False

        try:
            self.logger.info("Using MPIN for 2FA")

            # Call session_2fa with comprehensive error handling
            # Output suppression is handled at login() level
            try:
                session_response = self.client.session_2fa(OTP=self.mpin)
            except Exception as session_err:
                error_msg = str(session_err).lower()
                # Handle SDK internal errors (NoneType.get) - treat as session already active
                if "nonetype" in error_msg and "get" in error_msg:
                    self.logger.warning(
                        f"2FA SDK internal error (NoneType.get): {session_err} - "
                        "treating as session already active"
                    )
                    return True
                # Other exceptions are real failures
                self.logger.error(f"2FA call failed: {session_err}")
                return False

            # Handle None response (session may already be active)
            if session_response is None:
                self.logger.debug("2FA returned None - session may already be active")
                return True

            # Check for error in response
            error = self._extract_error_from_response(session_response)
            if error:
                self.logger.error(f"2FA failed: {error}")
                return False

            # Extract session token if present
            token = self._extract_token_from_response(session_response)
            if token:
                self.session_token = token
                # Don't log the token itself - just confirm extraction
                self.logger.debug("2FA session token extracted successfully")

            # Success (even if no token - session may already be active)
            return True

        except Exception as e:
            self.logger.error(f"2FA error: {e}")
            return False

    def _extract_error_from_response(self, response) -> str | None:
        """Extract error message from 2FA response safely."""
        try:
            if isinstance(response, dict):
                err = response.get("error")
            elif hasattr(response, "get") and callable(getattr(response, "get", None)):
                err = response.get("error")
            else:
                return None

            if not err:
                return None

            # Handle list of errors
            if isinstance(err, list) and len(err) > 0:
                if isinstance(err[0], dict):
                    return err[0].get("message", str(err[0]))
                return str(err[0])

            return str(err)

        except Exception as e:
            self.logger.debug(f"Error extracting error from response: {e}")
            return None

    def _extract_token_from_response(self, response) -> str | None:
        """Extract token from 2FA response safely."""
        try:
            # Try object attribute access first (SDK response object)
            if hasattr(response, "data"):
                data_obj = response.data
                if data_obj and hasattr(data_obj, "token"):
                    return data_obj.token

            # Try dict access (JSON response)
            data_field = None
            if isinstance(response, dict):
                data_field = response.get("data")
            elif hasattr(response, "get") and callable(getattr(response, "get", None)):
                data_field = response.get("data")

            if not data_field:
                return None

            # Extract token from data field (try both 'token' and 'access_token')
            if isinstance(data_field, dict):
                token = data_field.get("token") or data_field.get("access_token")
                return token
            elif hasattr(data_field, "get") and callable(getattr(data_field, "get", None)):
                token = data_field.get("token") or data_field.get("access_token")
                return token

            return None

        except Exception as e:
            # Sanitize error message in case it contains token info
            # Handle case where str(e) might return None or fail
            try:
                error_str = str(e) if e is not None else "Unknown error"
                if error_str is None:
                    error_str = "Unknown error (exception string is None)"
                error_msg = sanitize_log_message(error_str)
            except Exception as sanitize_error:
                # Fallback if sanitization fails
                error_msg = f"Error extracting token (sanitization failed: {sanitize_error})"
            self.logger.debug(f"Error extracting token from response: {error_msg}")
            return None

    def _force_relogin_impl(self) -> bool:
        """
        Internal implementation of force re-login (without locks).

        IMPORTANT: This method assumes self._client_lock is already held by the caller.
        Do NOT call this method directly unless you hold the lock. Use force_relogin() instead.

        Phase -1 CRITICAL FIX: Keep is_logged_in = True during re-auth attempt.
        Only set False if re-auth completely fails. This prevents Web API thread
        from clearing session while re-auth is in progress, which causes OTP spam.

        The issue: When JWT expires quickly (e.g., 13 seconds), the SDK's internal state
        can become corrupted. Creating a new client without cleanup can cause SDK to
        access None values internally, leading to 'NoneType' object has no attribute 'get' errors.
        """
        # Track caller for debugging
        caller = "unknown"
        try:
            stack = traceback.extract_stack()
            if len(stack) >= 2:
                caller_frame = stack[-2]
                caller = f"{caller_frame.filename.split('/')[-1]}:{caller_frame.lineno}"
        except Exception:
            pass

        reauth_start = time.time()
        self.logger.info(
            f"[REAUTH_DEBUG] _force_relogin_impl() STARTED at {time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"from {caller}"
        )

        try:
            self.logger.info("Forcing fresh login...")

            # Step 1: Clean up old client first (if exists)
            # This clears SDK internal state that might be corrupted
            cleanup_start = time.time()
            old_client = self.client
            if old_client:
                try:
                    # Try to logout old client to clear SDK state
                    # Don't fail if logout fails (client might already be invalid)
                    old_client.logout()
                    cleanup_duration = time.time() - cleanup_start
                    self.logger.debug(
                        f"[REAUTH_DEBUG] Old client logged out successfully "
                        f"(took {cleanup_duration:.2f}s)"
                    )
                except Exception as logout_err:
                    cleanup_duration = time.time() - cleanup_start
                    # Logout might fail if client is already invalid - that's okay
                    self.logger.debug(
                        f"[REAUTH_DEBUG] Old client logout failed (expected if expired) "
                        f"after {cleanup_duration:.2f}s: {logout_err}"
                    )
            else:
                self.logger.debug("[REAUTH_DEBUG] No old client to cleanup")

            # Phase -1 CRITICAL FIX: Don't set is_logged_in = False here!
            # Keep it True during re-auth attempt to prevent Web API thread
            # from clearing session. Only set False if re-auth completely fails

            # Step 2: Create new client (but keep is_logged_in = True)
            init_start = time.time()
            self.client = self._initialize_client()
            init_duration = time.time() - init_start
            self.logger.info(
                f"[REAUTH_DEBUG] Client initialization {'successful' if self.client else 'failed'} "
                f"(took {init_duration:.2f}s)"
            )

            if not self.client:
                # Only set False if client initialization fails
                self.is_logged_in = False
                self.session_token = None
                total_duration = time.time() - reauth_start
                self.logger.error(
                    f"[REAUTH_DEBUG] FAILED: Client initialization failed "
                    f"(total duration: {total_duration:.2f}s)"
                )
                return False

            # Step 3: Perform fresh login + 2FA
            login_start = time.time()
            login_success = self._perform_login()
            login_duration = time.time() - login_start
            self.logger.info(
                f"[REAUTH_DEBUG] Login {'successful' if login_success else 'failed'} "
                f"(took {login_duration:.2f}s)"
            )

            if not login_success:
                # Only set False if login fails
                self.is_logged_in = False
                self.session_token = None
                self.client = None
                total_duration = time.time() - reauth_start
                self.logger.error(
                    f"[REAUTH_DEBUG] FAILED: Login failed (total duration: {total_duration:.2f}s)"
                )
                return False

            # Step 4: Complete 2FA (with retry logic)
            max_2fa_retries = 2
            for attempt in range(max_2fa_retries):
                tfa_start = time.time()
                tfa_success = self._complete_2fa()
                tfa_duration = time.time() - tfa_start

                if tfa_success:
                    # Success - keep is_logged_in = True, update timestamp
                    total_duration = time.time() - reauth_start
                    self.is_logged_in = True
                    self.session_created_at = time.time()  # Phase -1: Reset session timer
                    self.logger.info(
                        f"[REAUTH_DEBUG] SUCCESS: Re-authentication completed in {total_duration:.2f}s "
                        f"(2FA attempt {attempt + 1} took {tfa_duration:.2f}s)"
                    )
                    self.logger.info("Re-authentication successful")
                    return True

                self.logger.warning(
                    f"[REAUTH_DEBUG] 2FA failed on attempt {attempt + 1}/{max_2fa_retries} "
                    f"(took {tfa_duration:.2f}s)"
                )

                if attempt < max_2fa_retries - 1:
                    self.logger.warning(
                        f"2FA failed, retrying ({attempt + 1}/{max_2fa_retries})..."
                    )
                    # Create another fresh client if 2FA fails
                    self.client = None
                    self.client = self._initialize_client()
                    if not self.client:
                        break
                    # Re-login before retrying 2FA
                    if not self._perform_login():
                        break
                else:
                    self.logger.error("2FA failed after retries")

            # Re-auth failed completely - only now set False
            total_duration = time.time() - reauth_start
            self.logger.error(
                f"[REAUTH_DEBUG] FAILED: Re-auth failed after {total_duration:.2f}s from {caller}"
            )
            self.is_logged_in = False
            self.session_token = None
            self.client = None
            return False

        except Exception as e:
            total_duration = time.time() - reauth_start
            self.logger.error(
                f"[REAUTH_DEBUG] EXCEPTION in _force_relogin_impl() after {total_duration:.2f}s: {e}",
                exc_info=True,
            )
            # Reset state on failure
            self.is_logged_in = False
            self.session_token = None
            self.client = None
            return False

    def force_relogin(self) -> bool:
        """
        Force a fresh login + 2FA (used when JWT expires) - THREAD-SAFE.

        IMPORTANT: Always creates a NEW client instance and properly cleans up old client.
        Uses lock to prevent concurrent re-authentication attempts from multiple threads.

        This is the public method that acquires the lock before calling the implementation.
        """
        # Track caller for debugging
        caller = "unknown"
        try:
            stack = traceback.extract_stack()
            if len(stack) >= 2:
                caller_frame = stack[-2]
                caller = f"{caller_frame.filename.split('/')[-1]}:{caller_frame.lineno}"
        except Exception:
            pass

        self.logger.info(
            f"[REAUTH_DEBUG] force_relogin() called from {caller} "
            f"at {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        # Use lock to prevent concurrent re-auth attempts
        # This ensures only one thread performs re-auth at a time
        lock_start = time.time()
        with self._client_lock:
            lock_acquired_duration = time.time() - lock_start
            if lock_acquired_duration > 0.1:
                self.logger.warning(
                    f"[REAUTH_DEBUG] Waited {lock_acquired_duration:.2f}s to acquire lock "
                    f"(another thread was re-authenticating)"
                )
            return self._force_relogin_impl()

    def logout(self) -> bool:
        """
        Logout from the session

        Returns:
            bool: True if logout successful, False otherwise
        """
        if not self.client:
            self.logger.warning("No active session to logout")
            return False

        try:
            self.client.logout()
            self.is_logged_in = False
            self.session_token = None
            self.logger.info("Logout successful")
            return True

        except Exception as e:
            self.logger.warning(f"Logout failed: {e}")
            return False

    def is_session_valid(self) -> bool:
        """
        Check if session is still valid (not expired).

        Phase -1: Proactively check session validity based on TTL.
        This allows us to re-authenticate before JWT expires, preventing
        API call failures.

        Returns:
            bool: True if session is valid, False if expired
        """
        if not self.is_logged_in:
            return False
        if self.session_created_at is None:
            # Legacy session without timestamp tracking - assume valid
            # This handles sessions created before Phase -1 implementation
            return True
        elapsed = time.time() - self.session_created_at
        return elapsed < self.session_ttl

    def get_client(self):
        """
        Get the authenticated client instance (thread-safe).

        Phase -1: Proactively check session validity before returning client.
        If session is expired, trigger re-authentication automatically.

        Uses lock to prevent race conditions when multiple threads
        (e.g., from ThreadPoolExecutor in SellOrderManager) access
        the client simultaneously.

        Returns:
            NeoAPI client or None if not logged in
        """
        # Track caller for debugging
        caller = "unknown"
        try:
            stack = traceback.extract_stack()
            if len(stack) >= 2:
                caller_frame = stack[-2]
                caller = f"{caller_frame.filename.split('/')[-1]}:{caller_frame.lineno}"
        except Exception:
            pass

        get_client_start = time.time()

        with self._client_lock:
            # Check session validity (TTL-based)
            is_valid = self.is_session_valid()
            session_age = None
            ttl_remaining = None

            if self.session_created_at:
                session_age = time.time() - self.session_created_at
                ttl_remaining = self.session_ttl - session_age

            self.logger.debug(
                f"[REAUTH_DEBUG] get_client() called from {caller}: "
                f"is_session_valid()={is_valid}, "
                f"session_age={session_age:.1f}s, "
                f"ttl_remaining={ttl_remaining:.1f}s, "
                f"is_logged_in={self.is_logged_in}"
            )

            # Phase -1: Proactively check session validity
            if not is_valid:
                self.logger.warning(
                    f"[REAUTH_DEBUG] Session expired (TTL-based): "
                    f"session_age={session_age:.1f}s, ttl={self.session_ttl}s, "
                    f"forcing re-login from {caller}"
                )
                # Call implementation directly since we already hold the lock
                # This prevents deadlock (force_relogin() would try to acquire lock again)
                reauth_start = time.time()
                reauth_success = self._force_relogin_impl()
                reauth_duration = time.time() - reauth_start

                if reauth_success:
                    total_duration = time.time() - get_client_start
                    self.logger.info(
                        f"[REAUTH_DEBUG] Re-auth successful in {reauth_duration:.2f}s "
                        f"(get_client() total: {total_duration:.2f}s, triggered from {caller})"
                    )
                else:
                    total_duration = time.time() - get_client_start
                    self.logger.error(
                        f"[REAUTH_DEBUG] Re-auth failed after {reauth_duration:.2f}s "
                        f"(get_client() total: {total_duration:.2f}s, triggered from {caller})"
                    )

                if reauth_duration > 10.0:
                    self.logger.warning(
                        f"[REAUTH_DEBUG] WARNING: Re-auth took {reauth_duration:.2f}s - "
                        f"this may cause database connection leaks if called during request! "
                        f"(caller: {caller})"
                    )

                if not reauth_success:
                    return None
            elif not self.is_logged_in:
                total_duration = time.time() - get_client_start
                self.logger.error(
                    f"[REAUTH_DEBUG] Not logged in from {caller} "
                    f"(get_client() took {total_duration:.2f}s)"
                )
                return None
            else:
                # Session is valid by TTL, but JWT might still be expired
                # This is logged for tracking - actual JWT expiry will be detected on API calls
                total_duration = time.time() - get_client_start
                if total_duration > 0.1:
                    self.logger.debug(
                        f"[REAUTH_DEBUG] Session valid (TTL), returning client from {caller} "
                        f"(took {total_duration:.2f}s). "
                        "Note: JWT may still be expired and will trigger re-auth on API calls."
                    )

            return self.client

    def get_session_token(self) -> str | None:
        """
        Get current session token

        Returns:
            str: Session token or None if not logged in
        """
        return self.session_token if self.is_logged_in else None

    def is_authenticated(self) -> bool:
        """
        Check if currently authenticated

        Returns:
            bool: True if authenticated, False otherwise
        """
        return self.is_logged_in
