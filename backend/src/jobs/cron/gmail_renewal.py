"""
Gmail watch renewal cron entry point.
Business logic lives in: modules/integrations/gmail/watch_renewal/renewer.py ? renew_all_watches()
"""
import logging
from modules.integrations.gmail.watch_renewal.renewer import renew_all_watches

log = logging.getLogger(__name__)


async def run_gmail_renewal_job() -> None:
    """Called by scheduler every 6 days."""
    log.info("[cron] Gmail watch renewal started")
    await renew_all_watches()
    log.info("[cron] Gmail watch renewal complete")
