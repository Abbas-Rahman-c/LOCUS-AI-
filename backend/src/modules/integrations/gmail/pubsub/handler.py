"""
Google Pub/Sub push message handler.
"""
from __future__ import annotations
from typing import Dict, Any
from modules.integrations.gmail.service import process_pubsub_notification


async def handle_gmail_pubsub_push(payload: Dict[str, Any]) -> None:
    """Delegate processing to the Gmail service."""
    await process_pubsub_notification(payload)
