"""
AES-GCM encryption / decryption for raw content.
"""
from __future__ import annotations
import os
import base64
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

log = logging.getLogger(__name__)


def _get_encryption_key() -> bytes:
    """Retrieve and format the 32-byte encryption key from environment variable."""
    secret = os.getenv("APP_SECRET_KEY", "fallback_secret_key_which_is_thirty_two_bytes_long_123!")
    # Derive a key from the secret
    import hashlib
    return hashlib.sha256(secret.encode()).digest()


def encrypt_data(data: str | bytes) -> bytes:
    """Encrypt a string or bytes using AES-GCM. Returns the raw encrypted bytes."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    # Combine nonce + ciphertext
    return nonce + ciphertext


def decrypt_data(encrypted_data: bytes) -> str:
    """Decrypt AES-GCM encrypted bytes. Returns the decrypted string."""
    if len(encrypted_data) < 12:
        raise ValueError("Encrypted data is too short")
        
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:]
    decrypted = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted.decode("utf-8")


def encrypt_string(data: str) -> str:
    """Encrypt a string and return it as a Base64-encoded string."""
    raw_encrypted = encrypt_data(data)
    return base64.b64encode(raw_encrypted).decode("utf-8")


def decrypt_string(encrypted_str: str) -> str:
    """Decrypt a Base64-encoded encrypted string."""
    raw_bytes = base64.b64decode(encrypted_str)
    return decrypt_data(raw_bytes)
