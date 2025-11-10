"""
Authentication Module for Kotak Neo API
Handles login, logout, and session management
"""

import os
import threading
from dotenv import load_dotenv
from typing import Optional
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger


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

        self.consumer_key = os.getenv("KOTAK_CONSUMER_KEY", "")
        self.consumer_secret = os.getenv("KOTAK_CONSUMER_SECRET", "")
        self.mobile_number = os.getenv("KOTAK_MOBILE_NUMBER", "")
        self.password = os.getenv("KOTAK_PASSWORD", "")
        self.totp_secret = os.getenv("KOTAK_TOTP_SECRET", "")
        self.mpin = os.getenv("KOTAK_MPIN", "")
        self.environment = os.getenv("KOTAK_ENVIRONMENT", "prod")

        # Validate required credentials (TOTP or MPIN accepted for 2FA)
        required_fields = [
            self.consumer_key, self.consumer_secret,
            self.mobile_number, self.password
        ]

        if not all(required_fields) or (not self.totp_secret and not self.mpin):
            missing = [name for field, name in zip(required_fields + [self.totp_secret or self.mpin], [
                "KOTAK_CONSUMER_KEY", "KOTAK_CONSUMER_SECRET",
                "KOTAK_MOBILE_NUMBER", "KOTAK_PASSWORD", "KOTAK_TOTP_SECRET or KOTAK_MPIN"
            ]) if not field]
            raise ValueError(f"Missing credentials: {', '.join(missing)}")

    def login(self) -> bool:
        """
        Perform complete login process.
        For long-running service, this is called ONCE at startup.
        """
        try:
            from neo_api_client import NeoAPI

            self.logger.info("Starting Kotak Neo API login process...")
            self.logger.info(f"Mobile: {self.mobile_number}")
            self.logger.info(f"Environment: {self.environment}")

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
            self.logger.info("Login completed successfully!")
            self.logger.info("Session will remain active for the entire trading day")
            return True

        except Exception as e:
            self.logger.error(f"Login failed with exception: {e}")
            return False

    def _initialize_client(self):
        """Initialize NeoAPI client"""
        try:
            from neo_api_client import NeoAPI

            client = NeoAPI(
                consumer_key=self.consumer_key,
                consumer_secret=self.consumer_secret,
                environment=self.environment,
                neo_fin_key="neotradeapi"
            )
            self.logger.info("NeoAPI client initialized successfully")
            return client

        except Exception as init_error:
            self.logger.error(f"Client initialization failed: {init_error}")
            return None

    def _perform_login(self) -> bool:
        """Perform username/password login"""
        try:
            self.logger.info("Attempting login...")
            login_response = self.client.login(
                mobilenumber=self.mobile_number,
                password=self.password
            )

            if login_response is None:
                self.logger.error("Login failed: No response from server")
                return False

            if isinstance(login_response, dict) and "error" in login_response:
                self.logger.error(f"Login failed: {login_response['error'][0]['message']}")
                return False

            self.logger.info("Login successful, proceeding with 2FA...")
            return True

        except Exception as e:
            self.logger.error(f"Login error: {e}")
            return False

    def _complete_2fa(self) -> bool:
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
                self.logger.debug("2FA session token extracted successfully")
            
            # Success (even if no token - session may already be active)
            return True
            
        except Exception as e:
            self.logger.error(f"2FA error: {e}")
            return False
    
    def _extract_error_from_response(self, response) -> Optional[str]:
        """Extract error message from 2FA response safely."""
        try:
            if isinstance(response, dict):
                err = response.get('error')
            elif hasattr(response, 'get') and callable(getattr(response, 'get', None)):
                err = response.get('error')
            else:
                return None
            
            if not err:
                return None
            
            # Handle list of errors
            if isinstance(err, list) and len(err) > 0:
                if isinstance(err[0], dict):
                    return err[0].get('message', str(err[0]))
                return str(err[0])
            
            return str(err)
            
        except Exception as e:
            self.logger.debug(f"Error extracting error from response: {e}")
            return None
    
    def _extract_token_from_response(self, response) -> Optional[str]:
        """Extract token from 2FA response safely."""
        try:
            # Try object attribute access first (SDK response object)
            if hasattr(response, 'data'):
                data_obj = response.data
                if data_obj and hasattr(data_obj, 'token'):
                    return data_obj.token
            
            # Try dict access (JSON response)
            data_field = None
            if isinstance(response, dict):
                data_field = response.get('data')
            elif hasattr(response, 'get') and callable(getattr(response, 'get', None)):
                data_field = response.get('data')
            
            if not data_field:
                return None
            
            # Extract token from data field
            if isinstance(data_field, dict):
                return data_field.get('token')
            elif hasattr(data_field, 'get') and callable(getattr(data_field, 'get', None)):
                return data_field.get('token')
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error extracting token from response: {e}")
            return None


    def force_relogin(self) -> bool:
        """
        Force a fresh login + 2FA (used when JWT expires) - THREAD-SAFE.
        
        IMPORTANT: Always creates a NEW client instance and properly cleans up old client.
        Uses lock to prevent concurrent re-authentication attempts from multiple threads.
        
        The issue: When JWT expires quickly (e.g., 13 seconds), the SDK's internal state
        can become corrupted. Creating a new client without cleanup can cause SDK to
        access None values internally, leading to 'NoneType' object has no attribute 'get' errors.
        """
        # Use lock to prevent concurrent re-auth attempts
        # This ensures only one thread performs re-auth at a time
        with self._client_lock:
            try:
                self.logger.info("Forcing fresh login...")
                
                # Step 1: Clean up old client first (if exists)
                # This clears SDK internal state that might be corrupted
                old_client = self.client
                if old_client:
                    try:
                        # Try to logout old client to clear SDK state
                        # Don't fail if logout fails (client might already be invalid)
                        old_client.logout()
                        self.logger.debug("Old client logged out successfully")
                    except Exception as logout_err:
                        # Logout might fail if client is already invalid - that's okay
                        self.logger.debug(f"Old client logout failed (expected if expired): {logout_err}")
                
                # Step 2: Reset authentication state
                self.is_logged_in = False
                self.session_token = None
                self.client = None
                
                # Step 3: ALWAYS create a new client (don't reuse stale clients)
                # This is critical: expired clients can cause SDK internal errors
                self.client = self._initialize_client()
                
                if not self.client:
                    self.logger.error("Failed to initialize new client for re-authentication")
                    return False
                
                # Step 4: Perform fresh login + 2FA
                # Add retry logic for 2FA in case SDK needs time to initialize
                if not self._perform_login():
                    return False
                
                # Retry 2FA up to 2 times if it fails with SDK errors
                max_2fa_retries = 2
                for attempt in range(max_2fa_retries):
                    if self._complete_2fa():
                        self.is_logged_in = True
                        self.logger.info("Re-authentication successful")
                        return True
                    
                    if attempt < max_2fa_retries - 1:
                        self.logger.warning(f"2FA failed, retrying ({attempt + 1}/{max_2fa_retries})...")
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
                
                return False
                
            except Exception as e:
                self.logger.error(f"Force re-login failed: {e}")
                # Reset state on failure
                self.is_logged_in = False
                self.session_token = None
                self.client = None
                return False

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
            logout_response = self.client.logout()
            self.is_logged_in = False
            self.session_token = None
            self.logger.info("Logout successful")
            return True

        except Exception as e:
            self.logger.warning(f"Logout failed: {e}")
            return False

    def get_client(self):
        """
        Get the authenticated client instance (thread-safe).
        
        Uses lock to prevent race conditions when multiple threads
        (e.g., from ThreadPoolExecutor in SellOrderManager) access
        the client simultaneously.

        Returns:
            NeoAPI client or None if not logged in
        """
        with self._client_lock:
            if not self.is_logged_in:
                self.logger.error("Not logged in. Please login first.")
                return None
            return self.client

    def get_session_token(self) -> Optional[str]:
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