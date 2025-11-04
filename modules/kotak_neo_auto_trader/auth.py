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
                error = login_response.get('error')
                try:
                    # Handle error as list or dict
                    if isinstance(error, list) and len(error) > 0:
                        error_item = error[0]
                        if isinstance(error_item, dict):
                            msg = error_item.get('message', str(error_item))
                        elif error_item is not None:
                            msg = str(error_item)
                        else:
                            msg = "Unknown error (None in error list)"
                    elif isinstance(error, dict):
                        msg = error.get('message', str(error))
                    else:
                        msg = str(error) if error is not None else "Unknown error"
                except Exception as parse_error:
                    self.logger.warning(f"Error parsing login error response: {parse_error}")
                    msg = str(error) if error is not None else "Unknown error"
                self.logger.error(f"Login failed: {msg}")
                return False

            self.logger.info("Login successful, proceeding with 2FA...")
            return True

        except Exception as e:
            self.logger.error(f"Login error: {e}")
            import traceback
            self.logger.debug(f"Login error traceback: {traceback.format_exc()}")
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
            
            # Debug: log the response type and content (CRITICAL for production debugging)
            self.logger.info(f"2FA response type: {type(session_response)}")
            self.logger.info(f"2FA response is None: {session_response is None}")
            self.logger.info(f"2FA response has .get(): {hasattr(session_response, 'get') if session_response is not None else 'N/A'}")
            try:
                import json
                response_str = json.dumps(session_response, indent=2, default=str)
                self.logger.debug(f"2FA response: {response_str}")
            except Exception as json_err:
                self.logger.warning(f"2FA response (cannot JSON serialize): {session_response}, error: {json_err}")
            
            # Handle None response (can happen with cached sessions)
            if session_response is None:
                self.logger.info("2FA returned None - session may already be active")
                return True  # Don't fail if already authenticated
            
            # Handle SDK error shape - be VERY defensive about .get() calls
            # CRITICAL: Check None FIRST before ANY attribute access
            try:
                # Double-check None (defensive programming - might have changed)
                if session_response is None:
                    self.logger.info("2FA response is None (checked again) - session may already be active")
                    return True
                
                # Check if session_response is a dict - SAFEST approach
                if isinstance(session_response, dict):
                    # Safe dict access - dict.get() is always safe
                    error = session_response.get('error')
                    if error:
                        try:
                            # Handle error as list or dict
                            if isinstance(error, list) and len(error) > 0:
                                error_item = error[0]
                                if isinstance(error_item, dict):
                                    msg = error_item.get('message', str(error_item))
                                elif error_item is not None:
                                    msg = str(error_item)
                                else:
                                    msg = "Unknown error (None in error list)"
                            elif isinstance(error, dict):
                                msg = error.get('message', str(error))
                            else:
                                msg = str(error) if error is not None else "Unknown error"
                        except Exception as parse_error:
                            self.logger.warning(f"Error parsing 2FA error response: {parse_error}")
                            msg = str(error) if error is not None else "Unknown error"
                        self.logger.error(f"2FA failed: {msg}")
                        return False
                    
                    # Extract session token when present
                    data = session_response.get('data')
                    if data is not None and isinstance(data, dict):
                        token = data.get('token')
                        if token:
                            self.session_token = token
                            self.logger.debug("2FA session token extracted from response['data']['token']")
                
                # Check if session_response has .get() method (but not a dict)
                # IMPORTANT: Check None FIRST before hasattr
                elif session_response is not None and hasattr(session_response, 'get'):
                    # Verify .get() is actually callable before using it
                    try:
                        get_method = getattr(session_response, 'get', None)
                        if not callable(get_method):
                            self.logger.debug("session_response.get exists but is not callable")
                            # Treat as unknown type
                            pass
                        else:
                            # Handle object-style response with .get() method
                            try:
                                # Safe .get() call - we know it exists and is callable
                                error = get_method('error')
                                if error:
                                    self.logger.error(f"2FA failed: {error}")
                                    return False
                                
                                # Safe .get() call for data
                                data = get_method('data')
                                if data is not None:
                                    # Safe token extraction - be extra careful
                                    token = None
                                    if isinstance(data, dict):
                                        token = data.get('token')
                                    elif hasattr(data, 'token'):
                                        token = getattr(data, 'token', None)
                                    elif hasattr(data, 'get') and callable(getattr(data, 'get', None)):
                                        try:
                                            token = data.get('token') if data is not None else None
                                        except (AttributeError, TypeError):
                                            token = None
                                    
                                    if token:
                                        self.session_token = token
                                        self.logger.debug("2FA session token extracted from response.data.token")
                            except AttributeError as e:
                                self.logger.warning(f"Error accessing object-style response (AttributeError): {e}")
                                # Don't fail - might be success
                            except Exception as e:
                                self.logger.warning(f"Error accessing object-style response: {e}")
                                # Don't fail - might be success
                    except Exception as e:
                        self.logger.debug(f"Error checking .get() method: {e}")
                
                # Check if session_response has .data attribute
                # IMPORTANT: Check None FIRST before hasattr
                elif session_response is not None and hasattr(session_response, 'data'):
                    try:
                        if hasattr(session_response.data, 'token'):
                            self.session_token = session_response.data.token
                            self.logger.debug("2FA session token extracted from response.data.token")
                    except AttributeError as e:
                        self.logger.debug(f"Could not access response.data.token: {e}")
                    except Exception as e:
                        self.logger.warning(f"Error accessing response.data.token: {e}")
                
                else:
                    # Unknown response type - log but don't fail (might be success)
                    if session_response is not None:
                        self.logger.debug(f"2FA returned unexpected response type: {type(session_response)}")
                    # Don't fail - might be success indicator
                    
            except AttributeError as e:
                # Catch any AttributeError from .get() calls
                error_msg = str(e)
                self.logger.error(f"2FA error (AttributeError accessing response): {error_msg}")
                self.logger.error(f"2FA error - session_response type: {type(session_response)}")
                self.logger.error(f"2FA error - session_response value: {session_response}")
                import traceback
                tb_str = traceback.format_exc()
                self.logger.error(f"2FA AttributeError traceback: {tb_str}")
                # AttributeError means we tried to call .get() on None or invalid object
                # This is a real error, so return False
                return False
            
            return True
        except AttributeError as e:
            # Specific handling for AttributeError (likely .get() on None)
            error_msg = str(e)
            self.logger.error(f"2FA error (AttributeError): {error_msg}")
            import traceback
            tb_str = traceback.format_exc()
            self.logger.error(f"2FA AttributeError traceback: {tb_str}")
            # Log client state for debugging
            self.logger.error(f"2FA error - client exists: {self.client is not None}")
            self.logger.error(f"2FA error - client type: {type(self.client) if self.client else 'None'}")
            return False
        except Exception as e:
            self.logger.error(f"2FA error: {e}")
            import traceback
            self.logger.debug(f"2FA error traceback: {traceback.format_exc()}")
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

    def validate_login(self, test_api_call: bool = True) -> tuple[bool, dict]:
        """
        Validate login by checking authentication state and optionally testing API access.
        
        Args:
            test_api_call (bool): If True, make a test API call to verify session is valid
            
        Returns:
            tuple[bool, dict]: (is_valid, validation_details)
                - is_valid: True if login is valid, False otherwise
                - validation_details: Dictionary with validation results and messages
        """
        validation_details = {
            "is_logged_in": False,
            "client_exists": False,
            "session_token_exists": False,
            "api_test_passed": None,
            "api_test_message": None,
            "errors": [],
            "warnings": []
        }
        
        # Check basic authentication state
        validation_details["is_logged_in"] = self.is_logged_in
        if not self.is_logged_in:
            validation_details["errors"].append("Not logged in (is_logged_in=False)")
        
        # Check client exists
        validation_details["client_exists"] = self.client is not None
        if not self.client:
            validation_details["errors"].append("Client not initialized")
        
        # Check session token
        validation_details["session_token_exists"] = self.session_token is not None
        if not self.session_token:
            validation_details["warnings"].append("Session token not set (may be normal for some SDK versions)")
        
        # Basic validation - if not logged in or no client, return early
        if not validation_details["is_logged_in"] or not validation_details["client_exists"]:
            return False, validation_details
        
        # Optional: Test API call to verify session is actually valid
        if test_api_call:
            try:
                # Try to get limits (lightweight API call that requires authentication)
                # This is a good test because it requires valid session
                if hasattr(self.client, 'limits'):
                    response = self.client.limits()
                    if response is None:
                        validation_details["api_test_passed"] = False
                        validation_details["api_test_message"] = "API call returned None"
                        validation_details["errors"].append("API test failed: No response from limits API")
                    elif isinstance(response, dict) and "error" in response:
                        error = response.get("error")
                        error_msg = "Unknown error"
                        try:
                            if isinstance(error, list) and len(error) > 0:
                                error_item = error[0]
                                if isinstance(error_item, dict):
                                    error_msg = error_item.get('message', str(error_item))
                                else:
                                    error_msg = str(error_item) if error_item else "Unknown error"
                            elif isinstance(error, dict):
                                error_msg = error.get('message', str(error))
                            else:
                                error_msg = str(error) if error else "Unknown error"
                        except Exception:
                            error_msg = str(error)
                        
                        validation_details["api_test_passed"] = False
                        validation_details["api_test_message"] = f"API error: {error_msg}"
                        
                        # Check if it's an auth error
                        if any(keyword in error_msg.lower() for keyword in ['invalid', 'jwt', 'token', 'credentials', 'unauthorized']):
                            validation_details["errors"].append(f"Session appears to be invalid: {error_msg}")
                        else:
                            validation_details["warnings"].append(f"API test returned error (may not be auth-related): {error_msg}")
                    else:
                        # Success - API call worked
                        validation_details["api_test_passed"] = True
                        validation_details["api_test_message"] = "API test successful - session is valid"
                elif hasattr(self.client, 'get_limits'):
                    # Try alternative method name
                    response = self.client.get_limits()
                    validation_details["api_test_passed"] = response is not None
                    validation_details["api_test_message"] = "API test successful" if response else "API call returned None"
                else:
                    # No limits method available, try holdings as fallback
                    if hasattr(self.client, 'holdings'):
                        response = self.client.holdings()
                        validation_details["api_test_passed"] = response is not None
                        validation_details["api_test_message"] = "API test successful (holdings)" if response else "API call returned None"
                    else:
                        validation_details["api_test_passed"] = None
                        validation_details["api_test_message"] = "No test API methods available (limits/holdings)"
                        validation_details["warnings"].append("Could not test API - no test methods available")
            except Exception as e:
                validation_details["api_test_passed"] = False
                validation_details["api_test_message"] = f"API test exception: {str(e)}"
                validation_details["errors"].append(f"API test failed with exception: {str(e)}")
        
        # Determine overall validity
        is_valid = (
            validation_details["is_logged_in"] and
            validation_details["client_exists"] and
            (validation_details["api_test_passed"] is not False if test_api_call else True)
        )
        
        return is_valid, validation_details