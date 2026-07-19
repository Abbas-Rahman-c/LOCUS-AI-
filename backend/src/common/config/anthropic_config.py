"""
Locus AI — Anthropic configuration (importable module).

Real implementation for the dot-named anthropic.config.py stub, following
the database.config.py -> database_config.py pattern: the dotted file is a
pointer, this is the module other code actually imports.

Usage: from common.config.anthropic_config import get_anthropic_client, get_anthropic_model

MVP uses a single configured model for every Claude call (no per-stage
model selection yet). Unlike the other configs in this package, missing
ANTHROPIC_API_KEY / ANTHROPIC_MODEL raise immediately instead of silently
defaulting to "" — an unset key must never reach the Anthropic client.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from anthropic import AsyncAnthropic


class AnthropicConfigError(RuntimeError):
    """Raised when required Anthropic configuration is missing from the environment."""


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise AnthropicConfigError(
            f"Missing required environment variable '{name}'. "
            "Set ANTHROPIC_API_KEY and ANTHROPIC_MODEL before making Anthropic API calls."
        )
    return value


@dataclass(frozen=True)
class AnthropicConfig:
    """Anthropic API settings, read once from env. api_key is never exposed via repr/str."""

    api_key: str
    model: str

    def __repr__(self) -> str:
        return f"AnthropicConfig(api_key='***', model={self.model!r})"


def get_anthropic_config() -> AnthropicConfig:
    """Read Anthropic settings from the environment.

    Raises AnthropicConfigError if ANTHROPIC_API_KEY or ANTHROPIC_MODEL is
    unset or blank, so misconfiguration fails at startup/first-use rather
    than surfacing as an opaque 401 from the Anthropic API later.
    """
    return AnthropicConfig(
        api_key=_require_env("ANTHROPIC_API_KEY"),
        model=_require_env("ANTHROPIC_MODEL"),
    )


@lru_cache(maxsize=1)
def get_anthropic_client() -> AsyncAnthropic:
    """Process-wide cached AsyncAnthropic client, built from environment config."""
    return AsyncAnthropic(api_key=get_anthropic_config().api_key)


@lru_cache(maxsize=1)
def get_anthropic_model() -> str:
    """Process-wide cached Claude model name used for every Claude call in the MVP."""
    return get_anthropic_config().model
