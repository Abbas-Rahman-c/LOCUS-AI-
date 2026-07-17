from pydantic import BaseModel
from typing import Optional

class FeedbackRequest(BaseModel):
    query: str
    synthesized_answer: str
    signal: str  # "up" or "down"
    comment: Optional[str] = None
    tenant_id: str
