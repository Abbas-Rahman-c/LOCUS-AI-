"""
Billing router — POST /billing/checkout

Creates a Stripe Checkout session for the authenticated tenant.
The tenant_id is retrieved exclusively from the JWT-authenticated
session context — never from the request body.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies import TenantContext, get_current_tenant
from modules.billing.schemas import CheckoutRequest, CheckoutResponse
from modules.billing.service import BillingError, create_checkout_session
from modules.billing.webhook import handle_stripe_webhook

log = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    summary="Create a Stripe Checkout session for plan selection",
)
async def checkout(
    body: CheckoutRequest,
    ctx: TenantContext = Depends(get_current_tenant),
) -> CheckoutResponse:
    """
    Authenticated endpoint: starts a Stripe Checkout session.

    The caller sends only the desired plan ('self_serve' or 'team').
    The tenant_id is pulled from the authenticated session — this is
    critical so that payments always map back to the correct tenant.
    """
    try:
        result = await create_checkout_session(
            tenant_id=ctx.tenant_id,
            plan=body.plan,
        )
    except BillingError as exc:
        log.error("Checkout failed for tenant=%s: %s", ctx.tenant_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return CheckoutResponse(
        checkout_url=result["checkout_url"],
        session_id=result["session_id"],
    )


@router.post(
    "/webhook",
    summary="Stripe Webhook Event Listener",
)
async def stripe_webhook(request: Request) -> dict:
    """
    Receives events directly from Stripe.
    This endpoint is unauthenticated by design; it validates the Stripe
    signature header using the webhook secret instead.
    """
    try:
        await handle_stripe_webhook(request)
        return {"status": "success"}
    except ValueError as exc:
        log.warning("Webhook validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:
        log.exception("Unexpected error processing webhook")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook failed"
        ) from exc
