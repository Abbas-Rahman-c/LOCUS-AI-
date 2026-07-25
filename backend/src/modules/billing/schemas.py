"""
Billing request/response schemas.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CheckoutRequest(BaseModel):
    """Body sent by the client to start a Stripe Checkout session."""
    plan: str = Field(
        ...,
        description="Plan tier to subscribe to: 'self_serve' or 'team'",
        pattern="^(self_serve|team)$",
    )


class CheckoutResponse(BaseModel):
    """URL the client should redirect the browser to."""
    checkout_url: str
    session_id: str
