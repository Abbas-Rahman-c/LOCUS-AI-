"""
Unit tests for the auth module: JWT issue / verify lifecycle.
"""
from __future__ import annotations

import time
import uuid

import pytest
from jose import ExpiredSignatureError, JWTError

from modules.auth.service import (
    AuthError,
    issue_tenant_jwt,
    verify_tenant_jwt,
)


def test_jwt_roundtrip():
    """Issue a JWT then verify it — claims must survive the roundtrip."""
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    token = issue_tenant_jwt(user_id=user_id, tenant_id=tenant_id, role="owner")
    payload = verify_tenant_jwt(token)

    assert payload["sub"] == user_id
    assert payload["tenant_id"] == tenant_id
    assert payload["role"] == "owner"
    assert payload["iss"] == "locus-ai"


def test_jwt_contains_expiry():
    """Issued JWT must carry an exp claim in the future."""
    token = issue_tenant_jwt(user_id="u1", tenant_id="t1", role="member")
    payload = verify_tenant_jwt(token)
    assert payload["exp"] > int(time.time())


def test_expired_jwt_raises(monkeypatch):
    """A JWT with TTL=0 must be immediately expired."""
    token = issue_tenant_jwt(user_id="u1", tenant_id="t1", role="member", ttl=-1)
    with pytest.raises((ExpiredSignatureError, JWTError)):
        verify_tenant_jwt(token)


def test_wrong_signature_rejected(monkeypatch):
    """A JWT signed with a different key must be rejected."""
    token = issue_tenant_jwt(user_id="u1", tenant_id="t1", role="member")

    # Tamper: change the secret so the signature no longer matches
    monkeypatch.setenv("APP_SECRET_KEY", "completely-different-secret-key-at-least-32-chars")
    with pytest.raises(JWTError):
        verify_tenant_jwt(token)


def test_missing_tenant_id_rejected():
    """A JWT without tenant_id claim must be rejected by verify_tenant_jwt."""
    # We can't issue one via the normal path, so forge it manually
    from jose import jwt as jose_jwt
    import os
    key = os.environ.get("APP_SECRET_KEY", "")
    raw = jose_jwt.encode(
        {"sub": "u1", "iss": "locus-ai", "exp": int(time.time()) + 3600},
        key,
        algorithm="HS256",
    )
    with pytest.raises(ValueError, match="missing tenant_id"):
        verify_tenant_jwt(raw)
