"""
Locus AI — Encrypted OAuth token persistence via Supabase Vault.

RPC wrappers for Vault-encrypted OAuth token read/write (service-role only).
All connectors use this shared module to store and retrieve tokens.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

log = logging.getLogger(__name__)


async def store_secret(
    secret_value: str,
    name: str,
    description: str = "",
) -> str:
    """
    Store a secret in Supabase Vault and return the Vault secret UUID.

    Args:
        secret_value: The plaintext secret (e.g. JSON-serialized OAuth tokens).
        name: Human-readable name (e.g. "slack_bot_token_{team_id}").
        description: Optional description.

    Returns:
        UUID string of the created Vault secret.
    """
    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    url = f"{supabase_url}/rest/v1/rpc/create_vault_secret"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "secret": secret_value,
        "name": name,
        "description": description,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code not in (200, 201):
            log.error(
                "Vault store_secret failed: status=%s body=%s",
                response.status_code,
                response.text,
            )
            raise RuntimeError(
                f"Failed to store secret in Vault: {response.status_code}"
            )
        result = response.json()

    vault_id = result if isinstance(result, str) else str(result)
    log.info("Secret stored in Vault: name=%s vault_id=%s", name, vault_id)
    return vault_id


async def retrieve_secret(vault_id: str) -> Optional[str]:
    """
    Retrieve a decrypted secret from Supabase Vault by its UUID.

    Returns the plaintext secret string, or None if not found.
    """
    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    url = f"{supabase_url}/rest/v1/rpc/read_vault_secret"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            url, json={"secret_id": vault_id}, headers=headers
        )
        if response.status_code not in (200, 201):
            log.error(
                "Vault retrieve_secret failed: status=%s", response.status_code
            )
            return None
        result = response.json()

    if isinstance(result, list) and result:
        return result[0].get("decrypted_secret")
    return result if isinstance(result, str) else None
