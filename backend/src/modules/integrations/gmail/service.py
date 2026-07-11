"""
Gmail watch() setup, incremental sync, watch renewal job.
"""
from __future__ import annotations
import base64
import logging
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from urllib.parse import urlencode
import httpx

from database.connection import get_db_pool
from common.config import get_gmail_settings
from modules.security.encryption import encrypt_string, decrypt_string
from modules.ingestion.envelope.normalizer import normalize_gmail_message
from modules.ingestion.raw_events.store import store_raw_event
from modules.integrations.gmail.oauth_state import create_state
from pgmq.producer import enqueue_event

log = logging.getLogger(__name__)


def get_auth_url(workspace_id: uuid.UUID) -> str:
    """Build the Google OAuth2 authorization URL."""
    settings = get_gmail_settings()
    scopes = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid"
    ]
    scope_str = " ".join(scopes)

    params = {
        "client_id": settings.gmail_client_id,
        "redirect_uri": settings.gmail_redirect_uri,
        "response_type": "code",
        "scope": scope_str,
        "state": create_state(workspace_id),
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def handle_callback(code: str, workspace_id: uuid.UUID) -> Dict[str, Any]:
    """Exchange auth code for tokens, fetch email, and save source."""
    settings = get_gmail_settings()
    pool = get_db_pool()

    # 1. Exchange authorization code for tokens
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.gmail_client_id,
                "client_secret": settings.gmail_client_secret,
                "code": code,
                "redirect_uri": settings.gmail_redirect_uri,
                "grant_type": "authorization_code",
            }
        )
        if resp.status_code != 200:
            log.error("Failed to exchange OAuth code: %s", resp.text)
            raise RuntimeError(f"OAuth exchange failed: {resp.text}")

        token_data = resp.json()
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        scopes = token_data.get("scope", "").split(" ")

        # 2. Get user info (email address)
        user_info_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if user_info_resp.status_code != 200:
            log.error("Failed to fetch userinfo: %s", user_info_resp.text)
            raise RuntimeError(f"Failed to fetch user email: {user_info_resp.text}")

        user_info = user_info_resp.json()
        email = user_info.get("email")
        if not email:
            raise RuntimeError("Email address not returned by Google OAuth")

    # 3. Save workspace source & tokens inside transaction
    async with pool.acquire() as conn:
        async with conn.transaction():
            # The Gmail address is the provider's external workspace identity.
            existing_source = await conn.fetchrow(
                """
                SELECT id, oauth_token_ref FROM source_connections
                WHERE tenant_id = $1 AND source = 'gmail'
                  AND external_workspace_id = $2
                """,
                workspace_id, email
            )

            if existing_source:
                source_id = existing_source["id"]
                await conn.execute(
                    """
                    UPDATE source_connections SET status = 'active' WHERE id = $1
                    """,
                    source_id
                )
            else:
                source_id = uuid.uuid4()
                config = json.dumps({"email_address": email, "history_id": None})
                await conn.execute(
                    """
                    INSERT INTO source_connections
                    (id, tenant_id, source, external_workspace_id, status, metadata)
                    VALUES ($1, $2, 'gmail', $3, 'active', $4::jsonb)
                    """,
                    source_id, workspace_id, email, config
                )

            # Encrypt tokens
            encrypted_access = encrypt_string(access_token)
            encrypted_refresh = encrypt_string(refresh_token) if refresh_token else None

            token_ref = existing_source["oauth_token_ref"] if existing_source else None
            if token_ref:
                await conn.execute(
                    """UPDATE oauth_tokens
                       SET access_token = $1, refresh_token = COALESCE($2, refresh_token),
                           expires_at = $3, scopes = $4, updated_at = NOW() WHERE id = $5""",
                    encrypted_access, encrypted_refresh, expires_at, scopes, token_ref,
                )
            else:
                token_ref = uuid.uuid4()
                await conn.execute(
                """
                INSERT INTO oauth_tokens (id, access_token, refresh_token, expires_at, scopes, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                """,
                    token_ref, encrypted_access, encrypted_refresh, expires_at, scopes
                )
                await conn.execute(
                    "UPDATE source_connections SET oauth_token_ref = $1 WHERE id = $2",
                    token_ref, source_id,
                )

    # 4. Setup watch (push notification) for this inbox
    try:
        await setup_watch(source_id)
    except Exception as e:
        log.warning("Failed to setup Gmail watch (Google Pub/Sub): %s. Sync will fall back to manual sync.", e)
        # Even if watch fails, we return success so the user can test using manual sync!
        # Let's save a placeholder history_id in config if it wasn't set by watch
        async with pool.acquire() as conn:
            source_row = await conn.fetchrow("SELECT metadata FROM source_connections WHERE id = $1", source_id)
            if source_row:
                config = json.loads(source_row["metadata"])
                if "history_id" not in config:
                    config["history_id"] = 1  # default start history id
                    await conn.execute(
                        "UPDATE source_connections SET metadata = $1::jsonb WHERE id = $2",
                        json.dumps(config), source_id
                    )

    return {"source_id": str(source_id), "email": email}


