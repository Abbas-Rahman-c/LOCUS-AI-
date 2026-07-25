from pydantic import BaseModel
from typing import Optional


class FeedbackRequest(BaseModel):
    query: str
    synthesized_answer: str
    signal: str  # "up" or "down"
    comment: Optional[str] = None
    # tenant_id intentionally NOT a field here - it must come exclusively
    # from the authenticated TenantContext (see router.py), never from the
    # caller. Accepting it in the request body was a real, unauthenticated
    # tenant-write bypass: this endpoint had no Depends(get_current_tenant)
    # at all, so any caller with no token could attribute feedback - and,
    # via tenant_connection(), the RLS session GUC itself - to any tenant_id
    # they typed in.