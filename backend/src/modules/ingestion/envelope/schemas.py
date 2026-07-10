"""
EventEnvelope Pydantic model — matches spec 1.4 exactly.
Every connector must output exactly this shape, no matter the source.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone


class EventEnvelope(BaseModel):
    tenant_id: UUID = Field(..., description="Which customer / workspace this belongs to")
    source: str = Field(..., description="Source system: 'gmail' | 'slack' | 'notion'")
    source_id: str = Field(..., description="Unique ID from that system — dedup checks against this")
    actor: str = Field(..., description="Who sent/wrote it (e.g. sender email, Slack user ID)")
    thread_ref: Optional[str] = Field(None, description="Which conversation/thread/page it belongs to")
    permission_scope: List[str] = Field(
        default_factory=list,
        description="Who's allowed to see this event (list of user IDs or roles). Empty = workspace-wide."
    )
    raw_content: Dict[str, Any] = Field(..., description="The actual message/email/page text and metadata")
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of when our system received this event"
    )
