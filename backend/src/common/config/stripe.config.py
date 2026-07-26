"""
Stripe API credentials and configuration.

Usage: from common.config import get_stripe_settings
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class StripeSettings(BaseSettings):
    stripe_secret_key: str = Field("", alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field("", alias="STRIPE_WEBHOOK_SECRET")
    stripe_self_serve_price_id: str = Field("", alias="STRIPE_SELF_SERVE_PRICE_ID")
    stripe_team_price_id: str = Field("", alias="STRIPE_TEAM_PRICE_ID")
    stripe_success_url: str = Field(
        "http://localhost:5173/billing/success",
        alias="STRIPE_SUCCESS_URL",
    )
    stripe_cancel_url: str = Field(
        "http://localhost:5173/billing/cancel",
        alias="STRIPE_CANCEL_URL",
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


_settings: StripeSettings | None = None


def get_stripe_settings() -> StripeSettings:
    """Retrieve the cached Stripe config settings."""
    global _settings
    if _settings is None:
        try:
            _settings = StripeSettings()
        except Exception:
            # Fallback for unit testing
            _settings = StripeSettings(
                stripe_secret_key="sk_test_placeholder",
                stripe_webhook_secret="whsec_placeholder",
                stripe_self_serve_price_id="price_self_serve_placeholder",
                stripe_team_price_id="price_team_placeholder",
            )
    return _settings
