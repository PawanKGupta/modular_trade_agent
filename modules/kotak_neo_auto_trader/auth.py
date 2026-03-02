"""
Authentication Module for Kotak Neo API
Handles login, logout, and session management
"""

import os
import re
import socket
import sys
import threading
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from dotenv import load_dotenv

try:
    import pyotp  # type: ignore[import]
except ImportError:
    pyotp = None

from modules.kotak_neo_auto_trader.infrastructure.clients.kotak_rest_client import KotakRestClient

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
        # Backward compatibility: older code expects `auth.client`
        self.client = None
        self.session_token: str | None = None  # Session token (Auth) from tradeApiValidate
        self.base_url: str | None = None  # baseUrl from tradeApiValidate
        self.trade_sid: str | None = None  # session sid (Sid) from tradeApiValidate
        self.is_logged_in = False
        self._rest_client: KotakRestClient | None = None

        # Phase -1: Session validity tracking
        # Track when session was created and its TTL (Time To Live)
        # JWT tokens from Kotak Neo API expire after ~1 hour
        # Use 55 minutes as safety margin to proactively re-auth before expiry
        self.session_created_at: float | None = None
        self.session_ttl: int = 3300  # 55 minutes (safety margin for 1-hour JWT)

        # Thread lock for thread-safe client access
        # Prevents race conditions when multiple threads use the same session
        self._client_lock = threading.Lock()

        # Use existing project logger
        self.logger = logger

        # Load credentials
        self._load_credentials()

        self.logger.info(f"KotakNeoAuth initialized with environment: {self.environment}")

    def _load_credentials(self):
        """Load credentials from environment file"""
        load_dotenv(self.config_file)

        # Ensure all credentials are strings (not None)
        # For REST APIs we map:
        # - consumer_key -> API key used in Authorization header (access token)
        # - consumer_secret -> UCC (client code)
        self.consumer_key = str(os.getenv("KOTAK_CONSUMER_KEY", "") or "")
        self.consumer_secret = str(os.getenv("KOTAK_CONSUMER_SECRET", "") or "")
        self.mobile_number = str(os.getenv("KOTAK_MOBILE_NUMBER", "") or "")
        self.password = str(os.getenv("KOTAK_PASSWORD", "") or "")
        self.totp_secret = str(os.getenv("KOTAK_TOTP_SECRET", "") or "")
        self.mpin = str(os.getenv("KOTAK_MPIN", "") or "")
        self.environment = str(os.getenv("KOTAK_ENVIRONMENT", "prod") or "prod")

        # Validate base credentials at init time.
        # TOTP secret is validated at login-time to keep non-login code paths testable.
        required_fields = [
            self.consumer_key,
            self.consumer_secret,
            self.mobile_number,
            self.mpin,
        ]

        if not all(required_fields):
            missing = [
                name
                for field, name in zip(
                    required_fields,
                    ["KOTAK_CONSUMER_KEY", "KOTAK_CONSUMER_SECRET (UCC/client code)", "KOTAK_MOBILE_NUMBER", "KOTAK_MPIN"],
                    strict=False,
                )
                if not field
            ]
            raise ValueError(f"Missing credentials: {', '.join(missing)}")

    def _perform_rest_login(self) -> bool:
        """
        Perform REST-based login using Kotak tradeApiLogin + tradeApiValidate.

        Uses:
        - consumer_key      -> Authorization header
        - consumer_secret   -> UCC/client code
        - mobile_number     -> mobileNumber
        - totp_secret       -> generates TOTP for Step 1
        - mpin              -> MPIN for Step 2
        """
        if not pyotp:
            self.logger.error(
                "pyotp is not installed; cannot generate TOTP for Kotak REST login. "
                "Install pyotp or configure alternative TOTP generation."
            )
            return False

        api_key = self.consumer_key.strip()
        ucc = self.consumer_secret.strip()
        mobile = self.mobile_number.strip()
        mpin = self.mpin.strip()
        totp_secret = self.totp_secret.strip()

        if not api_key or not ucc or not mobile or not mpin or not totp_secret:
            self.logger.error("REST login failed: missing required credentials")
            return False

        def _kotak_error_message(payload: dict, fallback: str) -> str:
            for key in ("message", "emsg", "error", "errorDescription", "stat"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return fallback

        try:
            # Step 1: tradeApiLogin (view token)
            # Normalize secret to support user-entered spaces/hyphens.
            normalized_totp_secret = re.sub(r"[\s\-]", "", totp_secret).upper()
            try:
                totp_code = pyotp.TOTP(normalized_totp_secret).now()
            except Exception as totp_err:  # noqa: BLE001
                self.logger.error(
                    "REST login failed: invalid KOTAK_TOTP_SECRET format. "
                    "Expected Base32 secret key (not the 6-digit OTP code). "
                    f"Details: {totp_err}"
                )
                return False

            url_login = "https://mis.kotaksecurities.com/login/1.0/tradeApiLogin"
            headers_login = {
                "Authorization": api_key,
                "neo-fin-key": "neotradeapi",
                "Content-Type": "application/json",
            }
            payload_login = {
                "mobileNumber": mobile.strip(),
                "ucc": ucc,
                "totp": totp_code,
            }

            import requests
            import json

            resp_login = requests.post(url_login, headers=headers_login, data=json.dumps(payload_login), timeout=10.0)
            data_login = resp_login.json()
            if (
                resp_login.status_code != 200
                or data_login.get("status") == "error"
                or str(data_login.get("stat", "")).lower() == "not_ok"
            ):
                msg = _kotak_error_message(data_login, "Login failed (Step 1)")
                self.logger.error(f"REST login failed at Step 1: {msg}")
                return False

            view_data = data_login.get("data") or {}
            view_sid = view_data.get("sid")
            view_token = view_data.get("token")
            if not view_sid or not view_token:
                self.logger.error("REST login failed: missing sid/token in Step 1 response")
                return False

            # Step 2: tradeApiValidate (MPIN)
            url_validate = "https://mis.kotaksecurities.com/login/1.0/tradeApiValidate"
            headers_validate = {
                "Authorization": api_key,
                "neo-fin-key": "neotradeapi",
                "Content-Type": "application/json",
                "sid": view_sid,
                "Auth": view_token,
            }
            payload_validate = {"mpin": mpin}

            resp_validate = requests.post(
                url_validate,
                headers=headers_validate,
                data=json.dumps(payload_validate),
                timeout=10.0,
            )
            data_validate = resp_validate.json()
            if (
                resp_validate.status_code != 200
                or data_validate.get("status") == "error"
                or str(data_validate.get("stat", "")).lower() == "not_ok"
            ):
                msg = _kotak_error_message(data_validate, "Login failed (Step 2)")
                self.logger.error(f"REST login failed at Step 2 (MPIN validation): {msg}")
                return False

            trade_data = data_validate.get("data") or {}
            base_url = trade_data.get("baseUrl")
            trade_token = trade_data.get("token")
            trade_sid = trade_data.get("sid")
            if not base_url or not trade_token or not trade_sid:
                self.logger.error(
                    "REST login failed: missing baseUrl/token/sid in Step 2 response"
                )
                return False

            # Store session token and base URL for later use by REST clients
            self.session_token = trade_token
            self.base_url = base_url  # type: ignore[attr-defined]
            self.trade_sid = trade_sid  # type: ignore[attr-defined]
            self._rest_client = None  # Reset client cache on new login
            self.client = None  # Reset compatibility attribute on new login

            self.logger.info("Kotak REST login completed successfully")
            return True

        except Exception as e:  # noqa: BLE001
            try:
                error_str = str(e) if e is not None else "Unknown error"
                if error_str is None:
                    error_str = "Unknown error (exception string is None)"
                error_msg = sanitize_log_message(error_str)
            except Exception:
                error_msg = "Unknown error (failed to format REST login error)"
            self.logger.error(f"REST login error: {error_msg}")
            return False

    # Compatibility hooks used by older tests and call-sites.
    # These wrappers remain REST-first and do not introduce SDK dependencies.
    def _initialize_client(self):
        return self.client

    def _perform_login(self) -> bool:
        return self._perform_rest_login()

    def _complete_2fa(self) -> bool:
        return True

    def get_rest_client(self) -> KotakRestClient:
        """
        Get a REST client bound to the current authenticated session.
        """
        if not self.is_authenticated():
            raise ConnectionError("Not authenticated")
        if not self.base_url or not self.session_token or not self.trade_sid:
            raise ConnectionError("Missing REST session details (base_url/session_token/trade_sid)")

        if self._rest_client is None:
            self._rest_client = KotakRestClient(
                base_url=self.base_url,
                session_token=self.session_token,
                session_sid=self.trade_sid,
                access_token=self.consumer_key,
            )
            self.client = self._rest_client
        return self._rest_client

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
                compat_client = self._initialize_client()
                if compat_client is not None and hasattr(compat_client, "session_2fa"):
                    try:
                        compat_client.session_2fa()
                        success = True
                    except Exception as e:  # noqa: BLE001
                        msg = str(e).lower()
                        # Historical SDK quirk: treat NoneType.get from session_2fa as
                        # already-authenticated success.
                        if "nonetype" in msg and "has no attribute 'get'" in msg:
                            success = True
                        else:
                            raise
                else:
                    success = self._perform_login()
                    if success:
                        success = self._complete_2fa()
                if not success:
                    return False
                if compat_client is not None:
                    self.client = compat_client

                self.is_logged_in = True
                self.session_created_at = time.time()  # Phase -1: Track session creation time
                self.logger.info("Login completed successfully via REST APIs!")
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
            self.logger.info("Forcing fresh REST login...")
            compat_client = self._initialize_client()
            success = self._perform_login()
            if success:
                success = self._complete_2fa()

            total_duration = time.time() - reauth_start

            if success:
                if compat_client is not None:
                    self.client = compat_client
                self.is_logged_in = True
                self.session_created_at = time.time()
                self.logger.info(
                    f"[REAUTH_DEBUG] SUCCESS: re-authentication completed in {total_duration:.2f}s"
                )
                return True

            self.is_logged_in = False
            self.session_token = None
            self.base_url = None
            self.trade_sid = None
            self._rest_client = None
            self.client = None
            self.logger.error(
                f"[REAUTH_DEBUG] FAILED: re-authentication failed after {total_duration:.2f}s"
            )
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
            self.base_url = None
            self.trade_sid = None
            self._rest_client = None
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
        # REST sessions can be cleared locally. (No SDK logout call.)
        self.is_logged_in = False
        self.session_token = None
        self.base_url = None
        self.trade_sid = None
        self._rest_client = None
        self.client = None
        self.logger.info("Logout successful (local session cleared)")
        return True

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
        Backward-compatible accessor (SDK removed).

        Historically this returned an SDK client. With REST migration, it returns a
        `KotakRestClient` bound to the current authenticated session.
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

            session_age_str = f"{session_age:.1f}s" if session_age is not None else "n/a"
            ttl_remaining_str = f"{ttl_remaining:.1f}s" if ttl_remaining is not None else "n/a"
            self.logger.debug(
                f"[REAUTH_DEBUG] get_client() called from {caller}: "
                f"is_session_valid()={is_valid}, "
                f"session_age={session_age_str}, "
                f"ttl_remaining={ttl_remaining_str}, "
                f"is_logged_in={self.is_logged_in}"
            )

            # Phase -1: Proactively check session validity
            if not is_valid:
                log_age = session_age if session_age is not None else -1.0
                self.logger.warning(
                    f"[REAUTH_DEBUG] Session expired (TTL-based): "
                    f"session_age={log_age:.1f}s, ttl={self.session_ttl}s, "
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

            if not self.is_logged_in:
                self.logger.error(f"[REAUTH_DEBUG] Not logged in from {caller}")
                return None

            try:
                return self.get_rest_client()
            except Exception as e:
                self.logger.error(f"Failed to build REST client: {e}")
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
