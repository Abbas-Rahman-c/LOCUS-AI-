from modules.feedback.schemas import FeedbackRequest
from database.tenant_context import tenant_connection
import logging

logger = logging.getLogger(__name__)


async def store_feedback(request: FeedbackRequest):
    """
    Persist a thumbs-up / thumbs-down signal into the feedback_events table.
    This data feeds directly into the evaluation harness (golden set scoring).

    When the database pool is unavailable (e.g. no network), the feedback is
    logged at WARNING level so it is still captured in server logs and can be
    backfilled later.  The endpoint returns success either way — we never want
    a database outage to block the user from rating an answer.
    """
    query = """
        INSERT INTO feedback_events (tenant_id, query, synthesized_answer, signal, comment)
        VALUES ($1, $2, $3, $4, $5)
    """
    try:
        async with tenant_connection(request.tenant_id) as conn:
            await conn.execute(
                query,
                request.tenant_id,
                request.query,
                request.synthesized_answer,
                request.signal,
                request.comment,
            )
        logger.info(
            f"Stored feedback signal={request.signal} for query={request.query!r}"
        )
    except RuntimeError as e:
        # Pool not initialised
        logger.warning(
            "DB pool not initialised — logging feedback instead: "
            f"signal={request.signal} query={request.query!r} ({e})"
        )
    except Exception as e:
        logger.error(f"Failed to store feedback: {e}")
        # Log but don't crash — feedback must never block the user experience
