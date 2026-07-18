"""
Shared database connection pool helper.

Thin re-export of database.pool so imports stay on one singleton
(lifespan / workers initialise via database.pool.init_db_pool).
"""
from __future__ import annotations

from database.pool import get_db_pool, init_db_pool

__all__ = ["get_db_pool", "init_db_pool"]
