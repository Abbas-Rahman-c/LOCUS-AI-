"""
Notion poll cron entry point.
Business logic lives in: modules/integrations/notion/poller.py ? poll_all_workspaces()
"""
import logging
from modules.integrations.notion.poller import poll_all_workspaces

log = logging.getLogger(__name__)


async def run_notion_poll_job() -> None:
    """Called by scheduler every 5 minutes."""
    log.info("[cron] Notion poll started")
    await poll_all_workspaces()
    log.info("[cron] Notion poll complete")
