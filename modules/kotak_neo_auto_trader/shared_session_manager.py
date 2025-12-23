#!/usr/bin/env python3
"""
Shared Session Manager for Kotak Neo API

Maintains ONE client object per user that is shared across:
- Unified service
- Web API
- Individual services
- Any other component

When session expires, recreates the client ONCE and everyone uses the new one.
"""

import threading
import time
from typing import Optional

from utils.logger import logger


class SharedSessionManager:
    """
    Manages shared Kotak Neo authentication sessions per user.

    Ensures only ONE client object exists per user, shared across all services.
    When session expires, recreates it once and all services use the new client.
    """

    def __init__(self):
        # Key: user_id, Value: KotakNeoAuth instance
        self._sessions: dict[int, KotakNeoAuth] = {}
        self._locks: dict[int, threading.Lock] = {}
        self._manager_lock = threading.Lock()  # Protects _sessions and _locks dicts

        # Phase -1: Re-auth rate limiting to prevent OTP spam
        # Track last re-auth time per user to enforce cooldown
        self._REAUTH_COOLDOWN = 60  # seconds
        self._last_reauth_time: dict[int, float] = {}

    def get_or_create_session(
        self, user_id: int, env_file: str, force_new: bool = False
    ) -> Optional["KotakNeoAuth"]:
        """
        Get existing session or create new one for user.

        Args:
            user_id: User ID
            env_file: Path to environment file with broker credentials
            force_new: If True, force creation of new session (clears old one)

        Returns:
            KotakNeoAuth instance or None if login fails
        """
        # Get or create lock for this user
        with self._manager_lock:
            if user_id not in self._locks:
                self._locks[user_id] = threading.Lock()
            user_lock = self._locks[user_id]

        with user_lock:
            # Phase -1: Check re-auth rate limiting (prevent OTP spam)
            if user_id in self._last_reauth_time:
                time_since_reauth = time.time() - self._last_reauth_time[user_id]
                if time_since_reauth < self._REAUTH_COOLDOWN:
                    logger.warning(
                        f"[SHARED_SESSION] Re-auth cooldown active for user {user_id}, "
                        f"{self._REAUTH_COOLDOWN - time_since_reauth:.0f}s remaining"
                    )
                    # Return existing session even if client is None
                    # (let API call handle it via @handle_reauth)
                    if user_id in self._sessions:
                        return self._sessions[user_id]

            # Check if session exists and is valid
            if not force_new and user_id in self._sessions:
                auth = self._sessions[user_id]

                # Phase -1: Check session health more carefully
                if auth.is_authenticated():
                    client = auth.get_client()

                    # Only clear if BOTH are false/None AND session actually expired
                    if not client:
                        # Check if session is actually expired (not just client None)
                        if hasattr(auth, "is_session_valid") and auth.is_session_valid():
                            # Session valid but client None - don't clear, let it recover
                            logger.warning(
                                f"[SHARED_SESSION] Session valid but client None for user {user_id}, "
                                "attempting recovery"
                            )
                            return auth  # Return existing, let API call handle via @handle_reauth
                        else:
                            # Session expired - clear it
                            logger.warning(
                                f"[SHARED_SESSION] Session expired for user {user_id}, clearing"
                            )
                            with self._manager_lock:
                                self._sessions.pop(user_id, None)
                    else:
                        # Both authenticated and client available - reuse
                        logger.info(f"[SHARED_SESSION] Reusing existing session for user {user_id}")
                        return auth
                else:
                    # Not authenticated - clear
                    logger.warning(
                        f"[SHARED_SESSION] Existing session for user {user_id} is invalid, clearing"
                    )
                    with self._manager_lock:
                        self._sessions.pop(user_id, None)

            # Create new session
            logger.info(f"[SHARED_SESSION] Creating new session for user {user_id}")
            from .auth import KotakNeoAuth  # Import here to avoid circular dependency

            auth = KotakNeoAuth(env_file)
            if auth.login():
                with self._manager_lock:
                    self._sessions[user_id] = auth
                # Phase -1: Record re-auth time for rate limiting
                self._last_reauth_time[user_id] = time.time()
                logger.info(f"[SHARED_SESSION] Session created and cached for user {user_id}")
                return auth
            else:
                logger.error(f"[SHARED_SESSION] Failed to create session for user {user_id}")
                return None

    def get_session(self, user_id: int) -> Optional["KotakNeoAuth"]:
        """
        Get existing session for user without creating new one.

        Args:
            user_id: User ID

        Returns:
            KotakNeoAuth instance or None if not found
        """
        with self._manager_lock:
            return self._sessions.get(user_id)

    def clear_session(self, user_id: int) -> None:
        """
        Clear session for user (forces new session on next get_or_create_session call).

        Args:
            user_id: User ID
        """
        with self._manager_lock:
            if user_id in self._sessions:
                auth = self._sessions.pop(user_id)
                try:
                    if auth.is_authenticated():
                        auth.logout()
                except Exception:
                    pass  # Ignore logout errors
                logger.info(f"[SHARED_SESSION] Cleared session for user {user_id}")


# Global singleton instance
_shared_session_manager = SharedSessionManager()


def get_shared_session_manager() -> SharedSessionManager:
    """Get the global shared session manager instance."""
    return _shared_session_manager
