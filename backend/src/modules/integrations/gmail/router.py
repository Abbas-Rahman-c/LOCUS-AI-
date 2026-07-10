"""
Gmail OAuth routes + Pub/Sub push endpoint.
"""
from __future__ import annotations
import logging
import uuid
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from modules.integrations.gmail import service
from modules.integrations.gmail.pubsub.handler import handle_gmail_pubsub_push

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/integrations/gmail", tags=["Gmail Integration"])


@router.get("/connect")
async def connect_gmail(
    workspace_id: uuid.UUID = Query(..., description="ID of the workspace connecting Gmail"),
    redirect: bool = Query(True, description="Whether to redirect to Google authorization page directly")
):
    """Start Gmail OAuth flow - returns redirect or the authorization URL."""
    try:
        url = service.get_auth_url(workspace_id)
        if redirect:
            return RedirectResponse(url)
        return {"auth_url": url}
    except Exception as e:
        log.exception("Failed to build OAuth URL")
        raise HTTPException(status_code=500, detail=f"Failed to generate Auth URL: {e}")


@router.get("/callback")
async def oauth_callback(
    code: str = Query(..., description="Google authorization code"),
    state: str = Query(..., description="Workspace ID state parameter")
):
    """Callback endpoint for Google OAuth redirection."""
    try:
        workspace_id = uuid.UUID(state)
        result = await service.handle_callback(code, workspace_id)
        return {
            "status": "success",
            "message": "Gmail inbox connected successfully and push watch registered",
            "workspace_id": str(workspace_id),
            "email": result["email"],
            "source_id": result["source_id"]
        }
    except Exception as e:
        log.exception("Failed to process Google OAuth callback")
        raise HTTPException(status_code=400, detail=f"OAuth connection failed: {e}")


@router.post("/pubsub")
async def pubsub_push(payload: dict):
    """Google Pub/Sub push notification endpoint."""
    try:
        await handle_gmail_pubsub_push(payload)
        return {"status": "success", "message": "Notification processed"}
    except Exception as e:
        log.exception("Error processing Google Pub/Sub push notification")
        # Return 200 to prevent Pub/Sub infinite retries for parsing errors,
        # but feel free to change to 500 if DB is down.
        return {"status": "error", "message": str(e)}


@router.post("/manual-sync")
async def manual_sync(
    workspace_id: uuid.UUID = Query(..., description="Workspace ID to sync Gmail for")
):
    """
    DEV-ONLY: Manually trigger a Gmail history sync for the given workspace.
    Useful for testing without Pub/Sub — just send an email, then call this endpoint.
    Returns a summary of events ingested.
    """
    try:
        count = await service.manual_sync(workspace_id)
        return {
            "status": "success",
            "workspace_id": str(workspace_id),
            "messages_ingested": count
        }
    except Exception as e:
        log.exception("Manual sync failed for workspace %s", workspace_id)
        raise HTTPException(status_code=500, detail=f"Manual sync failed: {e}")
