"""
Authentication Module for Kotak Neo API
Handles login, logout, and session management
"""

import os
import json
import pyotp
from dotenv import load_dotenv
from typing import Optional, Tuple
from datetime import datetime, timedelta
# Import existing project logger
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
    
    def __init__(self, config_file: str = "kotak_neo.env"):
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
        # Session cache path (persist token for the day)
        self.session_cache_path = Path(__file__).with_name("session_cache.json")
    
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
        Perform complete login process with daily token caching.
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
            
            # Try cached session first (valid for the day)
            if self._try_use_cached_session():
                self.is_logged_in = True
                self.logger.info("Reused cached session token (daily cache)")
                return True
            
            # Perform login + 2FA
            if not self._perform_login():
                return False
            if not self._complete_2fa():
                return False
            
            # Cache session for the day
            self._save_session_cache()
            
            self.is_logged_in = True
            self.logger.info("Login completed successfully!")
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
            
            if "error" in login_response:
                self.logger.error(f"Login failed: {login_response['error'][0]['message']}")
                return False
            
            self.logger.info("Login successful, proceeding with 2FA...")
            return True
            
        except Exception as e:
            self.logger.error(f"Login error: {e}")
            return False
    
    def _complete_2fa(self) -> bool:
        """Complete 2FA authentication"""
        try:
            if self.mpin:
                self.logger.info("Using MPIN for 2FA")
                session_response = self.client.session_2fa(OTP=self.mpin)
            else:
                # Generate TOTP (do not log actual OTP to console)
                totp = pyotp.TOTP(self.totp_secret)
                current_otp = totp.now()
                self.logger.info("Generated TOTP for 2FA")
                session_response = self.client.session_2fa(OTP=current_otp)
            
            if "error" in session_response:
                self.logger.error(f"2FA failed: {session_response['error'][0]['message']}")
                return False
            
            # Extract session token
            if hasattr(session_response, 'data') and hasattr(session_response.data, 'token'):
                self.session_token = session_response.data.token
            elif isinstance(session_response, dict) and 'data' in session_response:
                self.session_token = session_response['data'].get('token')
            
            return True
            
        except Exception as e:
            self.logger.error(f"2FA error: {e}")
            return False
    
    def _try_use_cached_session(self) -> bool:
        """Attempt to reuse a cached session token for the current day."""
        try:
            if not self.session_cache_path.exists():
                return False
            with open(self.session_cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            # Basic validations
            if cache.get('environment') != self.environment or cache.get('mobile') != self.mobile_number:
                return False
            exp = cache.get('expires_at')
            if not exp:
                return False
            if datetime.fromisoformat(exp) <= datetime.now():
                return False
            token = cache.get('session_token')
            if not token:
                return False
            # Try to inject token into client and verify by lightweight call
            try:
                # Common patterns in HTTP clients
                if hasattr(self.client, 'session') and hasattr(self.client.session, 'headers'):
                    self.client.session.headers['Authorization'] = f'Bearer {token}'
                # Fallback attributes
                for attr in ('access_token', 'bearer_token', 'session_token', 'auth_token'):
                    if hasattr(self.client, attr):
                        setattr(self.client, attr, token)
                # Validate token via a lightweight call: prefer get_profile, else limits/holdings
                ok = False
                try:
                    if hasattr(self.client, 'get_profile'):
                        prof = self.client.get_profile()
                        ok = prof is not None
                except Exception:
                    ok = False
                if not ok:
                    try:
                        lim = self.client.limits(segment="ALL", exchange="ALL")
                        ok = isinstance(lim, dict) and 'error' not in lim
                    except Exception:
                        ok = False
                if not ok and hasattr(self.client, 'holdings'):
                    try:
                        h = self.client.holdings()
                        ok = isinstance(h, dict) and 'error' not in h
                    except Exception:
                        ok = False
                if ok:
                    self.session_token = token
                    return True
            except Exception as e:
                self.logger.info(f"Cached session not usable, falling back to fresh login: {e}")
                return False
            return False
        except Exception:
            return False

    def _save_session_cache(self) -> None:
        """Save session token cache valid until end of day."""
        try:
            if not self.session_token:
                return
            # Expire at end-of-day local time
            now = datetime.now()
            eod = datetime(year=now.year, month=now.month, day=now.day, hour=23, minute=59, second=59)
            cache = {
                'session_token': self.session_token,
                'created_at': now.isoformat(),
                'expires_at': eod.isoformat(),
                'environment': self.environment,
                'mobile': self.mobile_number,
            }
            with open(self.session_cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            self.logger.info(f"Could not persist session cache: {e}")

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