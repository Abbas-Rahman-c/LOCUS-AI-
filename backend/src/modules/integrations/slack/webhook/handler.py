"""
Locus AI — Events API dispatcher.

Routes incoming Slack event types to the appropriate handler.
Currently handles:
  - url_verification  → challenge-response
  - event_callback    → message shaping + pgmq enqueue
"""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

from fastapi import Response
from fastapi.responses import JSONResponse

from queue.pgmq.producer import enqueue_event

log = logging.getLogger(__name__)

# Message subtypes that aren't real user messages
_IGNORED_SUBTYPES = {
    "channel_join", "channel_leave", "channel_topic",
    "channel_purpose", "channel_name", "channel_archive",
    "channel_unarchive", "bot_message", "message_deleted",
    "message_changed", "file_share", "pinned_item",
}


async def handle_event_payload(
    raw_body: bytes,
    resolve_tenant: "callable",
) -> Response:
    """
    Parse and dispatch a verified Slack Events API payload.

    Args:
        raw_body: The raw bytes (already HMAC-verified by the verifier dependency).
        resolve_tenant: async callable(team_id) -> list[dict] returning integration
                        rows with at least 'workspace_id' and 'id' keys.

    Returns:
        A FastAPI Response (always 200 to avoid Slack retries).
    """
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        log.error("Failed to parse Slack event body as JSON")
        return Response(status_code=400)

    event_type = payload.get("type")

    # ── URL Verification (challenge-response) ────────────────────────
    if event_type == "url_verification":
        challenge = payload.get("challenge", "")
        log.info("Slack URL verification challenge received")
        return JSONResponse(content={"challenge": challenge}, status_code=200)

    # ── Event Callback ───────────────────────────────────────────────
    if event_type == "event_callback":
        event = payload.get("event", {})
        team_id = payload.get("team_id", "")
        event_id = payload.get("event_id", "")

        # Ignore bot messages to avoid feedback loops
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            log.debug("Ignoring bot message: event_id=%s", event_id)
            return Response(status_code=200)

        # Only process message events for MVP
        inner_type = event.get("type", "")
        if inner_type not in ("message", "message.channels", "message.groups", "message.im", "message.mpim"):
            log.debug("Ignoring non-message event type: %s", inner_type)
            return Response(status_code=200)

        # Ignore system subtypes
        subtype = event.get("subtype")
        if subtype in _IGNORED_SUBTYPES:
            log.debug("Ignoring message subtype: %s", subtype)
            return Response(status_code=200)

        # ── Look up Locus tenant from Slack team_id ──────────────────
        integrations = await resolve_tenant(team_id)

        if not integrations:
            log.warning("No integration found for Slack team_id=%s", team_id)
            return Response(status_code=200)  # ACK but skip

        # ── Enqueue into Supabase pgmq for each matching workspace ───
        for integration in integrations:
            envelope = {
                "tenant_id": str(integration.get("workspace_id", "")),
                "source": "slack",
                "source_id": event_id,
                "team_id": team_id,
                "channel": event.get("channel", ""),
                "ts": event.get("ts", ""),
                "thread_ts": event.get("thread_ts"),
                "user": event.get("user"),
                "text": event.get("text"),
                "event_type": inner_type,
                "received_at": time.time(),
            }

            try:
                msg_id = await enqueue_event(envelope)
                log.info(
                    "Slack event enqueued to pgmq: tenant=%s channel=%s ts=%s msg_id=%s",
                    envelope["tenant_id"],
                    envelope["channel"],
                    envelope["ts"],
                    msg_id,
                )
            except Exception as exc:
                log.error("Failed to enqueue Slack event to pgmq: %s", exc)

        # Always return 200 to prevent Slack retries
        return Response(status_code=200)

    # ── Unknown event type ───────────────────────────────────────────
    log.warning("Unknown Slack event type: %s", event_type)
    return Response(status_code=200)
