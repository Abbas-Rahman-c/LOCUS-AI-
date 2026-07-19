"""
Locus AI — Voyage AI configuration (importable module).

Real implementation for the dot-named voyage.config.py stub, following the
database.config.py -> database_config.py / anthropic.config.py ->
anthropic_config.py pattern: the dotted file is a pointer, this is the
module other code actually imports.

Usage: from common.config.voyage_config import get_voyage_config

Like anthropic_config.py, VOYAGE_API_KEY must never silently default to ""
- an unset key must never reach the Voyage client. VOYAGE_MODEL defaults to
"voyage-4" per the current architecture (repository convention already
allows defaults elsewhere, e.g. slack_config.py). VOYAGE_OUTPUT_DIMENSION
defaults to 1024 to match public.decision_embeddings.embedding
(vector(1024), migration 007) but is validated regardless of source — a
misconfigured dimension must fail at config time, not surface later as an
opaque pgvector insert error.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

REQUIRED_OUTPUT_DIMENSION = 1024
DEFAULT_MODEL = "voyage-4"


class VoyageConfigError(RuntimeError):
    """Raised when required Voyage configuration is missing or invalid."""


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise VoyageConfigError(
            f"Missing required environment variable '{name}'. "
            "Set VOYAGE_API_KEY before making Voyage API calls."
        )
    return value


@dataclass(frozen=True)
class VoyageConfig:
    """Voyage API settings, read once from env. api_key is never exposed via repr/str."""

    api_key: str
    model: str
    output_dimension: int

    def __repr__(self) -> str:
        return (
            f"VoyageConfig(api_key='***', model={self.model!r}, "
            f"output_dimension={self.output_dimension!r})"
        )


def get_voyage_config() -> VoyageConfig:
    """Read Voyage settings from the environment.

    Raises VoyageConfigError if VOYAGE_API_KEY is unset/blank, or if
    VOYAGE_OUTPUT_DIMENSION resolves to anything other than 1024 — the only
    dimension public.decision_embeddings.embedding (vector(1024)) accepts.
    """
    model = os.environ.get("VOYAGE_MODEL", "").strip() or DEFAULT_MODEL

    raw_dimension = os.environ.get("VOYAGE_OUTPUT_DIMENSION", "").strip()
    if raw_dimension:
        try:
            output_dimension = int(raw_dimension)
        except ValueError as exc:
            raise VoyageConfigError(
                f"VOYAGE_OUTPUT_DIMENSION must be an integer, got {raw_dimension!r}."
            ) from exc
    else:
        output_dimension = REQUIRED_OUTPUT_DIMENSION

    if output_dimension != REQUIRED_OUTPUT_DIMENSION:
        raise VoyageConfigError(
            f"VOYAGE_OUTPUT_DIMENSION must be {REQUIRED_OUTPUT_DIMENSION} to match "
            f"public.decision_embeddings.embedding (vector({REQUIRED_OUTPUT_DIMENSION})); "
            f"got {output_dimension}."
        )

    return VoyageConfig(
        api_key=_require_env("VOYAGE_API_KEY"),
        model=model,
        output_dimension=output_dimension,
    )