async def setup_watch(source_id: uuid.UUID) -> Dict[str, Any]:
    """Call Google watch() API and update source_connections with subscription metadata."""
    settings = get_gmail_settings()
    pool = get_db_pool()

    async with pool.acquire() as conn:
        access_token = await _get_valid_access_token(source_id, conn)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/watch",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "topicName": settings.gmail_pubsub_topic,
                    "labelIds": ["INBOX"]
                }
            )
            if resp.status_code != 200:
                log.error("Failed to register Gmail watch: %s", resp.text)
                raise RuntimeError(f"Gmail watch setup failed: {resp.text}")

            watch_data = resp.json()
            history_id = watch_data.get("historyId")
            expiration_ms = int(watch_data.get("expiration", 0))

            # Convert expiration milliseconds to timestamp
            watch_expiry = datetime.fromtimestamp(expiration_ms / 1000.0, tz=timezone.utc)

            # Update source_connections with latest history_id & watch_expiry
            source_row = await conn.fetchrow("SELECT metadata FROM source_connections WHERE id = $1", source_id)
            config = json.loads(source_row["metadata"]) if source_row else {}
            config["history_id"] = history_id

            await conn.execute(
                """
                UPDATE source_connections
                SET watch_expiry = $1, metadata = $2::jsonb
                WHERE id = $3
                """,
                watch_expiry, json.dumps(config), source_id
            )

            log.info("Successfully established watch for Gmail source_id=%s, historyId=%s, expires=%s",
                     source_id, history_id, watch_expiry)
            return watch_data


