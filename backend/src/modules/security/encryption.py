"""
AES-GCM encryption / decryption for raw event content.

Key source (first match wins):
  1. RAW_EVENTS_ENCRYPTION_KEY
  2. APP_SECRET_KEY

Stored blob format:
  b"LOCUS1" + 12-byte nonce + ciphertext (includes GCM tag)
"""
from __future__ import annotations

import hashlib
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_MAGIC = b"LOCUS1"
_NONCE_LEN = 12


class EncryptionError(Exception):
    """Raised when encryption configuration or payload is invalid."""


@lru_cache(maxsize=1)
def _aesgcm() -> AESGCM:
    secret = os.environ.get("RAW_EVENTS_ENCRYPTION_KEY") or os.environ.get("APP_SECRET_KEY")
    if not secret or secret.startswith("generate-with-"):
        raise EncryptionError(
            "Set RAW_EVENTS_ENCRYPTION_KEY or APP_SECRET_KEY in backend/.env "
            "to a strong secret before storing raw events."
        )
    key = hashlib.sha256(secret.encode("utf-8")).digest()  # 32 bytes
    return AESGCM(key)


def encrypt_raw_content(plaintext: bytes) -> bytes:
    """Encrypt plaintext bytes for storage in raw_events.raw_content."""
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = _aesgcm().encrypt(nonce, plaintext, None)
    return _MAGIC + nonce + ciphertext


def decrypt_raw_content(blob: bytes) -> bytes:
    """
    Decrypt a raw_content blob.

    Legacy plaintext JSON (no LOCUS1 prefix) is returned unchanged so older
    rows written before encryption still read.
    """
    if not blob.startswith(_MAGIC):
        return blob
    nonce = blob[len(_MAGIC) : len(_MAGIC) + _NONCE_LEN]
    ciphertext = blob[len(_MAGIC) + _NONCE_LEN :]
    return _aesgcm().decrypt(nonce, ciphertext, None)


def is_encrypted_blob(blob: bytes) -> bool:
    return blob.startswith(_MAGIC)
