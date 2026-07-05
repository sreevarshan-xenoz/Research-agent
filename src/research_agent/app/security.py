"""RBAC, encryption, and secrets management for P18 Security Hardening.

Provides:
- Role-based access control (viewer, editor, admin)
- Fernet-based symmetric encryption for API keys at rest
- Role management utilities
"""

from __future__ import annotations

import base64
import logging
import threading
from enum import Enum
from typing import Any

from fastapi import Depends, HTTPException, status


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------


class UserRole(str, Enum):
    """Hierarchical RBAC roles. Higher ordinal = more privileges."""
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"

    @classmethod
    def has_ge(cls, a: str, b: str) -> bool:
        """Check if role a >= role b in privilege hierarchy."""
        order = [cls.VIEWER, cls.EDITOR, cls.ADMIN]
        try:
            return order.index(cls(a)) >= order.index(cls(b))
        except (ValueError, KeyError):
            return False


_ROLE_HIERARCHY: dict[str, int] = {
    "viewer": 0,
    "editor": 1,
    "admin": 2,
}


def role_ge(role_a: str, role_b: str) -> bool:
    """Check if role_a has >= privileges than role_b."""
    return _ROLE_HIERARCHY.get(role_a, 0) >= _ROLE_HIERARCHY.get(role_b, 0)


def role_gt(role_a: str, role_b: str) -> bool:
    """Check if role_a has > privileges than role_b."""
    return _ROLE_HIERARCHY.get(role_a, 0) > _ROLE_HIERARCHY.get(role_b, 0)


# ---------------------------------------------------------------------------
# Encryption utility (Fernet symmetric encryption)
# ---------------------------------------------------------------------------

# Module-level cache for the Fernet cipher
_fernet_instance: Any | None = None
_fernet_lock = threading.Lock()


def _get_fernet() -> Any:
    """Get or create the Fernet cipher instance.

    The encryption key is loaded from settings (or generated on-the-fly
    for development). The Fernet instance is cached module-globally.
    """
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    with _fernet_lock:
        if _fernet_instance is not None:
            return _fernet_instance

        try:
            # Lazy import to avoid circular import at module level
            from cryptography.fernet import Fernet
            from research_agent.config import load_settings
            settings = load_settings()
            key_str = str(settings.secrets_mgmt.encryption_key)

            if key_str:
                # Key provided in config — use it directly
                # Ensure proper padding for base64-encoded 32-byte key
                try:
                    key_bytes = key_str.encode("utf-8")
                    # Validate it's a proper Fernet key
                    Fernet(key_bytes)
                    _fernet_instance = Fernet(key_bytes)
                except (ValueError, Exception):
                    # Not a valid Fernet key — derive one from the secret
                    import hashlib
                    digest = hashlib.sha256(key_str.encode("utf-8")).digest()
                    encoded_key = base64.urlsafe_b64encode(digest)
                    _fernet_instance = Fernet(encoded_key)
            else:
                # No encryption key configured — generate a dev key
                dev_key = Fernet.generate_key()
                _fernet_instance = Fernet(dev_key)
                logger.warning(
                    "No ENCRYPTION_KEY configured. Generated ephemeral key for this session. "
                    "Encrypted data will NOT be decryptable after restart!"
                )
        except ImportError:
            logger.warning(
                "cryptography package not installed. Encryption disabled. "
                "Run: pip install cryptography"
            )
            _fernet_instance = None

        return _fernet_instance


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value using Fernet symmetric encryption.

    Returns the encrypted value as a base64-encoded string with a
    'enc:' prefix so it's distinguishable from plaintext.
    """
    cipher = _get_fernet()
    if cipher is None:
        return plaintext  # No encryption available — store as-is
    token = cipher.encrypt(plaintext.encode("utf-8"))
    return f"enc:{token.decode('utf-8')}"


def decrypt_value(encrypted: str) -> str:
    """Decrypt a Fernet-encrypted string value.

    Expects the 'enc:' prefix. If the value doesn't have the prefix,
    it's returned as-is (plaintext fallback for backward compat).
    """
    if not encrypted.startswith("enc:"):
        return encrypted
    cipher = _get_fernet()
    if cipher is None:
        logger.warning("Cannot decrypt value: cryptography package not available")
        return ""
    try:
        token = encrypted[4:]  # Strip 'enc:' prefix
        return cipher.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        logger.error("Decryption failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# RBAC FastAPI dependency
# ---------------------------------------------------------------------------


def require_role(minimum_role: str):
    """FastAPI dependency factory: require the current user to have at least
    the specified role.

    Usage:
        @app.get("/api/admin/settings")
        async def admin_settings(user: User = Depends(current_active_user)):
            # Will 403 if user.role < admin
            pass

    Or as a dependency directly:

        @app.get("/api/admin/settings")
        async def admin_settings(
            user: User = Depends(require_role("admin"))
        ):
            pass
    """
    async def _role_checker(
        user = Depends(lambda: __import__("research_agent.app.auth", fromlist=["current_active_user"]).current_active_user),
    ):
        # Get the role from the user object (it should have a 'role' field now)
        user_role = getattr(user, "role", "viewer") or "viewer"
        if not role_ge(user_role, minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role '{minimum_role}' or higher. Current role: '{user_role}'.",
            )
        return user

    return _role_checker


# ---------------------------------------------------------------------------
# Helpers for role management
# ---------------------------------------------------------------------------


def is_admin(user: Any) -> bool:
    """Check if a user has admin role."""
    return getattr(user, "role", None) == "admin"


def is_editor(user: Any) -> bool:
    """Check if a user has at least editor role."""
    return role_ge(getattr(user, "role", "viewer"), "editor")


async def get_user_role(user_id: str) -> str:
    """Get a user's role from the database.

    Args:
        user_id: The UUID string of the user.

    Returns:
        The role string (viewer, editor, admin). Defaults to 'viewer'.
    """
    try:
        from research_agent.app.auth import async_session_maker, User
        from sqlalchemy import select
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)  # type: ignore[attr-defined]
            )
            user = result.scalar_one_or_none()
            if user:
                return getattr(user, "role", "viewer") or "viewer"
    except Exception as exc:
        logger.warning("Failed to get user role for %s: %s", user_id, exc)
    return "viewer"


async def set_user_role(user_id: str, new_role: str) -> bool:
    """Set a user's role in the database.

    Args:
        user_id: The UUID string of the user.
        new_role: The new role (viewer, editor, admin).

    Returns:
        True if successful, False otherwise.
    """
    if new_role not in ("viewer", "editor", "admin"):
        logger.warning("Invalid role: %s", new_role)
        return False

    try:
        from research_agent.app.auth import async_session_maker, User
        from sqlalchemy import select
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)  # type: ignore[attr-defined]
            )
            user = result.scalar_one_or_none()
            if not user:
                return False
            user.role = new_role  # type: ignore[attr-defined]
            await session.commit()
            logger.info("User %s role updated to %s", user_id, new_role)
            return True
    except Exception as exc:
        logger.error("Failed to set user role for %s: %s", user_id, exc)
        return False
