"""
Supabase / Postgres connection settings (asyncpg).

Usage: from common.config.database_config import get_database_config
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env when config is imported (uvicorn cwd may vary)
_BACKEND_DIR = Path(__file__).resolve().parents[3]
load_dotenv(_BACKEND_DIR / ".env")


@dataclass(frozen=True)
class DatabaseConfig:
    """Postgres connection settings for asyncpg."""

    url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", ""))
    min_size: int = field(
        default_factory=lambda: int(os.environ.get("DATABASE_POOL_MIN_SIZE", "1"))
    )
    max_size: int = field(
        default_factory=lambda: int(os.environ.get("DATABASE_POOL_MAX_SIZE", "5"))
    )

    @property
    def dsn(self) -> str:
        """asyncpg-compatible DSN (strip SQLAlchemy-style +asyncpg prefix)."""
        return self.url.replace("postgresql+asyncpg://", "postgresql://")


def get_database_config() -> DatabaseConfig:
    return DatabaseConfig()
