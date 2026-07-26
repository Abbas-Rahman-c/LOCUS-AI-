"""
Billing webhook — handles asynchronous events from Stripe.

Updates tenant subscription status when subscriptions are created,
updated, deleted, or when payments fail.
"""
from __future__ import annotations

import logging

import stripe
from fastapi import Request

from common.config import get_stripe_settings
from database.pool import get_admin_db_pool

log = logging.getLogger(__name__)


async def handle_stripe_webhook(request: Request) -> None:
    """
    Process an incoming Stripe webhook event.

    Must use `request.body()` to get the raw bytes for signature verification.
    """
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    settings = get_stripe_settings()

    if not sig_header or not settings.stripe_webhook_secret:
        log.error("Missing Stripe signature or webhook secret is unconfigured")
        raise ValueError("Invalid signature or config")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError as exc:
        log.warning("Stripe signature verification failed: %s", exc)
        raise ValueError("Invalid signature") from exc
    except ValueError as exc:
        log.warning("Invalid Stripe payload: %s", exc)
        raise exc

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        await _handle_subscription_event(data, event_type)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(data)
    else:
        log.debug("Unhandled Stripe event type: %s", event_type)


async def _handle_subscription_event(subscription: dict, event_type: str) -> None:
    """
    Handle subscription created/updated/deleted events.

    Extracts tenant_id from metadata (set during checkout), updates
    the tenants table with customer_id, subscription_id, and status.
    """
    customer_id = subscription.get("customer")
    subscription_id = subscription.get("id")
    status = subscription.get("status")
    metadata = subscription.get("metadata", {})
    tenant_id = metadata.get("tenant_id")

    if not tenant_id:
        # If tenant_id isn't in metadata, we might need to look it up by customer_id
        # But our checkout creates it with metadata. Let's try lookup just in case.
        pool = get_admin_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM tenants WHERE stripe_customer_id = $1", customer_id
            )
            if row:
                tenant_id = str(row["id"])
            else:
                log.error("Webhook error: missing tenant_id in subscription metadata and no matching customer.")
                return

    log.info(
        "Stripe subscription %s for tenant %s (event: %s) -> status: %s",
        subscription_id,
        tenant_id,
        event_type,
        status,
    )

    # Note: 'status' from Stripe is typically: active, past_due, canceled, unpaid, trialing
    # We map these directly to our DB ENUM (which is inactive, active, past_due, canceled, trialing).
    if status == "unpaid":
        status = "past_due"

    # We use admin_db_pool because this route is hit unauthenticated by Stripe.
    pool = get_admin_db_pool()
    query = """
        UPDATE tenants
        SET
            stripe_customer_id = $1,
            stripe_subscription_id = $2,
            subscription_status = $3,
            updated_at = now()
        WHERE id = $4
    """
    async with pool.acquire() as conn:
        await conn.execute(
            query,
            customer_id,
            subscription_id,
            status,
            tenant_id,
        )


async def _handle_payment_failed(invoice: dict) -> None:
    """
    Handle invoice.payment_failed.
    Marks the tenant's subscription status as 'past_due'.
    """
    customer_id = invoice.get("customer")
    subscription_id = invoice.get("subscription")

    if not subscription_id or not customer_id:
        log.warning("Payment failed for invoice without subscription/customer")
        return

    log.info(
        "Stripe payment failed for customer %s, sub %s. Marking past_due.",
        customer_id,
        subscription_id,
    )

    pool = get_admin_db_pool()
    query = """
        UPDATE tenants
        SET
            subscription_status = 'past_due',
            updated_at = now()
        WHERE stripe_subscription_id = $1 OR stripe_customer_id = $2
    """
    async with pool.acquire() as conn:
        await conn.execute(query, subscription_id, customer_id)
