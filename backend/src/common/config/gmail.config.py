"""
Gmail OAuth credentials + Google Pub/Sub configuration.
"""
from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class GmailSettings(BaseSettings):
    gmail_client_id: str = Field("mock_client_id", alias="GMAIL_CLIENT_ID")
    gmail_client_secret: str = Field("mock_client_secret", alias="GMAIL_CLIENT_SECRET")
    gmail_pubsub_topic: str = Field("projects/mock-project/topics/gmail-push", alias="GMAIL_PUBSUB_TOPIC")
    gmail_redirect_uri: str = Field("http://localhost:8000/api/v1/integrations/gmail/callback", alias="GMAIL_REDIRECT_URI")
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

_settings: GmailSettings | None = None

def get_gmail_settings() -> GmailSettings:
    """Retrieve the cached Gmail config settings."""
    global _settings
    if _settings is None:
        # Load setting values from environment or dotenv file
        try:
            _settings = GmailSettings()
        except Exception:
            # Fallback settings for unit testing
            _settings = GmailSettings(
                gmail_client_id="mock_client_id",
                gmail_client_secret="mock_client_secret",
                gmail_pubsub_topic="projects/mock-project/topics/gmail-push",
                gmail_redirect_uri="http://localhost:8000/api/v1/integrations/gmail/callback"
            )
    return _settings
