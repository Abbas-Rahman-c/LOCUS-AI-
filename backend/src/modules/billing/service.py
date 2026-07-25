"""
Billing service — Stripe Checkout session creation and plan management.

Handles mapping between our plan tiers and Stripe Price IDs,
and creates Checkout Sessions with the tenant_id baked into
both client_reference_id and metadata for reliable webhook mapping.
"""
from __future__ import annotations

import logging

import stripe

from common.config import get_stripe_settings

log = logging.getLogger(__name__)


class BillingError(Exception):
    """Raised when a billing operation fails."""


def _configure_stripe() -> None:
    """Set the Stripe API key from config (idempotent)."""
    settings = get_stripe_settings()
    if not settings.stripe_secret_key:
        raise BillingError("STRIPE_SECRET_KEY is not configured")
    stripe.api_key = settings.stripe_secret_key


def _resolve_price_id(plan: str) -> str:
    """Map a plan name to its Stripe Price ID."""
    settings = get_stripe_settings()
    price_map = {
        "self_serve": settings.stripe_self_serve_price_id,
        "team": settings.stripe_team_price_id,
    }
    price_id = price_map.get(plan)
    if not price_id:
        raise BillingError(f"Unknown plan: {plan!r}")
    return price_id


async def create_checkout_session(
    tenant_id: str,
    plan: str,
) -> dict:
    """
    Create a Stripe Checkout Session for the given tenant and plan.

    The tenant_id is passed through:
      - client_reference_id → available on the session object after completion
      - metadata.tenant_id  → available in all webhook events for this session

    Returns a dict with 'checkout_url' and 'session_id'.
    """
    _configure_stripe()
    price_id = _resolve_price_id(plan)

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            client_reference_id=tenant_id,
            metadata={"tenant_id": tenant_id, "plan": plan},
            subscription_data={
                "metadata": {"tenant_id": tenant_id, "plan": plan},
            },
            success_url=get_stripe_settings().stripe_success_url
            + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=get_stripe_settings().stripe_cancel_url,
        )
    except stripe.error.StripeError as exc:
        log.error("Stripe Checkout session creation failed: %s", exc)
        raise BillingError(f"Stripe error: {exc}") from exc

    log.info(
        "Created Stripe Checkout session=%s for tenant=%s plan=%s",
        session.id,
        tenant_id,
        plan,
    )
    return {"checkout_url": session.url, "session_id": session.id}