async def process_pubsub_notification(payload: Dict[str, Any]) -> None:
    """Handle Gmail push notification, list history, fetch messages, normalize and enqueue."""
    # Pub/Sub payload structure: {"message": {"data": "base64_encoded_str", "messageId": "..."}}
    msg_data = payload.get("message", {}).get("data")
    if not msg_data:
        log.warning("Pub/Sub push payload does not contain message data")
        return

    try:
        decoded_bytes = base64.b64decode(msg_data)
        notification = json.loads(decoded_bytes.decode("utf-8"))
    except Exception as e:
        log.error("Failed to decode Pub/Sub data payload: %s", e)
        return

    email = notification.get("emailAddress")
    new_history_id = notification.get("historyId")

    if not email:
        log.warning("Gmail notification missing emailAddress")
        return

    pool = get_db_pool()
    async with pool.acquire() as conn:
        # Find active Gmail source matching emailAddress
        source_row = await conn.fetchrow(
            """
            SELECT id, tenant_id, metadata FROM source_connections
            WHERE source = 'gmail' AND status = 'active'
              AND metadata->>'email_address' = $1
            """,
            email
        )
        if not source_row:
            log.warning("No active Gmail source connection found for email: %s", email)
            return

        source_id = source_row["id"]
        workspace_id = source_row["tenant_id"]
        config = json.loads(source_row["metadata"])
        last_history_id = config.get("history_id")

        # Get valid OAuth access token
        try:
            access_token = await _get_valid_access_token(source_id, conn)
        except Exception as e:
            log.error("Cannot retrieve valid access token for email %s: %s", email, e)
            return

        # If no last history_id stored, we cannot perform incremental sync.
        # Save the new history_id and exit (or full sync initial batch if desired).
        if not last_history_id:
            config["history_id"] = new_history_id
            await conn.execute(
                "UPDATE source_connections SET metadata = $1::jsonb WHERE id = $2",
                json.dumps(config), source_id
            )
            log.info("Initialized historyId for %s to %s", email, new_history_id)
            return

        # Fetch changes using Gmail History API
        history_url = f"https://gmail.googleapis.com/gmail/v1/users/me/history?startHistoryId={last_history_id}"
        async with httpx.AsyncClient() as client:
            history_resp = await client.get(
                history_url,
                headers={"Authorization": f"Bearer {access_token}"}
            )

            # Check for expired history (404/410)
            if history_resp.status_code in (404, 410):
                log.warning("History ID %s is expired or out of date. Performing fallback full list.", last_history_id)
                # Fallback: get recent message ids and process them
                recent_messages = await _fetch_recent_messages(client, access_token)
                for msg_meta in recent_messages:
                    await _fetch_normalize_and_enqueue(client, access_token, msg_meta["id"], workspace_id)

                config["history_id"] = new_history_id
                await conn.execute(
                    "UPDATE source_connections SET metadata = $1::jsonb WHERE id = $2",
                    json.dumps(config), source_id
                )
                return

            if history_resp.status_code != 200:
                log.error("Failed to query Gmail History API: %s", history_resp.text)
                return

            history_data = history_resp.json()
            histories = history_data.get("history", [])

            # Process added messages
            processed_message_ids = set()
            for history in histories:
                messages_added = history.get("messagesAdded", [])
                for item in messages_added:
                    msg_meta = item.get("message", {})
                    msg_id = msg_meta.get("id")
                    if msg_id and msg_id not in processed_message_ids:
                        processed_message_ids.add(msg_id)
                        await _fetch_normalize_and_enqueue(client, access_token, msg_id, workspace_id)

            # Update history_id in metadata
            config["history_id"] = new_history_id
            await conn.execute(
                "UPDATE source_connections SET metadata = $1::jsonb WHERE id = $2",
                json.dumps(config), source_id
            )
            log.info("Processed %d new emails for %s. Updated historyId to %s",
                     len(processed_message_ids), email, new_history_id)


async def _fetch_recent_messages(client: httpx.AsyncClient, access_token: str) -> list[dict]:
    """Retrieve list of recent message metadata when history ID is expired."""
    list_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=10"
    resp = await client.get(list_url, headers={"Authorization": f"Bearer {access_token}"})
    if resp.status_code == 200:
        return resp.json().get("messages", [])
    return []


async def manual_sync(workspace_id: uuid.UUID, max_messages: int = 10) -> int:
    """
    DEV helper: Fetch the N most recent Gmail messages for a workspace,
    normalize each one to EventEnvelope, store raw event, and enqueue.
    Returns the count of messages ingested.
    No Pub/Sub required — useful for local testing.
    """
    pool = get_db_pool()
    async with pool.acquire() as conn:
        source_row = await conn.fetchrow(
            """
            SELECT id, metadata FROM source_connections
            WHERE tenant_id = $1 AND source = 'gmail' AND status = 'active'
            LIMIT 1
            """,
            workspace_id
        )
        if not source_row:
            raise ValueError(f"No active Gmail source found for workspace {workspace_id}")

        source_id = source_row["id"]
        config = json.loads(source_row["metadata"])

        try:
            access_token = await _get_valid_access_token(source_id, conn)
        except Exception as e:
            raise ValueError(f"Cannot retrieve valid access token: {e}")

    # Fetch recent messages and ingest
    count = 0
    async with httpx.AsyncClient() as client:
        list_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults={max_messages}"
        list_resp = await client.get(list_url, headers={"Authorization": f"Bearer {access_token}"})
        if list_resp.status_code != 200:
            raise RuntimeError(f"Failed to list messages: {list_resp.text}")

        messages = list_resp.json().get("messages", [])
        log.info("Manual sync: found %d recent messages for workspace %s", len(messages), workspace_id)

        for msg_meta in messages:
            await _fetch_normalize_and_enqueue(client, access_token, msg_meta["id"], workspace_id)
            count += 1

        # Update history_id from Gmail profile
        profile_resp = await client.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if profile_resp.status_code == 200:
            new_history_id = profile_resp.json().get("historyId")
            if new_history_id:
                config["history_id"] = new_history_id
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE source_connections SET metadata = $1::jsonb WHERE id = $2",
                        json.dumps(config), source_id
                    )
                log.info("Updated historyId to %s for workspace %s", new_history_id, workspace_id)

    return count


