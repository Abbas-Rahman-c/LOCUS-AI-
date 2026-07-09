"""
Locus AI — Slack configuration (importable module).

Re-exports from the dot-named config file for clean import paths.
Usage: from common.config.slack_config import get_slack_config
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SlackConfig:
    """Slack-specific configuration, read once from env."""

    client_id: str = field(default_factory=lambda: os.environ.get("SLACK_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.environ.get("SLACK_CLIENT_SECRET", ""))
    signing_secret: str = field(default_factory=lambda: os.environ.get("SLACK_SIGNING_SECRET", ""))
    scopes: str = field(
        default_factory=lambda: os.environ.get(
            "SLACK_SCOPES",
            "channels:history,channels:read,groups:history,groups:read,"
            "im:history,im:read,mpim:history,mpim:read,users:read",
        )
    )
    redirect_uri: str = field(default_factory=lambda: os.environ.get("SLACK_REDIRECT_URI", ""))
    backend_url: str = field(default_factory=lambda: os.environ.get("BACKEND_URL", "http://localhost:8000"))
    frontend_url: str = field(default_factory=lambda: os.environ.get("FRONTEND_URL", "http://localhost:5173"))

    @property
    def oauth_redirect_uri(self) -> str:
        """Full OAuth callback URL (uses override or derives from BACKEND_URL)."""
        return self.redirect_uri or f"{self.backend_url}/api/slack/oauth/callback"


def get_slack_config() -> SlackConfig:
    return SlackConfig()
