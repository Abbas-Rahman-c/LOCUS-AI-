"""
Unit tests for the billing module (Stripe Checkout & Webhooks).
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_tenant, TenantContext
from modules.billing.router import router as billing_router
from modules.billing.service import BillingError
import stripe

app = FastAPI()
app.include_router(billing_router)

# Override the auth dependency for the checkout test
async def override_get_current_tenant():
    return TenantContext(
        user_id="user-123",
        tenant_id="00000000-0000-0000-0000-000000000000",
        role="admin"
    )

app.dependency_overrides[get_current_tenant] = override_get_current_tenant

client = TestClient(app)


def _mock_admin_pool(mock_conn):
    return MagicMock(
        acquire=MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(return_value=False),
            )
        )
    )


@patch("modules.billing.service.stripe.checkout.Session.create")
@patch("modules.billing.service.get_stripe_settings")
def test_checkout_success(mock_get_settings, mock_stripe_create):
    """Test POST /billing/checkout creates a Stripe session."""
    # Setup mocks
    mock_settings = MagicMock()
    mock_settings.stripe_secret_key = "sk_test_123"
    mock_settings.stripe_self_serve_price_id = "price_self_serve"
    mock_settings.stripe_team_price_id = "price_team"
    mock_settings.stripe_success_url = "http://success"
    mock_settings.stripe_cancel_url = "http://cancel"
    mock_get_settings.return_value = mock_settings

    mock_session = MagicMock()
    mock_session.id = "cs_test_123"
    mock_session.url = "https://checkout.stripe.com/pay/cs_test_123"
    mock_stripe_create.return_value = mock_session

    response = client.post("/billing/checkout", json={"plan": "self_serve"})

    assert response.status_code == 200
    assert response.json()["checkout_url"] == mock_session.url
    assert response.json()["session_id"] == mock_session.id

    # Verify tenant_id was passed to stripe correctly
    mock_stripe_create.assert_called_once()
    kwargs = mock_stripe_create.call_args[1]
    assert kwargs["client_reference_id"] == "00000000-0000-0000-0000-000000000000"
    assert kwargs["metadata"]["tenant_id"] == "00000000-0000-0000-0000-000000000000"
    assert kwargs["metadata"]["plan"] == "self_serve"


@patch("modules.billing.service.get_stripe_settings")
def test_checkout_invalid_plan(mock_get_settings):
    """Test checkout rejects invalid plans with 422."""
    response = client.post("/billing/checkout", json={"plan": "enterprise"})
    assert response.status_code == 422


@patch("modules.billing.webhook.stripe.Webhook.construct_event")
@patch("modules.billing.webhook.get_stripe_settings")
@patch("modules.billing.webhook.get_admin_db_pool")
def test_webhook_subscription_created(mock_get_pool, mock_get_settings, mock_construct_event):
    """Test webhook handles customer.subscription.created."""
    mock_settings = MagicMock()
    mock_settings.stripe_webhook_secret = "whsec_123"
    mock_get_settings.return_value = mock_settings

    mock_event = {
        "type": "customer.subscription.created",
        "data": {
            "object": {
                "id": "sub_123",
                "customer": "cus_123",
                "status": "active",
                "metadata": {"tenant_id": "00000000-0000-0000-0000-000000000000"}
            }
        }
    }
    mock_construct_event.return_value = mock_event

    mock_conn = AsyncMock()
    mock_get_pool.return_value = _mock_admin_pool(mock_conn)

    response = client.post(
        "/billing/webhook",
        headers={"Stripe-Signature": "t=123,v1=sig"},
        content=b"raw_body"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    mock_conn.execute.assert_called_once()
    args = mock_conn.execute.call_args[0]
    # Check UPDATE arguments: customer_id, subscription_id, status, tenant_id
    assert args[1] == "cus_123"
    assert args[2] == "sub_123"
    assert args[3] == "active"
    assert args[4] == "00000000-0000-0000-0000-000000000000"


@patch("modules.billing.webhook.stripe.Webhook.construct_event")
@patch("modules.billing.webhook.get_stripe_settings")
@patch("modules.billing.webhook.get_admin_db_pool")
def test_webhook_payment_failed(mock_get_pool, mock_get_settings, mock_construct_event):
    """Test webhook handles invoice.payment_failed."""
    mock_settings = MagicMock()
    mock_settings.stripe_webhook_secret = "whsec_123"
    mock_get_settings.return_value = mock_settings

    mock_event = {
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "subscription": "sub_123",
                "customer": "cus_123"
            }
        }
    }
    mock_construct_event.return_value = mock_event

    mock_conn = AsyncMock()
    mock_get_pool.return_value = _mock_admin_pool(mock_conn)

    response = client.post(
        "/billing/webhook",
        headers={"Stripe-Signature": "t=123,v1=sig"},
        content=b"raw_body"
    )

    assert response.status_code == 200
    
    mock_conn.execute.assert_called_once()
    args = mock_conn.execute.call_args[0]
    assert args[1] == "sub_123"
    assert args[2] == "cus_123"


@patch("modules.billing.webhook.stripe.Webhook.construct_event")
@patch("modules.billing.webhook.get_stripe_settings")
def test_webhook_invalid_signature(mock_get_settings, mock_construct_event):
    """Test webhook returns 400 on invalid signature."""
    mock_settings = MagicMock()
    mock_settings.stripe_webhook_secret = "whsec_123"
    mock_get_settings.return_value = mock_settings

    mock_construct_event.side_effect = stripe.error.SignatureVerificationError("Invalid sig", "sig", b"body")

    response = client.post(
        "/billing/webhook",
        headers={"Stripe-Signature": "t=123,v1=bad_sig"},
        content=b"raw_body"
    )

    assert response.status_code == 400
