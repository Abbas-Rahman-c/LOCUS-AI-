"""
Voyage AI embedding configuration - shared by query-time and document-time
embedding.

Reads VOYAGE_API_KEY, VOYAGE_MODEL, VOYAGE_OUTPUT_DIMENSION. Backs both
modules.ai.embeddings.provider.embed_query() (Phase 2 retrieval) and
embed_document() (the ingestion write path, migrations/010_decision_
embeddings_voyage_ai.sql resizes decision_embeddings.embedding to match).

VOYAGE_OUTPUT_DIMENSION defaults to 1024 to match decision_embeddings.
embedding's vector(1024) column. A misconfigured dimension must fail loudly
here rather than surface later as an opaque pgvector error.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REQUIRED_OUTPUT_DIMENSION = 1024


class VoyageConfigError(RuntimeError):
    """Raised when required Voyage configuration is missing or invalid."""


class VoyageSettings(BaseSettings):
    voyage_api_key: str = Field(..., alias="VOYAGE_API_KEY")
    voyage_model: str = Field(default="voyage-4", alias="VOYAGE_MODEL")
    voyage_output_dimension: int = Field(
        default=REQUIRED_OUTPUT_DIMENSION, alias="VOYAGE_OUTPUT_DIMENSION"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


_settings: VoyageSettings | None = None


def get_voyage_config() -> VoyageSettings:
    """Read Voyage settings from the environment (cached after first call).

    Raises VoyageConfigError if VOYAGE_API_KEY is unset/blank, or if
    VOYAGE_OUTPUT_DIMENSION resolves to anything other than 1024 - the only
    dimension the live decision_embeddings.embedding column accepts today.
    """
    global _settings
    if _settings is None:
        try:
            _settings = VoyageSettings()  # type: ignore[call-arg]
        except Exception as exc:
            raise VoyageConfigError(f"Missing or invalid Voyage configuration: {exc}") from exc

    if _settings.voyage_output_dimension != REQUIRED_OUTPUT_DIMENSION:
        raise VoyageConfigError(
            f"VOYAGE_OUTPUT_DIMENSION must be {REQUIRED_OUTPUT_DIMENSION} to match "
            f"the live decision_embeddings.embedding column; got "
            f"{_settings.voyage_output_dimension}."
        )
    return _settings
