"""
Digest cron entry point.
Business logic lives in: modules/digest/service.py ? generate_team_pulse()
"""
import logging
from modules.digest.service import generate_team_pulse

log = logging.getLogger(__name__)


async def run_digest_job() -> None:
    """Called by scheduler every Monday 09:00 UTC."""
    log.info("[cron] weekly digest job started")
    await generate_team_pulse()
    log.info("[cron] weekly digest job complete")
