"""
Supabase / Postgres connection settings (asyncpg).

Usage:
  from common.config.database_config import get_app_database_config, get_admin_database_config

- APP_DATABASE_URL → non-bypass role (locus_app); workers + API runtime
- DATABASE_URL → postgres; admin scripts, migrations, cross-tenant jobs
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

    url: str
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


def get_admin_database_config() -> DatabaseConfig:
    """postgres / bypass role — migrations, admin scripts, cross-tenant jobs."""
    return DatabaseConfig(url=os.environ.get("DATABASE_URL", ""))


def get_app_database_config() -> DatabaseConfig:
    """Non-bypass locus_app role — workers and API (subject to row-level security)."""
    return DatabaseConfig(url=os.environ.get("APP_DATABASE_URL", ""))


def get_database_config() -> DatabaseConfig:
    """Backward-compatible alias for admin DATABASE_URL."""
    return get_admin_database_config()
