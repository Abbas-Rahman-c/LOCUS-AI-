"""
Unit tests for Gmail watch renewal.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.integrations.gmail.watch_renewal import renewer


@pytest.mark.asyncio
async def test_renew_single_watch_updates_source_state() -> None:
    source_id = uuid.uuid4()
    source = {
        "id": source_id,
        "tenant_id": uuid.uuid4(),
        "cursor_state": {
            "email_address": "user@example.com",
            "history_id": "123456",
        },
        "watch_expiry": datetime.now(timezone.utc),
    }

    watch_response = MagicMock()
    watch_response.status_code = 200
    watch_response.json.return_value = {
        "historyId": "654321",
        "expiration": "1893456000000",
    }

    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=None)
    mock_http_client.post = AsyncMock(return_value=watch_response)

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.transaction = MagicMock()
    mock_conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    mock_conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)

    settings = MagicMock(gmail_pubsub_topic="projects/mock/topics/gmail-push")

    with patch(
        "modules.integrations.gmail.watch_renewal.renewer.tenant_conn",
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        ),
    ), \
         patch("modules.integrations.gmail.watch_renewal.renewer.get_db_pool"), \
         patch("modules.integrations.gmail.watch_renewal.renewer.get_gmail_settings", return_value=settings), \
         patch("modules.integrations.gmail.watch_renewal.renewer._get_valid_access_token", new_callable=AsyncMock, return_value="access-token"), \
         patch("httpx.AsyncClient", return_value=mock_http_client):
        await renewer._renew_single_watch(source)

    mock_conn.execute.assert_awaited_once()
    sql, config_json, executed_source_id = mock_conn.execute.await_args.args

    assert "UPDATE source_connections" in sql
    assert executed_source_id == source_id

    stored_config = json.loads(config_json)
    assert stored_config["email_address"] == "user@example.com"
    assert stored_config["history_id"] == "654321"
    assert stored_config["watch_expiry"] == 1893456000000
