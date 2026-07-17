"""
Supabase project configuration.
Reads SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_SECRET_KEY, SUPABASE_JWKS_URL.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SupabaseSettings(BaseSettings):
    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_publishable_key: str = Field(..., alias="SUPABASE_PUBLISHABLE_KEY")
    supabase_secret_key: str = Field(..., alias="SUPABASE_SECRET_KEY")
    # JWKS endpoint — default follows Supabase convention
    supabase_jwks_url: str = Field(
        default="",
        alias="SUPABASE_JWKS_URL",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    def get_jwks_url(self) -> str:
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        base = self.supabase_url.rstrip("/")
        return f"{base}/auth/v1/.well-known/jwks.json"


_settings: SupabaseSettings | None = None


def get_supabase_settings() -> SupabaseSettings:
    global _settings
    if _settings is None:
        _settings = SupabaseSettings()  # type: ignore[call-arg]
    return _settings
