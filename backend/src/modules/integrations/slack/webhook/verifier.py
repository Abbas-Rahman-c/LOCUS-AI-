"""
Locus AI — HMAC-SHA256 signature verification for Slack webhooks.

Implements Slack's signing spec:
  https://api.slack.com/authentication/verifying-requests-from-slack

Used as a FastAPI dependency on the Slack Events API endpoint.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time

from fastapi import Depends, HTTPException, Request

from common.config.slack_config import get_slack_config

log = logging.getLogger(__name__)

# Slack allows up to 5 minutes of clock skew
_MAX_TIMESTAMP_DRIFT_SECONDS = 300
_SIGNING_VERSION = "v0"


async def _read_body(request: Request) -> bytes:
    """
    Read and cache the raw request body.

    FastAPI normally consumes the body stream once; we store it
    on request.state so both the verifier and the route handler
    can access it.
    """
    if hasattr(request.state, "raw_body"):
        return request.state.raw_body
    body = await request.body()
    request.state.raw_body = body
    return body


async def verify_slack_signature(request: Request) -> bytes:
    """
    FastAPI dependency that verifies X-Slack-Signature.

    Raises 401 on failure. Returns the raw body bytes on success
    so the downstream route doesn't need to re-read it.

    Verification steps:
      1. Check X-Slack-Request-Timestamp is within 5 minutes of server time.
      2. Construct the basestring:  v0:{timestamp}:{body}
      3. Compute HMAC-SHA256 using the app's signing secret.
      4. Compare computed signature to X-Slack-Signature header.
    """
    config = get_slack_config()

    # ── Extract headers ──────────────────────────────────────────────
    timestamp_header = request.headers.get("X-Slack-Request-Timestamp")
    signature_header = request.headers.get("X-Slack-Signature")

    if not timestamp_header or not signature_header:
        log.warning(
            "Missing Slack signature headers: timestamp=%s signature=%s",
            bool(timestamp_header),
            bool(signature_header),
        )
        raise HTTPException(
            status_code=401,
            detail="Missing Slack signature headers",
        )

    # ── Timestamp drift check ────────────────────────────────────────
    try:
        event_timestamp = int(timestamp_header)
    except (ValueError, TypeError):
        log.warning("Invalid Slack timestamp: %s", timestamp_header)
        raise HTTPException(
            status_code=401,
            detail="Invalid Slack timestamp",
        )

    now = int(time.time())
    drift = abs(now - event_timestamp)
    if drift > _MAX_TIMESTAMP_DRIFT_SECONDS:
        log.warning(
            "Slack timestamp too old: drift=%ds (max %ds)",
            drift,
            _MAX_TIMESTAMP_DRIFT_SECONDS,
        )
        raise HTTPException(
            status_code=401,
            detail="Slack request timestamp is too old",
        )

    # ── Read body ────────────────────────────────────────────────────
    body = await _read_body(request)

    # ── Compute HMAC-SHA256 ──────────────────────────────────────────
    sig_basestring = f"{_SIGNING_VERSION}:{event_timestamp}:{body.decode('utf-8')}"
    computed_hash = hmac.new(
        key=config.signing_secret.encode("utf-8"),
        msg=sig_basestring.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    computed_signature = f"{_SIGNING_VERSION}={computed_hash}"

    # ── Constant-time comparison ─────────────────────────────────────
    if not hmac.compare_digest(computed_signature, signature_header):
        log.warning(
            "Slack signature mismatch: computed=%s… received=%s…",
            computed_signature[:20],
            signature_header[:20],
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid Slack signature",
        )

    log.debug("Slack signature verified successfully")
    return body