async def _fetch_normalize_and_enqueue(
    client: httpx.AsyncClient,
    access_token: str,
    message_id: str,
    workspace_id: uuid.UUID
) -> None:
    """Fetch full Gmail message details, convert to EventEnvelope, save raw event, and enqueue."""
    try:
        msg_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}?format=full"
        resp = await client.get(msg_url, headers={"Authorization": f"Bearer {access_token}"})
        if resp.status_code != 200:
            log.error("Failed to fetch message details for %s: %s", message_id, resp.text)
            return

        raw_msg = resp.json()

        # 1. Normalize
        envelope = normalize_gmail_message(raw_msg, workspace_id)
        envelope_dict = envelope.model_dump()

        # Serialize datetime and UUID fields for pgmq JSON payload
        envelope_dict["received_at"] = envelope.received_at.isoformat()
        envelope_dict["tenant_id"] = str(envelope.tenant_id)

        # 2. Persist raw event (encrypted payload)
        await store_raw_event(envelope_dict)

        # 3. Enqueue to PGMQ
        await enqueue_event(envelope_dict)

        log.info("Normalized, stored and enqueued Gmail message: %s", message_id)
    except Exception as e:
        log.exception("Error processing message %s: %s", message_id, e)


async def _get_valid_access_token(source_id: uuid.UUID, conn) -> str:
    """Retrieve and verify access token, refreshing it if expired.

    Looks up the token via source_connections.oauth_token_ref so we never rely
    on a non-existent oauth_tokens.source_id column.
    """
    token_row = await conn.fetchrow(
        """
        SELECT ot.access_token, ot.refresh_token, ot.expires_at
        FROM oauth_tokens ot
        JOIN source_connections sc ON sc.oauth_token_ref = ot.id
        WHERE sc.id = $1
        """,
        source_id
    )
    if not token_row:
        raise ValueError(f"No tokens found for source_id {source_id}")

    access_token = decrypt_string(token_row["access_token"])
    refresh_token = decrypt_string(token_row["refresh_token"]) if token_row["refresh_token"] else None
    expires_at = token_row["expires_at"]

    # Check if access token is expired or expires in next 60 seconds
    if expires_at and expires_at <= datetime.now(timezone.utc) + timedelta(seconds=60):
        if not refresh_token:
            raise ValueError(f"Gmail access token for source {source_id} is expired and no refresh token exists")

        settings = get_gmail_settings()
        async with httpx.AsyncClient() as client:
            refresh_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.gmail_client_id,
                    "client_secret": settings.gmail_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                }
            )
            if refresh_resp.status_code != 200:
                log.error("Failed to refresh Gmail token: %s", refresh_resp.text)
                raise RuntimeError(f"Token refresh failed: {refresh_resp.text}")

            refresh_data = refresh_resp.json()
            new_access_token = refresh_data["access_token"]
            expires_in = refresh_data.get("expires_in", 3600)
            new_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            # Save new access token via the join path
            encrypted_access = encrypt_string(new_access_token)
            await conn.execute(
                """
                UPDATE oauth_tokens ot
                SET access_token = $1, expires_at = $2, updated_at = NOW()
                FROM source_connections sc
                WHERE sc.oauth_token_ref = ot.id AND sc.id = $3
                """,
                encrypted_access, new_expires_at, source_id
            )
            log.info("Refreshed access token for source_id=%s", source_id)
            return new_access_token

    return access_token
