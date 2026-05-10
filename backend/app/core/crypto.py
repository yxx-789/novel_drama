"""Symmetric encryption for sensitive user data (API keys)."""

import base64
import os

from cryptography.fernet import Fernet

from app.core.config import settings


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazy-init Fernet instance from FERNET_SECRET."""
    global _fernet
    if _fernet is None:
        secret = settings.FERNET_SECRET
        if not secret:
            raise RuntimeError("FERNET_SECRET is not configured")
        # Fernet requires a 32-byte base64-encoded key.
        # If the provided secret is not exactly 32 bytes after padding,
        # hash it to a fixed length and base64-encode.
        if len(secret) < 32:
            secret = secret.ljust(32, "0")
        key_bytes = secret[:32].encode("utf-8")
        encoded_key = base64.urlsafe_b64encode(key_bytes)
        _fernet = Fernet(encoded_key)
    return _fernet


def encrypt_api_key(plain_key: str) -> str:
    """Encrypt a plaintext API key and return base64 ciphertext."""
    f = _get_fernet()
    return f.encrypt(plain_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(cipher_text: str) -> str:
    """Decrypt base64 ciphertext and return the plaintext API key."""
    f = _get_fernet()
    return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
