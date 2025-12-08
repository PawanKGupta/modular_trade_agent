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

from utils.logger import logger

from .auth import KotakNeoAuth


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

    def get_or_create_session(
        self, user_id: int, env_file: str, force_new: bool = False
    ) -> KotakNeoAuth | None:
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
            # Check if session exists and is valid
            if not force_new and user_id in self._sessions:
                auth = self._sessions[user_id]
                if auth.is_authenticated() and auth.get_client():
                    logger.debug(f"[SHARED_SESSION] Reusing existing session for user {user_id}")
                    return auth
                else:
                    # Session exists but is invalid - clear it
                    logger.warning(
                        f"[SHARED_SESSION] Existing session for user {user_id} is invalid, clearing"
                    )
                    with self._manager_lock:
                        self._sessions.pop(user_id, None)

            # Create new session
            logger.info(f"[SHARED_SESSION] Creating new session for user {user_id}")
            auth = KotakNeoAuth(env_file)
            if auth.login():
                with self._manager_lock:
                    self._sessions[user_id] = auth
                logger.info(f"[SHARED_SESSION] Session created and cached for user {user_id}")
                return auth
            else:
                logger.error(f"[SHARED_SESSION] Failed to create session for user {user_id}")
                return None

    def get_session(self, user_id: int) -> KotakNeoAuth | None:
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
