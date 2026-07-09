"""
Locus AI — HMAC-SHA256 verification helper for Slack webhook signatures.

Lower-level utility. The FastAPI dependency lives in
modules/integrations/slack/webhook/verifier.py and calls this if needed.
"""
from __future__ import annotations

import hashlib
import hmac


def compute_slack_signature(signing_secret: str, timestamp: str, body: str) -> str:
    """
    Compute the expected Slack signature for a given payload.

    Args:
        signing_secret: The app's Slack signing secret.
        timestamp: X-Slack-Request-Timestamp header value.
        body: Raw request body as a string.

    Returns:
        The full signature string in the form "v0=<hex_digest>".
    """
    sig_basestring = f"v0:{timestamp}:{body}"
    computed = hmac.new(
        key=signing_secret.encode("utf-8"),
        msg=sig_basestring.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"v0={computed}"


def verify_signature(signing_secret: str, timestamp: str, body: str, expected: str) -> bool:
    """
    Constant-time comparison of a computed Slack signature against the expected value.
    """
    computed = compute_slack_signature(signing_secret, timestamp, body)
    return hmac.compare_digest(computed, expected)
