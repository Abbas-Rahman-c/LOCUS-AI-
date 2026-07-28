"""
Digest cron entry point.

NOT YET IMPLEMENTED as a real scheduled job. generate_team_pulse() requires
a specific tenant_id and permission_scopes — it's built for the on-demand
GET /digest endpoint (one authenticated caller, one tenant), not for an
unattended cron job that would need to loop over every active tenant itself.
That "for each active tenant, generate and deliver a digest" logic doesn't
exist yet. This stays a safe no-op until it's built for real, rather than
crashing weekly with a missing-arguments error.
"""
import logging

log = logging.getLogger(__name__)


async def run_digest_job() -> None:
    """Called by scheduler every Monday 09:00 UTC. Currently a no-op — see module docstring."""
    log.info("[cron] weekly digest job fired, but automated cross-tenant digest generation is not yet implemented — skipping")