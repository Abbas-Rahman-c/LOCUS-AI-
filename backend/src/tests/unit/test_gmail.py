"""
Unit tests for Gmail integration, normalization, and encryption.
"""
from __future__ import annotations
import uuid
import json
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from common.config import get_gmail_settings
from modules.security.encryption import encrypt_data, decrypt_data
from modules.ingestion.envelope.schemas import EventEnvelope
from modules.ingestion.envelope.normalizer import normalize_gmail_message
from modules.integrations.gmail import service

def test_encryption_decryption():
    """Verify that encrypting and decrypting data yields the original string."""
    original_text = "secret oauth token value 12345"
    encrypted = encrypt_data(original_text)
    assert isinstance(encrypted, bytes)
    assert encrypted != original_text.encode()
    
    decrypted = decrypt_data(encrypted)
    assert decrypted == original_text

def test_get_auth_url():
    """Verify that the OAuth URL is correctly generated with required scopes."""
    workspace_id = uuid.uuid4()
    auth_url = service.get_auth_url(workspace_id)
    
    settings = get_gmail_settings()
    assert settings.gmail_client_id in auth_url
    assert settings.gmail_redirect_uri in auth_url
    assert str(workspace_id) in auth_url
    assert "scope=" in auth_url
    assert "gmail.readonly" in auth_url

def test_normalize_gmail_message():
    """Verify that raw Gmail message responses are normalized to standard EventEnvelopes (spec 1.4)."""
    workspace_id = uuid.uuid4()
    
    raw_message = {
        "id": "msg123",
        "threadId": "thread456",
        "snippet": "Hello, this is a test email.",
        "payload": {
            "headers": [
                {"name": "From", "value": "Sender Name <sender@example.com>"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "To", "value": "recipient@example.com"},
                {"name": "Date", "value": "Thu, 9 Jul 2026 14:00:00 +0000"}
            ],
            "body": {
                # urlsafe_b64encode of "Hello, this is the full body!"
                "data": "SGVsbG8sIHRoaXMgaXMgdGhlIGZ1bGwgYm9keSE="
            }
        }
    }
    
    envelope = normalize_gmail_message(raw_message, workspace_id)
    
    # Spec 1.4 contract assertions
    assert isinstance(envelope, EventEnvelope)
    assert envelope.tenant_id == workspace_id           # which customer
    assert envelope.source == "gmail"                   # source system
    assert envelope.source_id == "msg123"               # unique id for dedup
    assert envelope.actor == "sender@example.com"       # who sent it
    assert envelope.thread_ref == "thread456"           # conversation thread
    assert envelope.permission_scope == []              # empty = workspace-wide
    assert envelope.raw_content["subject"] == "Test Subject"
    assert envelope.raw_content["body"] == "Hello, this is the full body!"
    assert envelope.raw_content["to"] == "recipient@example.com"
    assert envelope.received_at is not None             # timestamp our system received

@pytest.mark.asyncio
async def test_handle_callback_success():
    """Verify code exchange, email retrieval, and source saving in handle_callback."""
    workspace_id = uuid.uuid4()
    
    # Mock token exchange response
    token_response = MagicMock()
    token_response.status_code = 200
    token_response.json.return_value = {
        "access_token": "mock_access_token_abc",
        "refresh_token": "mock_refresh_token_xyz",
        "expires_in": 3600,
        "scope": "https://www.googleapis.com/auth/gmail.readonly"
    }
    
    # Mock user info response
    userinfo_response = MagicMock()
    userinfo_response.status_code = 200
    userinfo_response.json.return_value = {
        "email": "user@example.com"
    }
    
    # Create async mock client that acts as context manager
    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=None)
    mock_http_client.post = AsyncMock(return_value=token_response)
    mock_http_client.get = AsyncMock(return_value=userinfo_response)
    
    # Mock database connections
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)  # No existing source
    mock_conn.execute = AsyncMock()
    mock_conn.transaction = MagicMock()
    mock_conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    mock_conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
    
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    
    with patch("modules.integrations.gmail.service.get_db_pool", return_value=mock_pool), \
         patch("modules.integrations.gmail.service.setup_watch", new_callable=AsyncMock) as mock_setup_watch, \
         patch("httpx.AsyncClient", return_value=mock_http_client):
        
        result = await service.handle_callback("auth_code_123", workspace_id)
        
        assert result["email"] == "user@example.com"
        assert "source_id" in result
        mock_setup_watch.assert_called_once()
