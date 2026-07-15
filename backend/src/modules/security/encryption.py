"""
AES-GCM encryption / decryption.

Two related but separate uses:
  1. encrypt_raw_content / decrypt_raw_content — raw_events.raw_content
     (versioned format, backwards-compatible with pre-encryption rows)
  2. encrypt_string / decrypt_string — OAuth tokens (oauth_tokens table),
     used by the Gmail and Slack connectors. Simple Base64-encoded output.

Key source (first match wins):
  1. RAW_EVENTS_ENCRYPTION_KEY
  2. APP_SECRET_KEY
"""
from __future__ import annotations

import base64
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
            "to a strong secret before storing raw events or OAuth tokens."
        )
    key = hashlib.sha256(secret.encode("utf-8")).digest()  # 32 bytes
    return AESGCM(key)


# ── Raw event content (versioned, backwards-compatible) ──────────────────

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


# ── OAuth tokens (simple Base64 string in/out) ────────────────────────────
# Used by Gmail/Slack connectors when writing to oauth_tokens.access_token
# and .refresh_token. Same underlying key and cipher as above, just a
# plain-string convenience wrapper instead of the versioned blob format,
# matching what's already stored in oauth_tokens today.

def encrypt_string(data: str) -> str:
    """Encrypt a string and return it as a Base64-encoded string."""
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = _aesgcm().encrypt(nonce, data.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_string(encrypted_str: str) -> str:
    """Decrypt a Base64-encoded encrypted string produced by encrypt_string()."""
    raw = base64.b64decode(encrypted_str)
    nonce = raw[:_NONCE_LEN]
    ciphertext = raw[_NONCE_LEN:]
    return _aesgcm().decrypt(nonce, ciphertext, None).decode("utf-8")