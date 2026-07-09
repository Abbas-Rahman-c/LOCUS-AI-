"""
Locus AI — Slack connector router.

Handles:
  1. OAuth 2.0 install flow (redirect + callback)
  2. Events API endpoint (url_verification + event_callback)
  3. HMAC signature verification on every incoming Slack request

Design constraints:
  • Respond to Slack within 3 seconds to avoid retries
  • Enqueue shaped events into Supabase pgmq (INGESTION_CONTRACT.md)
  • Store access tokens in Supabase Vault, never in plaintext
"""
from __future__ import annotations

import logging
import secrets
import time
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from common.config.slack_config import get_slack_config
from modules.integrations.slack.webhook.verifier import verify_slack_signature
from modules.integrations.slack.webhook.handler import handle_event_payload
from modules.integrations.slack.service import (
    exchange_code_for_token,
    store_token_in_vault,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/slack", tags=["slack"])

# ── In-memory state store for OAuth CSRF ─────────────────────────────
_oauth_states: dict[str, dict[str, Any]] = {}


# ═══════════════════════════════════════════════════════════════════════
# 1. OAuth 2.0 Install Flow
# ═══════════════════════════════════════════════════════════════════════

@router.get("/oauth/install")
async def slack_oauth_install(
    workspace_id: str = Query(..., description="Locus workspace UUID initiating the install"),
) -> RedirectResponse:
    """
    Redirect the user to Slack's OAuth authorization page.

    Generates a cryptographic state token tied to the Locus workspace_id
    to prevent CSRF attacks during the callback.
    """
    config = get_slack_config()
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "workspace_id": workspace_id,
        "created_at": time.time(),
    }

    # Clean up stale states (older than 10 minutes)
    cutoff = time.time() - 600
    stale_keys = [k for k, v in _oauth_states.items() if v["created_at"] < cutoff]
    for k in stale_keys:
        _oauth_states.pop(k, None)

    authorize_url = (
        "https://slack.com/oauth/v2/authorize"
        f"?client_id={config.client_id}"
        f"&scope={config.scopes}"
        f"&redirect_uri={config.oauth_redirect_uri}"
        f"&state={state}"
    )

    log.info(
        "Slack OAuth install initiated: workspace=%s state=%s…",
        workspace_id,
        state[:8],
    )
    return RedirectResponse(url=authorize_url, status_code=302)


@router.get("/oauth/callback")
async def slack_oauth_callback(
    code: str = Query(..., description="Authorization code from Slack"),
    state: str = Query(..., description="CSRF state token"),
) -> RedirectResponse:
    """
    Handle Slack's OAuth callback after user grants permissions.

    Steps:
      1. Validate state token (CSRF protection)
      2. Exchange authorization code for access token
      3. Store access token in Supabase Vault
      4. Redirect user to frontend success page
    """
    config = get_slack_config()

    # ── Validate state ───────────────────────────────────────────────
    state_data = _oauth_states.pop(state, None)
    if not state_data:
        log.warning("Invalid OAuth state: %s…", state[:8])
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    workspace_id = state_data["workspace_id"]
    log.info("Slack OAuth callback: workspace=%s code=%s…", workspace_id, code[:8])

    # ── Exchange code for token ──────────────────────────────────────
    result = await exchange_code_for_token(code)

    if not result.ok:
        return RedirectResponse(
            url=f"{config.frontend_url}/integrations?error=slack_oauth_failed&message={result.error}",
            status_code=302,
        )

    # ── Store token in Supabase Vault ────────────────────────────────
    try:
        vault_id = await store_token_in_vault(result)
    except Exception as exc:
        log.error("Failed to store Slack token in Vault: %s", exc)
        return RedirectResponse(
            url=f"{config.frontend_url}/integrations?error=vault_storage_failed",
            status_code=302,
        )

    log.info(
        "Slack OAuth complete: team=%s (%s) workspace=%s",
        result.team_name,
        result.team_id,
        workspace_id,
    )

    # ── Redirect to frontend success ─────────────────────────────────
    return RedirectResponse(
        url=(
            f"{config.frontend_url}/integrations"
            f"?success=slack_connected"
            f"&team={result.team_name}"
        ),
        status_code=302,
    )


# ═══════════════════════════════════════════════════════════════════════
# 2. Events API Endpoint
# ═══════════════════════════════════════════════════════════════════════

async def _resolve_tenant(team_id: str) -> list[dict]:
    """
    Look up all Locus workspaces connected to a Slack team_id.

    Uses the Supabase REST API to query the sources table.
    Returns a list of dicts with at least 'workspace_id' and 'id'.
    """
    from common.config.slack_config import get_slack_config
    import os

    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not service_key:
        log.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY for tenant lookup")
        return []

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    params = {
        "type": "eq.slack",
        "external_workspace_id": f"eq.{team_id}",
        "select": "id,workspace_id",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{supabase_url}/rest/v1/sources",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        log.error("Failed to resolve tenant for team_id=%s: %s", team_id, exc)
        return []


@router.post("/events")
async def slack_events(
    request: Request,
    raw_body: bytes = Depends(verify_slack_signature),
) -> Response:
    """
    Handle all incoming Slack Events API requests.

    Two request types:
      1. url_verification — Slack challenge-response during app setup
      2. event_callback — A real event (message, reaction, etc.)
         Shaped and pushed to Supabase pgmq immediately, returning 200 OK
         within 3 seconds to avoid Slack's retry loop.
    """
    return await handle_event_payload(raw_body, _resolve_tenant)


# ═══════════════════════════════════════════════════════════════════════
# 3. Integration status helper endpoint
# ═══════════════════════════════════════════════════════════════════════

@router.get("/status/{workspace_id}")
async def slack_integration_status(workspace_id: str) -> JSONResponse:
    """
    Return the current Slack integration status for a workspace.
    Used by the frontend to show connection state.
    """
    integrations = await _resolve_tenant_by_workspace(workspace_id)
    return JSONResponse(
        content={
            "connected": len(integrations) > 0,
            "integrations": integrations,
        },
        status_code=200,
    )


async def _resolve_tenant_by_workspace(workspace_id: str) -> list[dict]:
    """Query sources table for Slack integrations belonging to a workspace."""
    import os

    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not service_key:
        return []

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    params = {
        "workspace_id": f"eq.{workspace_id}",
        "type": "eq.slack",
        "select": "*",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{supabase_url}/rest/v1/sources",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        log.error("Failed to list Slack integrations for workspace=%s: %s", workspace_id, exc)
        return []
