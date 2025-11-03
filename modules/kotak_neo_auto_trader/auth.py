"""
Authentication Module for Kotak Neo API
Handles login, logout, and session management
"""

import os
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
            self.logger.warning(f"Client initialization warning: {init_error}")
            self.logger.info("Attempting to continue with login...")

            # Create client anyway - sometimes it still works
            from neo_api_client import NeoAPI
            return NeoAPI(
                consumer_key=self.consumer_key,
                consumer_secret=self.consumer_secret,
                environment=self.environment,
                neo_fin_key="neotradeapi"
            )

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
        """Complete 2FA authentication using MPIN from env (recommended by Kotak Neo)."""
        if not self.mpin:
            self.logger.error("MPIN not configured; set KOTAK_MPIN in kotak_neo.env for 2FA")
            return False
        try:
            self.logger.info("Using MPIN for 2FA")
            # Ensure client is available
            if not self.client:
                self.logger.error("No client available for 2FA")
                return False
            
            session_response = self.client.session_2fa(OTP=self.mpin)
            
            # Debug: log the response to see hsServerId
            import json
            self.logger.debug(f"2FA response: {json.dumps(session_response, indent=2, default=str)}")
            
            # Handle None response (can happen with cached sessions)
            if session_response is None:
                self.logger.debug("2FA returned None - session may already be active")
                return True  # Don't fail if already authenticated
            
            # Handle SDK error shape
            if isinstance(session_response, dict) and session_response.get('error'):
                err = session_response.get('error')
                try:
                    msg = err[0]['message'] if isinstance(err, list) and err else str(err)
                except Exception:
                    msg = str(err)
                self.logger.error(f"2FA failed: {msg}")
                return False
            
            # Extract session token when present
            if hasattr(session_response, 'data') and hasattr(session_response.data, 'token'):
                self.session_token = session_response.data.token
                self.logger.debug("2FA session token extracted from response.data.token")
            elif isinstance(session_response, dict) and 'data' in session_response:
                # Fix: Check if data field is None before accessing it
                data_field = session_response.get('data')
                if data_field is None:
                    self.logger.debug("2FA response data field is None - session may already be active")
                    return True  # Don't fail if data is None (cached session)
                
                token = data_field.get('token') if isinstance(data_field, dict) else None
                if token:
                    self.session_token = token
                    self.logger.debug("2FA session token extracted from response['data']['token']")
            
            return True
        except Exception as e:
            self.logger.error(f"2FA error: {e}")
            return False


    def force_relogin(self) -> bool:
        """Force a fresh login + 2FA (used when JWT expires)."""
        try:
            self.logger.info("Forcing fresh login...")
            if not self.client:
                self.client = self._initialize_client()
            if not self._perform_login():
                return False
            if not self._complete_2fa():
                return False
            self.is_logged_in = True
            self.logger.info("Re-authentication successful")
            return True
        except Exception as e:
            self.logger.error(f"Force re-login failed: {e}")
            return False

    def _response_requires_2fa(self, resp) -> bool:
        """Check if response indicates 2FA is required."""
        try:
            s = str(resp)
            return '2fa' in s.lower() or 'complete the 2fa' in s.lower()
        except Exception:
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
        Get the authenticated client instance

        Returns:
            NeoAPI client or None if not logged in
        """
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