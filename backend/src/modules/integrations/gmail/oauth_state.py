"""Single-use, short-lived OAuth state records for the Gmail flow."""
from __future__ import annotations

import secrets
import time
import uuid

_TTL_SECONDS = 600
_states: dict[str, tuple[uuid.UUID, float]] = {}


def create_state(tenant_id: uuid.UUID) -> str:
    """Create an opaque state token bound to a tenant for one callback."""
    _purge_expired()
    state = secrets.token_urlsafe(32)
    _states[state] = (tenant_id, time.monotonic() + _TTL_SECONDS)
    return state


def consume_state(state: str) -> uuid.UUID:
    """Validate and consume state; replayed, unknown, and expired values fail."""
    record = _states.pop(state, None)
    if record is None:
        raise ValueError("Invalid or already-used OAuth state")
    tenant_id, expires_at = record
    if time.monotonic() > expires_at:
        raise ValueError("Expired OAuth state")
    return tenant_id


def _purge_expired() -> None:
    now = time.monotonic()
    for state, (_, expires_at) in list(_states.items()):
        if expires_at <= now:
            _states.pop(state, None)
