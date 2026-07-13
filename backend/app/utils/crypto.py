"""Credential encryption utilities using Fernet symmetric encryption.

The encryption key is derived from ``CREDENTIAL_ENCRYPTION_KEY`` first,
then falls back to ``SECRET_KEY`` for development convenience. In production
``DEBUG=False`` a warning is logged once if the dedicated credential key is
missing, because JWT key leakage should not compromise stored credentials.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings

_jwt_fallback_warned = False


def _load_fernet() -> Fernet:
    """Load a Fernet instance, deriving the key from configured secrets."""
    global _jwt_fallback_warned

    settings = get_settings()
    secret = settings.credential_encryption_key
    if not secret:
        secret = settings.secret_key
        if secret and not settings.debug and not _jwt_fallback_warned:
            # Lazy import to avoid circular setup issues.
            import structlog

            logger = structlog.get_logger()
            logger.warning(
                "credential_encryption_key_missing",
                message=(
                    "Production environment is missing CREDENTIAL_ENCRYPTION_KEY; "
                    "falling back to SECRET_KEY. Configure a dedicated encryption key "
                    "and re-encrypt stored credentials."
                ),
            )
            _jwt_fallback_warned = True
    if not secret:
        raise RuntimeError(
            "No encryption key available: set CREDENTIAL_ENCRYPTION_KEY or SECRET_KEY"
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_token(plain: str) -> str:
    """Encrypt a plaintext string and return a base64-encoded token."""
    return _load_fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_token(cipher: str) -> str:
    """Decrypt a base64-encoded token and return the plaintext string."""
    return _load_fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")


def mask_token(token: str) -> str:
    """Mask a token for display, keeping the first 4 and last 4 characters."""
    if not token:
        return ""
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"
