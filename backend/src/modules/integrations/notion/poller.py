"""
Notion page change poller - co-located with the Notion connector.

Notion has no push notifications for this use case, so we poll on a schedule.
jobs/cron/notion_poller.py calls poll_all_workspaces() every 5 minutes.

Detection strategy: diff current page content/last_edited_time against last-seen state
stored in the sources table. Only changed pages are forwarded to the ingestion queue.
"""
from __future__ import annotations
import logging

log = logging.getLogger(__name__)


async def poll_all_workspaces() -> None:
    """Poll Notion for page changes across all connected workspaces."""
    sources = await _get_notion_sources()
    log.info("Notion poll: checking %d workspaces", len(sources))
    for source in sources:
        try:
            await _poll_workspace(source)
        except Exception:
            log.exception("Notion poll failed for source_id=%s", source.get("id"))


async def _get_notion_sources() -> list[dict]:
    """Fetch all active Notion source connections from Supabase."""
    # TODO: SELECT * FROM sources WHERE source_type='notion' AND status='active'
    raise NotImplementedError


async def _poll_workspace(source: dict) -> None:
    """Diff Notion pages for one workspace and enqueue changed pages."""
    # TODO: fetch pages via Notion API, diff vs last_seen_state, enqueue changed pages
    raise NotImplementedError
