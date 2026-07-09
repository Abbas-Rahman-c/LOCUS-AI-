"""
Locus AI — Slack OAuth exchange and token storage.

Handles the code-for-token exchange with Slack and persists
the bot token into Supabase Vault via the shared token_store.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from common.config.slack_config import get_slack_config
from database.vault.token_store import store_secret

log = logging.getLogger(__name__)


@dataclass
class SlackOAuthResult:
    """Result of a successful Slack OAuth exchange."""
    ok: bool
    access_token: str
    team_id: str
    team_name: str
    bot_user_id: str
    scope: str
    installed_by: str
    vault_id: Optional[str] = None
    error: Optional[str] = None


async def exchange_code_for_token(code: str) -> SlackOAuthResult:
    """
    Exchange a Slack authorization code for a bot access token.

    Returns a SlackOAuthResult with the token details.
    """
    config = get_slack_config()
    token_url = "https://slack.com/api/oauth.v2.access"
    token_payload = {
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "code": code,
        "redirect_uri": config.oauth_redirect_uri,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(token_url, data=token_payload)
        resp.raise_for_status()
        data = resp.json()

    if not data.get("ok") or not data.get("access_token"):
        error_msg = data.get("error", "Unknown Slack OAuth error")
        log.error("Slack OAuth token exchange failed: %s", error_msg)
        return SlackOAuthResult(
            ok=False, access_token="", team_id="", team_name="",
            bot_user_id="", scope="", installed_by="", error=error_msg,
        )

    team = data.get("team", {})
    authed_user = data.get("authed_user", {})

    return SlackOAuthResult(
        ok=True,
        access_token=data["access_token"],
        team_id=team.get("id", ""),
        team_name=team.get("name", ""),
        bot_user_id=data.get("bot_user_id", ""),
        scope=data.get("scope", ""),
        installed_by=authed_user.get("id", ""),
    )


async def store_token_in_vault(result: SlackOAuthResult) -> str:
    """
    Persist the Slack bot token into Supabase Vault.

    Returns the Vault secret UUID.
    """
    token_bundle = json.dumps({
        "access_token": result.access_token,
        "bot_user_id": result.bot_user_id,
        "team_id": result.team_id,
        "team_name": result.team_name,
        "scope": result.scope,
        "installed_by": result.installed_by,
        "stored_at": time.time(),
    })

    vault_id = await store_secret(
        secret_value=token_bundle,
        name=f"slack_bot_token_{result.team_id}",
        description=f"Slack bot token for {result.team_name} ({result.team_id})",
    )
    result.vault_id = vault_id
    log.info("Slack token stored in Vault: team=%s vault_id=%s", result.team_id, vault_id)
    return vault_id
