"""
Digest cron entry point.
Business logic lives in: modules/digest/service.py -> generate_team_pulse()

Note: the weekly digest is also available on-demand via GET /digest.
This cron job is for scheduled push delivery when that's needed.
For MVP, the frontend pulls the digest on demand; this job is a no-op
placeholder so the scheduler registration doesn't crash.
"""
import logging

log = logging.getLogger(__name__)


async def run_digest_job() -> None:
    """Called by scheduler every Monday 09:00 UTC.

    MVP: digest is served on-demand via GET /digest endpoint.
    Push delivery (email/Slack) is a follow-up — this stub ensures the
    scheduler starts cleanly without an import error.
    """
    log.info("[cron] weekly digest job fired — delivery via GET /digest endpoint (MVP)")
